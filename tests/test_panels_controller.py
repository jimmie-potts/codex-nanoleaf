"""The NL22 Panels as a second protected-controller device, each ledger owned by its own worker (#113)."""
import contextlib
import http.client
import json
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from test_bridge import b
from test_device_worker import DeviceWorkerTest, ROOT
import controller_server as server
import controller_state
import enrollment
import integration_api
import shared_input
import wall_server

FIXTURE = ROOT / 'tests/fixtures/linux-state-v4'


def puts(fake):
    return [(endpoint, payload) for _, method, endpoint, payload in fake.calls if method == 'PUT']


class PanelsControllerTest(DeviceWorkerTest):
    def setUp(self):
        super().setUp()
        server.configure(self.directory, b, 'controller', 'wall', 'source')
        server.configure(self.directory, b, 'controller', 'panels', 'source')
        self.token = server.issue(self.directory, b, 'client', ['read', 'control'])
        self.app = server.App(self.directory, b, launch=lambda _: None)

    def request(self, device, command):
        snap = self.app.snapshot(device)
        return dict(apiVersion='1.0', controllerId='controller', deviceId=device, requestId=snap['nextRequestId'],
                    expectedConfigurationRevision=snap['configurationRevision'], expectedGeneration=snap['generation'],
                    command=command)

    def command(self, device, command):
        request = self.request(device, command)
        return request, self.app.admit(self.token, request)

    def receipt(self, request):
        row = self.query('SELECT receipt FROM ' + controller_state.table('controller_requests', request['deviceId']) +
                         ' WHERE sequence=?', request['requestId']['sequence'])
        return json.loads(row[0][0])

    def free(self):
        for device in ('wall', 'panels'):
            self.mode('free', device)
            self.run_worker(device)
        self.fake.lines.calls.clear()
        self.fake.panels.calls.clear()

    def discover(self):
        # Work observation records each device's saved scenes in its own ledger.
        self.event('UserPromptSubmit')
        for device in ('wall', 'panels'):
            self.run_worker(device, self.free_after(3, device))


