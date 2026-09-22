"""Native power, brightness and saved-scene controls through the protected controller (#64)."""
import contextlib
import json
import unittest
from unittest.mock import patch
import test_scene_restore as scenes
from test_bridge import b
import controller_server as server
import controller_state as state


class ControlsTest(unittest.TestCase):
    run_worker = scenes.SceneTest.run_worker
    query = scenes.SceneTest.query
    event = scenes.SceneTest.event
    saved = scenes.SceneTest.saved

    def setUp(self):
        scenes.SceneTest.setUp(self)
        server.configure(self.directory, b, 'controller', 'device', 'source')
        self.token = server.issue(self.directory, b, 'client', ['read', 'control'])
        self.app = server.App(self.directory, b, launch=lambda _: None)

    def mode(self, name):
        b.set_mode(self.directory, name, launch=lambda _: None, now=self.clock.now)

    def command(self, command):
        snap = self.app.snapshot()
        req = dict(apiVersion='1.0', controllerId='controller', deviceId='device', requestId=snap['nextRequestId'],
                   expectedConfigurationRevision=snap['configurationRevision'], expectedGeneration=snap['generation'], command=command)
        return req, self.app.admit(self.token, req)

    def puts(self):
        return [(endpoint, payload) for _, method, endpoint, payload in self.device.calls if method == 'PUT']

    def scene_ids(self):
        return self.app.snapshot()['capabilities']['scenes']['sceneIds']

    def test_capabilities_declare_power_brightness_and_scenes_with_constraints(self):
        snap = self.app.snapshot()
        self.assertTrue(self.app.contract.validate('snapshot', snap))
        caps = snap['capabilities']
        self.assertEqual(caps['power'], {'supported': True})
        self.assertEqual(caps['brightness'], {'supported': True, 'minimum': 0, 'maximum': 100})
        self.assertEqual(caps['scenes'], {'supported': True, 'sceneIds': []})
        for name in ('media', 'zones', 'preview'):
            self.assertEqual(caps[name], {'supported': False})
        self.assertEqual(caps['modes'], {'supported': True, 'values': ['Work', 'Quiet', 'Free']})
        self.assertEqual(snap['state']['desired']['power'], {'status': 'unknown'})
        self.assertEqual(snap['state']['desired']['brightness'], {'status': 'unknown'})

    def test_admission_replays_power_and_reports_desired_state_before_send(self):
        req, (code, receipt) = self.command({'kind': 'power.set', 'on': False})
        self.assertEqual(code, 202); self.assertEqual(receipt['outcome'], 'queued')
        self.assertEqual(self.app.admit(self.token, req), (code, receipt))
        snap = self.app.snapshot()
        self.assertTrue(self.app.contract.validate('snapshot', snap))
        self.assertEqual(snap['state']['desired']['power'], {'status': 'known', 'value': False})
        self.assertEqual(snap['state']['desired']['brightness'], {'status': 'unknown'})
        self.assertEqual([p['command'] for p in snap['state']['pending']], [{'kind': 'power.set', 'on': False}])
        self.assertEqual(snap['state']['lastSuccessfulSend'], {'status': 'unknown'})
        self.assertEqual(snap['state']['observation'], {'status': 'unknown'})
        self.assertEqual(self.device.calls, [])
        _, (code, receipt) = self.command({'kind': 'brightness.set', 'percent': 55})
        self.assertEqual(code, 202)
        self.assertEqual(self.app.snapshot()['state']['desired']['brightness'], {'status': 'known', 'value': 55})

    def test_scene_rejected_in_work_and_quiet_before_any_write(self):
        self.run_worker()  # Work observation discovers the fake device's scenes.
        ids = self.scene_ids(); self.assertEqual(len(ids), 2)
        self.assertNotIn('Beach Waves', json.dumps(self.app.snapshot()))
        self.device.calls.clear()
        for mode in ('work', 'quiet'):
            self.mode(mode)
            req, (code, receipt) = self.command({'kind': 'scene.activate', 'sceneId': ids[1]})
            self.assertEqual(code, 422); self.assertEqual(receipt['outcome'], 'failed')
            self.assertEqual(receipt['failure'], {'code': 'unsupported-capability'})
            self.assertTrue(self.app.contract.validate('receipt', receipt))
            self.assertEqual(self.app.admit(self.token, req), (200, receipt))
        self.mode('free'); self.run_worker()  # Only the identity check can reject in Free.
        self.device.calls.clear()
        _, (code, receipt) = self.command({'kind': 'scene.activate', 'sceneId': 'scene-unknown'})
        self.assertEqual(code, 422); self.assertEqual(receipt['failure']['code'], 'unsupported-capability')
        self.assertEqual([c for c in self.device.calls if c[1] == 'PUT'], [])
        self.assertEqual(self.app.snapshot()['state']['pending'], [])

    def test_power_and_brightness_in_free_are_one_write_each_without_polling(self):
        self.mode('free'); self.run_worker()
        self.device.calls.clear()
        for command, write in (({'kind': 'brightness.set', 'percent': 42}, ('/state', {'brightness': {'value': 42, 'duration': 0}})),
                               ({'kind': 'power.set', 'on': False}, ('/state', {'on': {'value': False}}))):
            req, (code, receipt) = self.command(command)
            self.assertEqual((code, receipt['outcome']), (202, 'queued'))
            self.run_worker()
            self.assertEqual(self.device.calls[-1][1:], ('PUT',) + write)
            self.assertEqual(self.receipt(req)['outcome'], 'sent')
            self.assertEqual([c for c in self.device.calls if c[1] == 'GET'], [])
        desired = self.app.snapshot()['state']['desired']
        self.assertEqual((desired['brightness'], desired['power']), ({'status': 'known', 'value': 42}, {'status': 'known', 'value': False}))
        self.assertEqual((self.device.brightness, self.device.on), (42, False))
        self.device.calls.clear(); self.run_worker()
        self.assertEqual(self.device.calls, [])

    def test_scene_that_disappears_before_send_fails_typed_without_a_write(self):
        self.run_worker()
        ids = self.scene_ids()
        self.mode('free'); self.run_worker()
        req, (code, _) = self.command({'kind': 'scene.activate', 'sceneId': ids[1]})
        self.assertEqual(code, 202)
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            state.discovered(db, ['Beach Waves'])
        self.device.calls.clear(); self.run_worker()
        self.assertEqual([c for c in self.device.calls if c[1] == 'PUT'], [])
        self.assertEqual((self.receipt(req)['outcome'], self.receipt(req)['failure']), ('failed', {'code': 'unsupported-capability'}))
        self.assertEqual(self.app.admit(self.token, req), (200, self.receipt(req)))

    def receipt(self, req):
        return json.loads(self.query('SELECT receipt FROM controller_requests WHERE sequence=%d' % req['requestId']['sequence'])[0][0])

    def test_brightness_executes_once_through_worker_and_governs_work_indicators(self):
        self.event('UserPromptSubmit')
        self.run_worker([(1003, lambda: self.event('Interrupt'))])
        self.assertEqual(self.device.brightness, 43)  # Idle: the remembered scene returned.
        self.event('UserPromptSubmit', 'b')
        req, _ = self.command({'kind': 'brightness.set', 'percent': 60})
        self.device.calls.clear()
        self.run_worker([(1002, lambda: self.event('Interrupt', 'b'))])
        writes = self.puts()
        self.assertEqual(writes[0], ('/state', {'brightness': {'value': 60, 'duration': 0}}))
        self.assertEqual(self.receipt(req)['outcome'], 'sent')
        self.assertEqual(self.receipt(req)['completedOperations'], ['transport-1'])
        self.assertEqual(self.app.admit(self.token, req), (200, self.receipt(req)))
        indicator = [p for e, p in writes if e == '/state' and 'on' in p]
        self.assertTrue(indicator)
        self.assertTrue(all(p['brightness']['value'] == 60 for p in indicator))
        self.assertEqual(self.saved()['scene'], {'name': 'Beach Waves', 'brightness': 43})
        self.assertEqual(self.device.brightness, 60)  # Idle restore keeps the override.
        self.assertEqual(self.app.snapshot()['state']['lastSuccessfulSend']['requestId'], req['requestId'])

    def test_uncertain_control_write_is_held_until_explicit_choice(self):
        req, _ = self.command({'kind': 'brightness.set', 'percent': 60})
        self.device.fail = lambda method, endpoint, payload: method == 'PUT'
        with self.assertRaises(OSError):
            self.run_worker()
        self.assertEqual(self.receipt(req)['outcome'], 'uncertain')
        self.assertEqual(self.receipt(req)['priorEffects'], 'possible')
        calls = list(self.device.calls)
        self.run_worker()
        self.assertEqual(self.device.calls, calls)
        self.mode('quiet')
        self.run_worker([(1001, lambda: self.mode('free'))])
        self.assertTrue(self.puts())

    def test_mode_command_cancels_queued_control_as_stale_generation(self):
        req, _ = self.command({'kind': 'brightness.set', 'percent': 60})
        self.mode('quiet')
        receipt = self.receipt(req)
        self.assertEqual((receipt['outcome'], receipt['failure']['code']), ('cancelled', 'stale-generation'))
        self.assertEqual(self.app.snapshot()['state']['desired']['brightness'], {'status': 'unknown'})
        seen = []
        self.run_worker([(1001, lambda: seen.append(self.device.brightness)), (1002, lambda: self.mode('free'))])
        self.assertNotIn(('/state', {'brightness': {'value': 60, 'duration': 0}}), self.puts())
        self.assertEqual(seen, [10])

    def test_quiet_idle_override_persists_until_same_mode_quiet_reapplies_ten_percent(self):
        # Quiet keeps watching, so the run ends with an explicit Free choice.
        seen = []
        observe = lambda: seen.append((self.device.brightness, self.saved()['scene']['brightness'], self.saved()['quiet_brightness']))
        self.mode('quiet')
        self.run_worker([(1001, observe), (1002, lambda: self.command({'kind': 'brightness.set', 'percent': 50})),
                         (1005, observe), (1006, lambda: self.mode('quiet')), (1009, observe),
                         (1010, lambda: self.mode('free'))])
        self.assertEqual(seen, [(10, 43, 10), (50, 43, 50), (10, 43, 10)])
        self.assertEqual((self.device.selected, self.device.brightness), ('Beach Waves', 43))
        self.assertEqual(self.app.snapshot()['state']['desired']['brightness'], {'status': 'unknown'})

    def test_work_idle_override_is_restored_by_same_mode_work_without_reselecting(self):
        self.run_worker()
        self.command({'kind': 'brightness.set', 'percent': 70})
        self.run_worker()
        self.assertEqual(self.device.brightness, 70)
        self.run_worker()
        self.assertEqual(self.saved()['scene'], {'name': 'Beach Waves', 'brightness': 43})
        self.device.calls.clear()
        self.mode('work'); self.run_worker()
        self.assertEqual(self.device.brightness, 43)
        self.assertEqual([e for e, _ in self.puts()], ['/state'])
        self.assertEqual(self.app.snapshot()['state']['desired']['brightness'], {'status': 'unknown'})

    def test_power_off_suppresses_indicator_writes_and_keeps_tracking(self):
        self.event('UserPromptSubmit')
        self.run_worker([(1001, lambda: self.event('Interrupt'))])
        self.event('UserPromptSubmit', 'b')
        req, _ = self.command({'kind': 'power.set', 'on': False})
        seen = []
        self.device.calls.clear()
        self.run_worker([(1002, lambda: self.event('PermissionRequest', 'b', tool_name='exec_command')),
                         (1003, lambda: seen.append((dict(self.query('SELECT id,status FROM sessions'))['b'],
                                                     self.query("SELECT started FROM activity WHERE session='b'")))),
                         (1004, lambda: self.event('Interrupt', 'b'))])
        self.assertEqual(self.puts(), [('/state', {'on': {'value': False}})])
        self.assertEqual(self.receipt(req)['outcome'], 'sent')
        self.assertEqual(seen, [('blocked', [(1002.0,)])])  # Tracking continued while dark: the status change got its epoch.
        self.assertEqual(dict(self.query('SELECT id,status FROM sessions'))['b'], 'idle')
        self.assertEqual(self.app.snapshot()['state']['desired']['power'], {'status': 'known', 'value': False})
        self.event('UserPromptSubmit', 'c')
        self.device.calls.clear(); self.mode('work')
        self.assertEqual(self.app.snapshot()['state']['desired']['power'], {'status': 'unknown'})
        self.run_worker([(1006, lambda: self.event('Interrupt', 'c'))])
        self.assertTrue(any(e == '/state' and p.get('on') == {'value': True} for e, p in self.puts()))

    def test_scene_activates_in_free_with_one_write_and_no_polling(self):
        self.event('UserPromptSubmit')
        self.run_worker([(1001, lambda: self.event('Interrupt'))])
        ids = self.scene_ids()
        self.mode('free'); self.run_worker()
        started = self.query('SELECT session,started FROM activity')
        self.device.calls.clear()
        req, (code, receipt) = self.command({'kind': 'scene.activate', 'sceneId': ids[1]})
        self.assertEqual(code, 202)
        self.run_worker()
        self.assertEqual(self.device.calls[-1][1:], ('PUT', '/effects', {'select': 'Cotton Candy'}))
        self.assertEqual([c for c in self.device.calls if c[1] == 'PUT'], [self.device.calls[-1]])
        self.assertEqual([c for c in self.device.calls if c[1] == 'GET'], [])
        self.assertEqual(self.receipt(req)['outcome'], 'sent')
        self.assertEqual(self.query('SELECT session,started FROM activity'), started)
        self.device.calls.clear(); self.run_worker()
        self.assertEqual(self.device.calls, [])
        self.mode('work'); self.run_worker()
        self.assertEqual(self.saved()['scene']['name'], 'Cotton Candy')

    def test_free_handoff_clears_override_and_stops_polling(self):
        self.event('UserPromptSubmit')
        self.command({'kind': 'brightness.set', 'percent': 60})
        self.run_worker([(1002, lambda: self.mode('free'))])
        self.assertEqual(self.app.snapshot()['state']['desired']['brightness'], {'status': 'unknown'})
        self.assertEqual((self.device.selected, self.device.brightness), ('Beach Waves', 43))
        self.device.calls.clear(); self.run_worker()
        self.assertEqual(self.device.calls, [])

    def test_free_brightness_is_an_external_change_that_becomes_the_preference(self):
        self.mode('free'); self.run_worker()
        self.command({'kind': 'brightness.set', 'percent': 42}); self.run_worker()
        self.assertEqual(self.saved()['scene'], {'name': 'Beach Waves', 'brightness': 43})
        self.mode('work'); self.run_worker()
        self.assertEqual(self.saved()['scene'], {'name': 'Beach Waves', 'brightness': 42})
        self.assertEqual(self.saved()['quiet_scene'], None)

    def test_discovery_is_bounded_named_only_in_extension_and_quiet_between_changes(self):
        self.device.names = ['Scene %d' % i for i in range(300)] + ['x' * 81]
        self.device.selected = 'Scene 0'
        self.run_worker()
        ids = self.scene_ids()
        self.assertEqual(len(ids), 256)
        self.assertTrue(all(len(i) <= 128 and i.startswith('scene-') for i in ids))
        cursor = self.app.snapshot()['cursor']
        self.run_worker()
        self.assertEqual(self.app.snapshot()['cursor'], cursor)
        self.device.names = ['Beach Waves', 'x' * 81]; self.device.selected = 'Beach Waves'
        self.run_worker()
        listed = self.app.integration_snapshot(self.token, 'device')['scenes']
        self.assertEqual(listed[0], {'id': self.scene_ids()[0], 'name': 'Beach Waves'})
        self.assertEqual(listed[1], {'id': self.scene_ids()[1]})
        self.assertNotIn('Beach Waves', json.dumps(self.app.snapshot()))
        self.assertNotIn('Beach Waves', json.dumps(self.app.feed(None)))

    def test_control_admitted_during_observation_is_not_undone_by_that_iteration(self):
        # The listener can admit a control while the worker is inside its device round trip.
        for command, check in (({'kind': 'power.set', 'on': False}, lambda: (self.device.on, [p for e, p in self.puts() if 'on' in p])),
                               ({'kind': 'brightness.set', 'percent': 70}, lambda: (self.device.brightness, [p['brightness']['value'] for e, p in self.puts() if 'brightness' in p]))):
            self.mode('work')
            self.event('UserPromptSubmit', 'race')
            self.device.calls.clear()
            admitted = []
            original = self.device.request
            def request(config, method, endpoint='', payload=None):
                if method == 'GET' and endpoint == '/effects' and not admitted:
                    admitted.append(self.command(command)[1][1]['outcome'])
                return original(config, method, endpoint, payload)
            with patch.object(b, 'light_request', request):
                self.run_worker([(1002, lambda: self.event('Interrupt', 'race'))])
            self.assertEqual(admitted, ['queued'])
            value, writes = check()
            if command['kind'] == 'power.set':
                self.assertEqual((value, writes), (False, [{'on': {'value': False}}]))
            else:
                self.assertEqual(value, 70)
                self.assertEqual(writes[0], 70)
                self.assertTrue(all(w == 70 for w in writes), writes)

    def test_control_admitted_after_observation_is_seen_by_the_same_pass_guards(self):
        # Admission after the device round trip, during the unread read, must still be honored.
        self.event('UserPromptSubmit', 'late')
        admitted = []
        def unread():
            if not admitted:
                admitted.append(self.command({'kind': 'power.set', 'on': False})[1][1]['outcome'])
            return self.unread
        self.device.calls.clear()
        pending = [(1002, lambda: self.event('Interrupt', 'late'))]
        def advance(seconds):
            self.clock.sleep(seconds)
            self.assertLess(self.clock.now(), 1025, 'Worker did not release control after idle')
            while pending and self.clock.now() >= pending[0][0]:
                pending.pop(0)[1]()
        b.run_worker(self.directory, sleep=advance, now=self.clock.now, read_unread=unread)
        self.assertEqual(admitted, ['queued'])
        self.assertEqual([p for e, p in self.puts() if 'on' in p], [{'on': {'value': False}}])
        self.assertFalse(self.device.on)

    def test_control_committed_between_journaled_sends_is_applied_before_idle_exit(self):
        # A listener commit can land in the window where a journaled send releases the lock.
        self.mode('free'); self.run_worker()
        admitted = []
        original = state.Execution.complete
        def complete(execution):
            if not admitted:
                execution.db.commit()
                admitted.append(self.command({'kind': 'power.set', 'on': False})[1][1]['outcome'])
                execution.db.execute('BEGIN IMMEDIATE')
            return original(execution)
        self.device.calls.clear()
        with patch.object(state.Execution, 'complete', complete):
            self.run_worker()
        self.assertEqual(admitted, ['queued'])
        self.assertEqual(self.puts(), [('/state', {'on': {'value': False}})])
        self.assertEqual(self.app.snapshot()['state']['pending'], [])
        self.assertEqual(self.app.snapshot()['state']['lastOutcome']['receipt']['outcome'], 'sent')

    def test_ledger_without_scene_key_publishes_new_ids_with_an_event(self):
        self.run_worker()
        before = self.app.snapshot()
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            data = state.read(db); del data['sceneKey']; state.save(db, data)
        self.assertEqual(self.scene_ids(), [])
        self.run_worker()
        after = self.app.snapshot()
        self.assertEqual(len(after['capabilities']['scenes']['sceneIds']), 2)
        self.assertNotEqual(after['capabilities']['scenes']['sceneIds'], before['capabilities']['scenes']['sceneIds'])
        self.assertGreater(after['cursor']['sequence'], before['cursor']['sequence'])

    def test_scene_ids_are_not_recoverable_from_published_snapshot_fields(self):
        self.run_worker()
        snap = self.app.snapshot()
        ids = snap['capabilities']['scenes']['sceneIds']
        for epoch in (snap['identity']['controllerEpoch'], snap['generation']['epoch'], snap['nextRequestId']['epoch']):
            guesses = {state.scene_id({'epoch': epoch, 'sceneKey': epoch}, name) for name in self.device.names}
            self.assertFalse(guesses & set(ids))
        with contextlib.closing(state.readonly(self.directory)) as db:
            data = state.read(db)
        self.assertNotIn(data['sceneKey'], json.dumps(snap))
        self.assertNotIn(data['sceneKey'], json.dumps(self.app.integration_snapshot(self.token, 'device')))


if __name__ == '__main__':
    unittest.main()
