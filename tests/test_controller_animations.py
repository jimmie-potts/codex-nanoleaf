"""Requested Free-only animations through the integration extension and the Lines worker (#92)."""
import contextlib
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_scene_restore as scenes
from test_bridge import b
import controller_server as server
import effects
import integration_api

WAVE = {'kind': 'animation.play', 'pattern': 'wave', 'colors': ['#0044aa', '#00aa66'], 'speed': 'slow'}


class AnimationTest(unittest.TestCase):
    run_worker = scenes.SceneTest.run_worker
    query = scenes.SceneTest.query

    def setUp(self):
        scenes.SceneTest.setUp(self)
        server.configure(self.directory, b, 'controller', 'device', 'source')
        self.token = server.issue(self.directory, b, 'client', ['read', 'control'])
        self.launched = []
        self.app = server.App(self.directory, b, launch=self.launched.append)
        # Admission and the worker share the test clock for expiry and admission order.
        for module in (integration_api, server, server.state):
            clock = patch.object(module, 'time', SimpleNamespace(time=self.clock.now, monotonic=time.monotonic))
            clock.start(); self.addCleanup(clock.stop)

    def mode(self, name):
        b.set_mode(self.directory, name, launch=lambda _: None, now=self.clock.now)

    def options(self):
        return self.app.integration_animations(self.token, 'device')

    def request(self, command=WAVE, **changes):
        view = self.options()
        return dict(dict(apiVersion=integration_api.VERSION, controllerId='controller', deviceId='device',
                         requestId=view['nextRequestId'], expectedRevision=view['revision'], command=command), **changes)

    def play(self, command=WAVE, **changes):
        req = self.request(command, **changes)
        return req, self.app.integration_admit(self.token, req)

    def receipt(self, req):
        return json.loads(self.query('SELECT receipt FROM integration_requests WHERE sequence=%d' % req['requestId']['sequence'])[0][0])

    def puts(self):
        return [(endpoint, payload) for _, method, endpoint, payload in self.device.calls if method == 'PUT']

    def expected(self, command=WAVE):
        return effects.render(command, self.config['line_groups'], self.config['line_positions'])

    def free(self):
        self.mode('free'); self.run_worker(); self.device.calls.clear()