class LedgerTest(PanelsControllerTest):
    def test_status_command_reads_the_named_ledger(self):
        import io
        from contextlib import redirect_stdout
        for device in ('panels', None):
            out = io.StringIO()
            with redirect_stdout(out):
                server.command(['controller-status', '--state-dir', str(self.directory)] + (['--device-id', device] if device else []), b)
            self.assertEqual(json.loads(out.getvalue())['identity']['deviceId'], device or 'wall')

    def test_registered_but_unconfigured_device_is_forbidden(self):
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            controller_state.drop(db, 'panels')
        stale = self.request('wall', {'kind': 'power.set', 'on': True})
        self.assertEqual(self.app.admit(self.token, dict(stale, deviceId='panels')), (403, {'failure': {'code': 'forbidden'}}))
        self.assertEqual(self.app.authorize(self.token, 'panels'), 'forbidden')

    def test_devices_lists_both_ledgers_lines_first(self):
        listed = self.app.devices()
        self.assertEqual([snap['identity']['deviceId'] for snap in listed], ['wall', 'panels'])
        self.assertTrue(all(self.app.contract.validate('snapshot', snap) for snap in listed))
        self.assertNotEqual(listed[0]['identity']['controllerEpoch'], listed[1]['identity']['controllerEpoch'])
        self.assertEqual(self.app.snapshot('panels')['identity'], listed[1]['identity'])
        self.assertEqual(self.app.snapshot()['identity'], listed[0]['identity'])

    def test_configure_adds_only_a_registered_device_and_never_redirects(self):
        wall, panels = self.app.snapshot('wall')['identity'], self.app.snapshot('panels')['identity']
        server.configure(self.directory, b, 'controller', 'panels', 'source')
        server.configure(self.directory, b, 'controller', 'wall', 'source')
        self.assertEqual((self.app.snapshot('wall')['identity'], self.app.snapshot('panels')['identity']), (wall, panels))
        for identity in (('controller', 'missing', 'source'), ('other', 'panels', 'source'), ('controller', 'panels', 'other')):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                server.configure(self.directory, b, *identity)
        self.assertEqual([s['identity']['deviceId'] for s in self.app.devices()], ['wall', 'panels'])

    def test_a_registered_device_cannot_become_the_original_ledger(self):
        fresh = tempfile.TemporaryDirectory(); self.addCleanup(fresh.cleanup)
        directory = Path(fresh.name)
        shutil.copyfile(self.directory / 'config.json', directory / 'config.json')
        with self.assertRaises(ValueError):
            server.configure(directory, b, 'controller', 'panels', 'source')
        with contextlib.closing(b.connect_state(directory)) as db:
            self.assertFalse(controller_state.present(db))

    def test_lines_public_id_cannot_shadow_a_later_registered_device(self):
        fresh = tempfile.TemporaryDirectory(); self.addCleanup(fresh.cleanup)
        directory = Path(fresh.name)
        config = json.loads((self.directory / 'config.json').read_text())
        panels = config['devices'].pop('panels')
        b.write_json(directory / 'config.json', config)
        server.configure(directory, b, 'controller', 'panels', 'source')  # Before the Panels were enrolled.
        config['devices']['panels'] = panels
        b.write_json(directory / 'config.json', config)
        with self.assertRaises(ValueError):
            server.configure(directory, b, 'controller', 'panels', 'source')
        with contextlib.closing(b.connect_state(directory)) as db:
            self.assertEqual(controller_state.ledgers(db), ['wall'])

    def test_removing_the_panels_removes_their_ledger(self):
        self.free()
        request, _ = self.command('panels', {'kind': 'power.set', 'on': False})
        self.assertEqual(enrollment.remove(self.directory, b, 'panels', force=True, wait=0)['cleaned'], True)
        self.assertEqual([snap['identity']['deviceId'] for snap in self.app.devices()], ['wall'])
        stale = dict(request, requestId=dict(request['requestId'], sequence=1), command={'kind': 'mode.set', 'mode': 'Quiet'})
        self.assertEqual(self.app.admit(self.token, stale), (403, {'failure': {'code': 'forbidden'}}))
        self.assertEqual(self.query("SELECT name FROM sqlite_master WHERE name LIKE 'controller%@panels'"), [])
        self.assertEqual(self.query("SELECT key FROM meta WHERE key LIKE '%@panels'"), [])
        self.assertFalse(enrollment.leftovers(self.directory, b, 'panels'))
        self.assertEqual(self.app.snapshot('wall')['identity']['deviceId'], 'wall')

    def test_a_panels_map_edit_advances_only_the_panels_ledger(self):
        before = {device: self.app.snapshot(device) for device in ('wall', 'panels')}
        lines_request = self.request('wall', {'kind': 'brightness.set', 'percent': 55})
        wall_server.App(self.directory, b, launch=lambda *_: None).update('/api/settings', {'device': 'panels', 'style': 'project'})
        after = {device: self.app.snapshot(device) for device in ('wall', 'panels')}
        self.assertEqual(after['panels']['configurationRevision'], before['panels']['configurationRevision'] + 1)
        self.assertNotEqual(after['panels']['cursor'], before['panels']['cursor'])
        self.assertEqual((after['wall']['configurationRevision'], after['wall']['cursor']),
                         (before['wall']['configurationRevision'], before['wall']['cursor']))
        self.assertEqual(self.app.admit(self.token, lines_request)[0], 202)

    def test_shared_edits_from_the_panels_page_advance_the_lines_ledger(self):
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO projects (id, name, color, roots) VALUES ('project-a', 'A', '#123456', '[]')")
        before = {device: self.app.snapshot(device)['configurationRevision'] for device in ('wall', 'panels')}
        wall_server.App(self.directory, b, launch=lambda *_: None).update('/api/project', {'device': 'panels', 'id': 'project-a', 'color': '#abcdef'})
        after = {device: self.app.snapshot(device)['configurationRevision'] for device in ('wall', 'panels')}
        self.assertEqual(after, {'wall': before['wall'] + 1, 'panels': before['panels']})

    def test_each_ledger_keeps_its_own_sequence_revision_and_generation(self):
        self.free()
        panels_request, (code, _) = self.command('panels', {'kind': 'brightness.set', 'percent': 42})
        lines_request, _ = self.command('wall', {'kind': 'power.set', 'on': False})
        self.assertEqual(code, 202)
        self.assertEqual((panels_request['requestId']['sequence'], lines_request['requestId']['sequence']), (0, 0))
        self.assertNotEqual(panels_request['requestId']['epoch'], lines_request['requestId']['epoch'])
        before = {device: self.app.snapshot(device) for device in ('wall', 'panels')}
        self.command('panels', {'kind': 'mode.set', 'mode': 'Quiet'})
        after = {device: self.app.snapshot(device) for device in ('wall', 'panels')}
        for key in ('configurationRevision', 'generation', 'nextRequestId'):
            self.assertEqual(after['wall'][key], before['wall'][key])
        self.assertNotEqual(after['panels']['generation'], before['panels']['generation'])
        self.assertEqual(after['panels']['state']['desired']['mode'], {'status': 'known', 'value': 'Quiet'})
        self.assertEqual(after['wall']['state']['desired']['mode'], {'status': 'known', 'value': 'Free'})
        # The Panels mode command superseded only the Panels' queued control.
        self.assertEqual(self.receipt(panels_request)['failure'], {'code': 'stale-generation'})
        self.assertEqual(self.receipt(lines_request)['outcome'], 'queued')

    def test_local_mode_change_cancels_only_that_devices_controls(self):
        self.free()
        panels_request, _ = self.command('panels', {'kind': 'brightness.set', 'percent': 42})
        lines_request, _ = self.command('wall', {'kind': 'brightness.set', 'percent': 55})
        generation = self.app.snapshot('wall')['generation']
        self.mode('work', 'panels')
        self.assertEqual((self.receipt(panels_request)['outcome'], self.receipt(panels_request)['failure']),
                         ('cancelled', {'code': 'stale-generation'}))
        self.assertEqual(self.receipt(lines_request)['outcome'], 'queued')
        self.assertEqual(self.app.snapshot('wall')['generation'], generation)
        self.assertEqual(self.app.snapshot('panels')['state']['desired']['mode']['value'], 'Work')

    def test_revocation_cancels_queued_work_on_every_device(self):
        self.free()
        panels_request, _ = self.command('panels', {'kind': 'power.set', 'on': False})
        lines_request, _ = self.command('wall', {'kind': 'power.set', 'on': False})
        server.revoke(self.directory, b, 'client')
        for request in (panels_request, lines_request):
            self.assertEqual(self.receipt(request)['failure'], {'code': 'forbidden'})
        holds = dict(self.query("SELECT key, value FROM meta WHERE key LIKE 'controller_hold_revision%'"))
        self.assertEqual(set(holds), {'controller_hold_revision', 'controller_hold_revision@panels'})