class AdmissionTest(AnimationTest):
    def test_rejected_in_work_and_quiet_without_a_ticket_write_or_mode_change(self):
        for mode in ('work', 'quiet'):
            self.mode(mode)
            before = self.options()['nextRequestId']
            _, result = self.play()
            self.assertEqual(result, (422, {'failure': {'code': 'unsupported-capability'}}))
            self.assertEqual(self.options()['nextRequestId'], before)
            self.assertEqual(self.options()['mode'], mode.capitalize())
        self.assertEqual(self.query('SELECT * FROM integration_requests'), [])
        self.assertEqual((self.device.calls, self.launched), ([], []))

    def test_invalid_stale_oversized_and_unplaced_requests_consume_no_ticket(self):
        self.free()
        before = self.options()['nextRequestId']
        cases = [
            (dict(WAVE, pattern='pulse', direction='left'), {}, 400, 'invalid-request'),
            (dict(WAVE, colors=['#12345']), {}, 400, 'invalid-request'),
            (dict(WAVE, extra=1), {}, 400, 'invalid-request'),
            (WAVE, {'expectedRevision': 'f' * 64}, 409, 'revision-conflict'),
        ]
        for command, changes, code, failure in cases:
            with self.subTest(command=command, changes=changes):
                self.assertEqual(self.play(command, **changes)[1], (code, {'failure': {'code': failure}}))
        with patch.object(effects, 'MAX_BYTES', 100):
            self.assertEqual(self.play()[1], (429, {'failure': {'code': 'capacity'}}))
        (self.directory / 'layout.json').write_text(json.dumps({'line_groups': self.config['line_groups']}))
        self.assertEqual(self.play()[1], (422, {'failure': {'code': 'unsupported-capability'}}))
        self.assertEqual(self.play(dict(WAVE, pattern='pulse', colors=['#ffffff']))[1][0], 202)  # Non-spatial needs no positions.
        self.assertEqual(before['sequence'] + 1, self.options()['nextRequestId']['sequence'])

    def test_accepted_in_free_joins_duplicates_and_blocks_a_second_queue(self):
        self.mode('free')  # Desired Free; the handoff itself may still be pending.
        req, (code, receipt) = self.play()
        self.assertEqual((code, receipt), (202, dict(apiVersion=integration_api.VERSION, requestId=req['requestId'], outcome='queued',
                                                     priorEffects='none', physicalOutcome='unknown')))
        self.assertEqual(self.launched, [self.directory])
        self.assertEqual(self.app.integration_admit(self.token, req), (202, receipt))
        self.assertEqual(self.app.integration_admit(self.token, dict(req, command=dict(WAVE, speed='fast')))[0], 409)
        self.assertEqual(self.play()[1], (429, {'failure': {'code': 'capacity'}}))
        view = self.app.integration_snapshot(self.token, 'device')
        self.assertEqual(view['pending'], [req])

    def test_options_route_is_pure_and_the_snapshot_shape_is_unchanged(self):
        reader = server.issue(self.directory, b, 'reader', ['read'])
        before = (self.directory / 'status.sqlite').read_bytes()
        view = self.app.integration_animations(reader, 'device')
        self.assertEqual((self.directory / 'status.sqlite').read_bytes(), before)
        self.assertEqual(view['patterns'], [{'id': 'wave', 'spatial': True}, {'id': 'gradient', 'spatial': True},
                                            {'id': 'pulse', 'spatial': False}, {'id': 'breathe', 'spatial': False},
                                            {'id': 'sparkle', 'spatial': False}])
        self.assertEqual(view['speeds'], ['slow', 'medium', 'fast'])
        self.assertEqual(view['directions'], ['left', 'right', 'up', 'down', 'outward', 'inward'])
        self.assertEqual(view['defaults'], {'speed': 'medium', 'direction': 'right', 'loop': True})
        self.assertEqual(view['limits'], {'minColors': 1, 'maxColors': 8, 'maxFramesPerZone': 20, 'maxEffectBytes': 8192})
        snapshot = self.app.integration_snapshot(reader, 'device')
        self.assertEqual((view['mode'], view['revision'], view['nextRequestId'], view['identity']),
                         ('Work', snapshot['revision'], snapshot['nextRequestId'], snapshot['identity']))
        self.assertEqual(set(snapshot['capabilities']), {'settings.set', 'elements.assign', 'task.assign', 'project.color', 'mode.set'})
        self.assertEqual(snapshot['limits'], {'maxItems': 1000, 'maxPending': 1, 'maxReceipts': 256, 'maxBodyBytes': 65536})
        self.assertNotIn('animation', json.dumps(snapshot))
        with self.assertRaises(integration_api.Failure):
            self.app.integration_animations(reader, 'other')
        self.assertEqual(self.device.calls, [])


class WorkerTest(AnimationTest):
    def v1(self, command):
        snap = self.app.snapshot()
        req = dict(apiVersion='1.0', controllerId='controller', deviceId='device', requestId=snap['nextRequestId'],
                   expectedConfigurationRevision=snap['configurationRevision'], expectedGeneration=snap['generation'], command=command)
        return self.app.admit(self.token, req)

    def animation_writes(self):
        return [payload for endpoint, payload in self.puts() if endpoint == '/effects' and 'write' in payload
                and payload['write']['animType'] == 'custom']

    def test_plays_once_after_the_free_handoff_and_never_again(self):
        scenes.SceneTest.event(self, 'UserPromptSubmit')  # The bridge owns a status display to hand off.
        played = []
        def switch():
            self.mode('free')  # Pending: the handoff and the animation share one pass.
            played.append(self.play())
        self.run_worker([(1002, switch)])
        req, (code, _) = played[0]
        self.assertEqual(code, 202)
        after = [(endpoint, payload) for at, method, endpoint, payload in self.device.calls if method == 'PUT' and at >= 1002]
        self.assertEqual(after[-1], ('/effects', self.expected()))
        self.assertIn(('/effects', {'select': 'Beach Waves'}), after[:-1])  # The Free handoff restored the scene first.
        receipt = self.receipt(req)
        self.assertEqual((receipt['outcome'], receipt['priorEffects'], receipt['physicalOutcome']), ('sent', 'confirmed-transmission', 'unknown'))
        self.assertNotIn('failure', receipt)
        self.assertEqual(self.app.integration_admit(self.token, req), (200, receipt))
        self.assertEqual(self.options()['mode'], 'Free')
        self.device.calls.clear(); self.run_worker()
        self.assertEqual(self.device.calls, [])

    def test_explicit_mode_commands_retire_a_queued_animation(self):
        commands = [lambda: self.mode('work'), lambda: self.mode('quiet'), lambda: self.mode('free'),
                    lambda: self.assertEqual(self.v1({'kind': 'mode.set', 'mode': 'Free'})[0] // 100, 2)]
        for command in commands:
            with self.subTest(command=command):
                self.free()
                req, (code, _) = self.play()
                self.assertEqual(code, 202)
                command()
                receipt = self.receipt(req)
                self.assertEqual((receipt['outcome'], receipt['failure'], receipt['priorEffects']), ('cancelled', {'code': 'stale-generation'}, 'none'))
                self.mode('free'); self.run_worker()  # Quiet would keep the worker watching.
                self.assertEqual(self.animation_writes(), [])

    def test_failed_send_ends_uncertain_and_is_never_replayed(self):
        self.free()
        req, _ = self.play()
        self.device.fail = lambda method, endpoint, payload: endpoint == '/effects' and 'write' in (payload or {})
        with self.assertRaises(OSError):
            self.run_worker()
        receipt = self.receipt(req)
        self.assertEqual((receipt['outcome'], receipt['failure'], receipt['priorEffects']), ('uncertain', {'code': 'uncertain-result'}, 'possible'))
        self.assertEqual(self.app.integration_admit(self.token, req), (200, receipt))
        self.device.calls.clear(); self.run_worker()
        self.assertEqual(self.animation_writes(), [])
        self.assertEqual(self.options()['nextRequestId']['sequence'], req['requestId']['sequence'] + 1)

    def test_worker_restart_finishes_an_interrupted_attempt_as_uncertain(self):
        self.free()
        req, _ = self.play()
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("UPDATE integration_requests SET phase='attempting' WHERE sequence=?", (req['requestId']['sequence'],))
        self.assertEqual(self.play()[1], (429, {'failure': {'code': 'capacity'}}))  # Still in flight.
        self.assertEqual(self.app.integration_snapshot(self.token, 'device')['pending'], [req])
        self.run_worker()
        self.assertEqual(self.animation_writes(), [])
        receipt = self.receipt(req)
        self.assertEqual((receipt['outcome'], receipt['failure'], receipt['priorEffects']), ('uncertain', {'code': 'uncertain-result'}, 'possible'))

    def test_scene_and_animation_play_in_admission_order(self):
        self.run_worker()  # Work observation discovers the fake device's scenes.
        scene = self.app.snapshot()['capabilities']['scenes']['sceneIds'][1]
        self.free()
        self.assertEqual(self.v1({'kind': 'scene.activate', 'sceneId': scene})[0], 202)
        self.clock.sleep(0.1)
        self.play()
        self.run_worker()
        self.assertEqual([p.get('select', 'animation') for _, p in self.puts()], ['Cotton Candy', 'animation'])
        self.device.calls.clear()
        self.play()
        self.clock.sleep(0.1)
        self.assertEqual(self.v1({'kind': 'scene.activate', 'sceneId': scene})[0], 202)
        self.run_worker()
        self.assertEqual([p.get('select', 'animation') for _, p in self.puts()], ['animation', 'Cotton Candy'])

    def test_cancel_revocation_and_expiry_retire_before_send(self):
        self.free()
        req, _ = self.play()
        self.assertEqual(self.app.integration_cancel(self.token, 'device', req['requestId'])[1]['outcome'], 'cancelled')
        req, _ = self.play()
        server.revoke(self.directory, b, 'client')
        self.assertEqual((self.receipt(req)['outcome'], self.receipt(req)['failure']), ('cancelled', {'code': 'forbidden'}))
        self.token = server.issue(self.directory, b, 'client', ['read', 'control'])
        req, _ = self.play()
        self.clock.sleep(31)
        self.run_worker()
        self.assertEqual((self.receipt(req)['outcome'], self.receipt(req)['failure']), ('failed', {'code': 'request-expired'}))
        self.assertEqual(self.animation_writes(), [])

    def test_mode_committed_while_the_attempt_is_recorded_prevents_the_send(self):
        self.free()
        req, _ = self.play()
        record = integration_api.attempt
        def racing(db, sequence):
            generation = record(db, sequence)
            self.mode('work')  # Commits between the durable attempt and the send.
            return generation
        with patch.object(integration_api, 'attempt', racing):
            self.run_worker()
        self.assertEqual(self.animation_writes(), [])
        self.assertEqual((self.receipt(req)['outcome'], self.receipt(req)['failure']), ('cancelled', {'code': 'stale-generation'}))

    def test_revocation_or_disable_while_the_attempt_is_recorded_prevents_the_send(self):
        interventions = {'revoke': lambda: server.revoke(self.directory, b, 'client'),
                         'disable': lambda: server.command(['controller-disable', '--state-dir', str(self.directory)], b)}
        for name, intervene in interventions.items():
            with self.subTest(name=name):
                self.setUp()
                self.free()
                req, _ = self.play()
                record = integration_api.attempt
                def racing(db, sequence):
                    generation = record(db, sequence)
                    intervene()  # Commits between the durable attempt and the send.
                    return generation
                with patch.object(integration_api, 'attempt', racing):
                    self.run_worker()
                self.assertEqual(self.animation_writes(), [])
                self.assertEqual((self.receipt(req)['outcome'], self.receipt(req)['failure']), ('cancelled', {'code': 'forbidden'}))

    def test_admission_clears_a_transport_hold_like_a_fresh_native_request(self):
        self.run_worker()  # Work observation discovers the fake device's scenes.
        scene = self.app.snapshot()['capabilities']['scenes']['sceneIds'][1]
        self.free()
        self.device.fail = lambda method, endpoint, payload: 'select' in (payload or {})
        self.assertEqual(self.v1({'kind': 'scene.activate', 'sceneId': scene})[0], 202)
        with self.assertRaises(OSError):
            self.run_worker()
        self.assertTrue(self.query("SELECT 1 FROM meta WHERE key='controller_hold_revision'"))
        req, (code, _) = self.play()
        self.assertEqual(code, 202)
        self.assertEqual(self.query("SELECT 1 FROM meta WHERE key='controller_hold_revision'"), [])
        self.device.calls.clear(); self.run_worker()
        self.assertEqual(self.animation_writes(), [self.expected()])
        self.assertEqual(self.receipt(req)['outcome'], 'sent')
        self.assertNotIn(('/effects', {'select': 'Cotton Candy'}), self.puts())  # The uncertain scene is not replayed.

    def test_unsent_animation_restores_the_hold_like_unsent_v1_work(self):
        hold = lambda: self.query("SELECT value FROM meta WHERE key='controller_hold_revision'")
        revision = lambda: self.query("SELECT value FROM meta WHERE key='mode_revision'")
        self.free()
        def fail(_):
            raise OSError('launch failed')
        self.app = server.App(self.directory, b, launch=fail)
        req, (code, receipt) = self.play()
        self.assertEqual((code, receipt['outcome'], receipt['failure']), (503, 'failed', {'code': 'transport-failure'}))
        self.assertEqual(hold(), revision())  # The admission's authorization does not outlive the failed launch.
        self.app = server.App(self.directory, b, launch=lambda _: None)
        req, (code, _) = self.play()
        self.assertEqual((code, hold()), (202, []))
        self.clock.sleep(31)
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            integration_api.recover(db)  # The listener's maintenance expires unsent work.
        self.assertEqual((self.receipt(req)['outcome'], self.receipt(req)['failure']), ('failed', {'code': 'request-expired'}))
        self.assertEqual(hold(), revision())
        self.run_worker()
        self.assertEqual(self.animation_writes(), [])


class HTTPTest(AnimationTest):
    def test_route_needs_credentials_and_serves_the_options(self):
        import test_controller_api
        import threading
        self.server = server.make_server(self.app)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join()))
        http = lambda *a, **kw: test_controller_api.ControllerHTTPTest.http(self, *a, **kw)
        path = '/controller/integration/v1/animations?deviceId=device'
        self.assertEqual(http('GET', path, token=False)[0], 401)
        self.assertEqual(http('GET', path + '&extra=1')[0], 404)
        code, view = http('GET', path)
        self.assertEqual((code, view['limits']['maxColors']), (200, 8))
        self.mode('free')
        self.assertEqual(http('POST', '/controller/integration/v1/commands', self.request())[0], 202)


if __name__ == '__main__':
    unittest.main()