class WorkerOwnershipTest(PanelsControllerTest):
    def test_a_command_runs_only_on_its_own_devices_worker(self):
        self.free()
        panels_request, _ = self.command('panels', {'kind': 'brightness.set', 'percent': 42})
        lines_request, _ = self.command('wall', {'kind': 'power.set', 'on': False})
        self.run_worker('panels')
        self.assertEqual(puts(self.fake.panels), [('/state', {'brightness': {'value': 42, 'duration': 0}})])
        self.assertEqual(puts(self.fake.lines), [])
        self.assertEqual((self.receipt(panels_request)['outcome'], self.receipt(lines_request)['outcome']), ('sent', 'queued'))
        self.run_worker('wall')
        self.assertEqual(puts(self.fake.lines), [('/state', {'on': {'value': False}})])
        self.assertEqual(len(puts(self.fake.panels)), 1)
        self.assertEqual(self.receipt(lines_request)['outcome'], 'sent')
        self.assertEqual(self.app.snapshot('panels')['state']['lastSuccessfulSend']['requestId'], panels_request['requestId'])
        self.assertEqual(self.app.snapshot('wall')['state']['lastSuccessfulSend']['requestId'], lines_request['requestId'])

    def test_commands_admitted_mid_pass_stay_with_their_own_device(self):
        self.free()
        admitted = []
        def admit_during_pass():
            # The pass reads unread evidence outside its transaction, so admissions can land here.
            if not admitted:
                admitted.append(self.command('wall', {'kind': 'brightness.set', 'percent': 55})[0])
                admitted.append(self.command('panels', {'kind': 'power.set', 'on': False})[0])
            return self.unread
        self.run_worker('panels', read_unread=admit_during_pass)
        lines_request, panels_request = admitted
        self.assertEqual(puts(self.fake.panels), [('/state', {'on': {'value': False}})])
        self.assertEqual(puts(self.fake.lines), [])
        self.assertEqual((self.receipt(panels_request)['outcome'], self.receipt(lines_request)['outcome']), ('sent', 'queued'))

    def test_panels_override_governs_only_the_panels(self):
        self.event('UserPromptSubmit')
        self.command('panels', {'kind': 'brightness.set', 'percent': 60})
        self.assertEqual(self.app.snapshot('panels')['state']['desired']['brightness'], {'status': 'known', 'value': 60})
        self.assertEqual(self.app.snapshot('wall')['state']['desired']['brightness'], {'status': 'unknown'})
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.run_worker('wall', self.free_after(3, 'wall'))
        levels = lambda fake: [payload['brightness']['value'] for endpoint, payload in puts(fake)
                               if endpoint == '/state' and 'brightness' in payload]
        self.assertIn(60, levels(self.fake.panels))
        self.assertIn(30, levels(self.fake.lines))
        self.assertNotIn(60, levels(self.fake.lines))

    def test_panels_mode_command_is_journaled_by_the_panels_worker(self):
        self.free()
        request, (code, _) = self.command('panels', {'kind': 'mode.set', 'mode': 'Quiet'})
        self.assertEqual(code, 202)
        self.run_worker('panels', self.free_after(3, 'panels'))
        receipt = self.receipt(request)
        self.assertEqual(receipt['outcome'], 'sent')
        self.assertTrue(receipt['completedOperations'])
        self.assertTrue(puts(self.fake.panels))
        self.assertEqual(puts(self.fake.lines), [])
        self.assertEqual(self.app.snapshot('panels')['state']['lastSuccessfulSend']['requestId'], request['requestId'])

    def test_uncertain_panels_mode_write_holds_only_the_panels(self):
        self.free()
        request, _ = self.command('panels', {'kind': 'mode.set', 'mode': 'Quiet'})
        self.fake.panels.fail = lambda method, endpoint, payload: method == 'PUT'
        with self.assertRaises(OSError):
            self.run_worker('panels')
        self.assertIn(self.receipt(request)['outcome'], ('uncertain', 'partially-applied'))
        holds = dict(self.query("SELECT key, value FROM meta WHERE key LIKE 'controller_hold_revision%'"))
        self.assertEqual(set(holds), {'controller_hold_revision@panels'})

    def test_revoke_or_disable_that_missed_the_panels_ledger_ends_its_request(self):
        # Older source revokes and disables through the original tables only.
        self.free()
        request, _ = self.command('panels', {'kind': 'power.set', 'on': False})
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("UPDATE controller_credentials SET active=0 WHERE principal='client'")
        self.run_worker('panels')
        self.assertEqual(puts(self.fake.panels), [])
        self.assertEqual((self.receipt(request)['outcome'], self.receipt(request)['failure']), ('cancelled', {'code': 'forbidden'}))
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("UPDATE controller_credentials SET active=1 WHERE principal='client'")
            controller_state.release(db, 'panels')
        request, _ = self.command('panels', {'kind': 'power.set', 'on': False})
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            data = controller_state.read(db); data['stopped'] = True; controller_state.save(db, data)
        self.run_worker('panels')
        self.assertEqual(puts(self.fake.panels), [])
        self.assertEqual(self.receipt(request)['failure'], {'code': 'forbidden'})

    def test_panels_hold_leaves_the_lines_running(self):
        self.free()
        panels_request, _ = self.command('panels', {'kind': 'brightness.set', 'percent': 42})
        self.fake.panels.fail = lambda method, endpoint, payload: method == 'PUT'
        with self.assertRaises(OSError):
            self.run_worker('panels')
        self.assertEqual(self.receipt(panels_request)['outcome'], 'uncertain')
        holds = dict(self.query("SELECT key, value FROM meta WHERE key LIKE 'controller_hold_revision%'"))
        self.assertEqual(set(holds), {'controller_hold_revision@panels'})
        lines_request, (code, _) = self.command('wall', {'kind': 'brightness.set', 'percent': 55})
        self.assertEqual(code, 202)
        self.run_worker('wall')
        self.assertEqual(puts(self.fake.lines), [('/state', {'brightness': {'value': 55, 'duration': 0}})])
        self.assertEqual(self.receipt(lines_request)['outcome'], 'sent')
        # The Panels' automatic retry never sends the uncertain request again.
        self.fake.panels.calls.clear()
        self.run_worker('panels')
        self.assertEqual(puts(self.fake.panels), [])
        # The Lines keep rendering tasks while the Panels are held.
        self.mode('work', 'wall'); self.event('UserPromptSubmit')
        self.fake.lines.calls.clear()
        self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertTrue(self.effects(self.fake.lines))

    def test_lines_hold_leaves_panels_commands_running(self):
        self.free()
        self.command('wall', {'kind': 'brightness.set', 'percent': 55})
        self.fake.lines.fail = lambda method, endpoint, payload: method == 'PUT'
        with self.assertRaises(OSError):
            self.run_worker('wall')
        panels_request, _ = self.command('panels', {'kind': 'power.set', 'on': False})
        self.run_worker('panels')
        self.assertEqual(puts(self.fake.panels), [('/state', {'on': {'value': False}})])
        self.assertEqual(self.receipt(panels_request)['outcome'], 'sent')
        holds = dict(self.query("SELECT key, value FROM meta WHERE key LIKE 'controller_hold_revision%'"))
        self.assertEqual(set(holds), {'controller_hold_revision'})

    def test_each_worker_discovers_only_its_own_scenes(self):
        self.discover()
        lines_ids = self.app.snapshot('wall')['capabilities']['scenes']['sceneIds']
        panels_ids = self.app.snapshot('panels')['capabilities']['scenes']['sceneIds']
        self.assertEqual((len(lines_ids), len(panels_ids)), (2, 2))
        self.assertFalse(set(lines_ids) & set(panels_ids))
        names = lambda device: [scene.get('name') for scene in self.app.integration_snapshot(self.token, device)['scenes']]
        self.assertEqual(names('wall'), ['Beach Waves', 'Cotton Candy'])
        self.assertEqual(names('panels'), ['Forest', 'Sunset'])

    def test_panels_scene_follows_the_panels_mode(self):
        self.discover()
        sunset = self.app.snapshot('panels')['capabilities']['scenes']['sceneIds'][1]
        self.mode('free', 'wall'); self.run_worker('wall')
        self.mode('work', 'panels')
        self.fake.lines.calls.clear(); self.fake.panels.calls.clear()
        rejected, (code, receipt) = self.command('panels', {'kind': 'scene.activate', 'sceneId': sunset})
        self.assertEqual((code, receipt['failure']), (422, {'code': 'unsupported-capability'}))
        self.assertEqual(self.app.admit(self.token, rejected), (200, receipt))  # Retained for replay.
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.assertNotIn(('/effects', {'select': 'Sunset'}), puts(self.fake.panels))
        self.assertEqual(puts(self.fake.lines), [])
        self.run_worker('panels')
        self.fake.panels.calls.clear()
        request, (code, _) = self.command('panels', {'kind': 'scene.activate', 'sceneId': sunset})
        self.assertEqual(code, 202)
        self.run_worker('panels')
        self.assertEqual(puts(self.fake.panels), [('/effects', {'select': 'Sunset'})])
        self.assertEqual(puts(self.fake.lines), [])
        self.assertEqual(self.receipt(request)['outcome'], 'sent')

    def test_panels_instance_still_owns_no_shared_ingestion(self):
        calls = []
        original = integration_api.process
        integration_api.process = lambda *a, **k: calls.append('integration')
        self.addCleanup(setattr, integration_api, 'process', original)
        tick = shared_input.Poller.tick
        shared_input.Poller.tick = lambda poller, instant: calls.append('feed') or False
        self.addCleanup(setattr, shared_input.Poller, 'tick', tick)
        self.event('UserPromptSubmit')
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.assertEqual(calls, [])
        self.assertTrue(self.effects(self.fake.panels))


class IntegrationTest(PanelsControllerTest):
    def extension(self, device, command):
        view = self.app.integration_snapshot(self.token, device)
        return dict(apiVersion=integration_api.VERSION, controllerId='controller', deviceId=device,
                    requestId=view['nextRequestId'], expectedRevision=view['revision'], command=command)

    def test_panels_extension_snapshot_is_read_only(self):
        self.discover()
        before = (self.directory / 'status.sqlite').read_bytes()
        calls = len(self.fake.panels.calls) + len(self.fake.lines.calls)
        lines, panels = (self.app.integration_snapshot(self.token, device) for device in ('wall', 'panels'))
        self.assertEqual(set(panels), set(lines))
        self.assertEqual(panels['identity'], self.app.snapshot('panels')['identity'])
        self.assertEqual(panels['configurationRevision'], self.app.snapshot('panels')['configurationRevision'])
        self.assertEqual((panels['elements'], panels['wallPending'], panels['pending'], panels['outcomes']), ([], None, [], []))
        self.assertEqual(set(panels['capabilities']), set(lines['capabilities']))
        for operation in integration_api.OPERATIONS:
            self.assertEqual(panels['capabilities'][operation], {'supported': False, 'scope': 'control'})
        self.assertEqual(panels['capabilities']['mode.set'], lines['capabilities']['mode.set'])
        self.assertEqual([scene['name'] for scene in panels['scenes']], ['Forest', 'Sunset'])
        self.assertEqual(panels['nextRequestId']['epoch'], self.app.snapshot('panels')['identity']['controllerEpoch'])
        self.assertEqual((self.directory / 'status.sqlite').read_bytes(), before)
        self.assertEqual(len(self.fake.panels.calls) + len(self.fake.lines.calls), calls)

    def test_panels_extension_commands_fail_before_reservation(self):
        self.free()
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO projects (id, name, color, roots) VALUES ('project-a', 'A', '#123456', '[]')")
        project = self.app.integration_snapshot(self.token, 'wall')['projects']
        self.assertTrue(project)
        commands = [{'kind': 'animation.play', 'pattern': 'pulse', 'colors': ['#ff00ff']},
                    {'kind': 'settings.set', 'style': 'project'}]
        if project:
            commands.append({'kind': 'project.color', 'projectId': project[0]['id'], 'color': '#abcdef'})
        for command in commands:
            with self.subTest(kind=command['kind']):
                request = self.extension('panels', command)
                self.assertEqual(self.app.integration_admit(self.token, request), (422, {'failure': {'code': 'unsupported-capability'}}))
                self.assertEqual(self.app.integration_snapshot(self.token, 'panels')['nextRequestId'], request['requestId'])
        self.assertEqual(self.query('SELECT COUNT(*) FROM integration_requests'), [(0,)])
        self.run_worker('panels')
        self.assertEqual(puts(self.fake.panels), [])

    def test_panels_receipt_cancel_and_animations_routes(self):
        ticket = self.app.integration_snapshot(self.token, 'panels')['nextRequestId']
        with self.assertRaises(integration_api.Failure) as raised:
            integration_api.receipt(self.app, self.token, 'panels', ticket)
        self.assertEqual(raised.exception.code, 'request-expired')
        self.assertEqual(self.app.integration_cancel(self.token, 'panels', ticket), (410, {'failure': {'code': 'request-expired'}}))
        with self.assertRaises(integration_api.Failure) as raised:
            self.app.integration_animations(self.token, 'panels')
        self.assertEqual(raised.exception.code, 'unsupported-capability')
        with self.assertRaises(integration_api.Failure) as raised:
            self.app.integration_snapshot(self.token, 'missing')
        self.assertIn(raised.exception.code, ('forbidden', 'unknown-device'))


class HttpTest(PanelsControllerTest):
    def setUp(self):
        super().setUp()
        self.server = server.make_server(self.app)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        def stop():
            self.server.shutdown(); self.server.server_close(); thread.join()
        self.addCleanup(stop)

    def http(self, method, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        self.addCleanup(connection.close)
        headers = {'Authorization': 'Bearer ' + self.token}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_routes_select_the_named_device(self):
        code, listed = self.http('GET', '/controller/v1/devices')
        self.assertEqual(code, 200)
        self.assertEqual([snap['identity']['deviceId'] for snap in listed['devices']], ['wall', 'panels'])
        code, snap = self.http('GET', '/controller/v1/snapshot?deviceId=panels')
        self.assertEqual((code, snap['identity']['deviceId']), (200, 'panels'))
        cursor = snap['cursor']
        code, receipt = self.http('POST', '/controller/v1/commands', self.request('panels', {'kind': 'mode.set', 'mode': 'Quiet'}))
        self.assertEqual((code, receipt['deviceId']), (202, 'panels'))
        code, events = self.http('GET', f"/controller/v1/feed?deviceId=panels&epoch={cursor['epoch']}&sequence={cursor['sequence']}")
        self.assertEqual(code, 200)
        self.assertTrue(events)
        self.assertTrue(all(event['snapshot']['identity']['deviceId'] == 'panels' for event in events))
        code, lines = self.http('GET', '/controller/v1/snapshot?deviceId=wall')
        self.assertEqual(lines['state']['pending'], [])
        self.assertEqual(self.http('GET', '/controller/v1/snapshot?deviceId=missing')[0], 403)
        wrong = dict(self.request('panels', {'kind': 'power.set', 'on': True}), deviceId='missing')
        self.assertEqual(self.http('POST', '/controller/v1/commands', wrong)[0], 403)


class CompatibilityTest(unittest.TestCase):
    # The committed pre-change database carries a single-device ledger with receipts and events.
    # The Lines keep the original tables untouched, so older source can still read and write them.
    ORIGINAL = ('controller_meta', 'controller_requests', 'controller_events', 'controller_credentials')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for name in ('config.json', 'layout.json', 'scene-state.json'):
            shutil.copyfile(FIXTURE / name.replace('.json', '-fixture.json'), self.directory / name)
        config = json.loads((self.directory / 'config.json').read_text())
        config.update(panelsToken='fakePanels', devices={'panels': {'kind': 'panels', 'ip': '192.0.2.2', 'token_ref': 'panelsToken'}})
        b.write_json(self.directory / 'config.json', config)
        with contextlib.closing(sqlite3.connect(self.directory / 'status.sqlite')) as db:
            db.executescript((FIXTURE / 'status.sql').read_text())
            db.execute("INSERT OR REPLACE INTO meta VALUES ('controller_hold_revision', '2')")
            db.commit()
            self.before = self.original(db)
            self.requests = db.execute('SELECT request, receipt FROM controller_requests').fetchall()
        self.token = json.loads((FIXTURE / 'fixture.json').read_text())['controllerToken']

    def original(self, db):
        return {name: (db.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone(),
                       sorted(db.execute('SELECT * FROM ' + name).fetchall(), key=repr)) for name in self.ORIGINAL}

    def test_original_tables_are_unchanged_and_accept_pre_change_writes(self):
        with contextlib.closing(b.connect_state(self.directory)) as db:
            self.assertEqual(self.original(db), self.before)
        identity = json.loads(self.before['controller_meta'][1][0][1])['identity']
        server.configure(self.directory, b, identity['controllerId'], 'panels', identity['sourceId'])
        with contextlib.closing(b.connect_state(self.directory)) as db:
            self.assertEqual(self.original(db), self.before)
            self.assertEqual(controller_state.ledgers(db), ['wall', 'panels'])
            self.assertEqual(db.execute("SELECT value FROM meta WHERE key='controller_hold_revision'").fetchone(), ('2',))
            # The exact positional writes of the pre-change source still succeed on the Lines ledger.
            with db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT OR REPLACE INTO controller_meta VALUES (1,?)', (self.before['controller_meta'][1][0][1],))
                db.execute('INSERT INTO controller_events VALUES (?,?)', (999, '{}'))
                db.execute('INSERT INTO controller_requests VALUES (?,?,?,?,?,?,?)', (999, '{}', '{}', 'codex', 'done', 0.0, 0))
                db.rollback()
        app = server.App(self.directory, b, launch=lambda _: None)
        retained, receipt = (json.loads(value) for value in self.requests[0])
        self.assertEqual(app.admit(self.token, retained), (200, receipt))
        self.assertEqual(app.snapshot()['identity'], identity)
        self.assertEqual(app.snapshot('panels')['identity']['deviceId'], 'panels')

if __name__ == '__main__':
    unittest.main()
