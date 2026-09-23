"""Enroll and remove NL22 Light Panels on an existing Linux Lines installation (#45)."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from test_bridge import b, Clock
from test_scene_restore import Device
import controller_server as server
import devices
import enrollment

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / 'tests/fixtures/nl22-panels-fixture.json').read_text())['panelLayout']
LINES_IP, PANELS_IP, OTHER_IP = '192.0.2.1', '192.0.2.2', '192.0.2.3'
LINES_TOKEN, PANELS_TOKEN = 'fakeLines', 'fakePanelsCredential1'


class FakeDevices:
    """Fake Lines and NL22 controllers addressed by their configured address."""
    def __init__(self, clock):
        self.lines, self.panels = Device(clock), Device(clock)
        self.info = {PANELS_IP: {'name': 'Light Panels', 'model': 'NL22', 'firmwareVersion': '5.2.2',
                                 'panelLayout': copy.deepcopy(FIXTURE)},
                     LINES_IP: {'name': 'Lines', 'model': 'NL59', 'firmwareVersion': '9.0.0'}}
        self.unreachable = set()
        self.seen = []

    def request(self, config, method, endpoint='', payload=None):
        self.seen.append((config['ip'], config.get('token'), method, endpoint))
        if config['ip'] in self.unreachable:
            raise OSError('Device unavailable')
        if method == 'GET' and endpoint == '':
            return copy.deepcopy(self.info[config['ip']])
        target = {LINES_IP: self.lines, PANELS_IP: self.panels}[config['ip']]
        return target.request(config, method, endpoint, payload)


class EnrollmentTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / 'state'
        self.directory.mkdir(mode=0o700)
        self.hooks = Path(temporary.name) / 'hooks.json'
        self.hooks.write_text(json.dumps({'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'trusted'}]}]}}))
        self.clock = Clock()
        self.fake = FakeDevices(self.clock)
        b.write_json(self.directory / 'config.json', {
            'ip': LINES_IP, 'token': LINES_TOKEN,
            'devices': {'wall': {'kind': 'lines', 'ip': LINES_IP, 'token_ref': 'token'}},
            'wall_port': 8765, 'controller_port': 41231, 'mcp_port': 41230})
        lines = devices.lines_entry([[100 + i * 2, 101 + i * 2] for i in range(15)], [[i * 10, 0] for i in range(15)])
        devices.save_layout(self.directory / 'layout.json', {'wall': lines})
        patcher = patch.object(b, 'light_request', self.fake.request)
        patcher.start()
        self.addCleanup(patcher.stop)
        server.configure(self.directory, b, 'local-controller', 'wall', 'local-source')
        server.issue(self.directory, b, 'codex', ['read', 'control'])
        b.write_json(self.directory / 'mcp-credentials.json', {'principals': [{'id': 'codex'}]})
        self.event('UserPromptSubmit', 'a')
        self.event('UserPromptSubmit', 'b')
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO line_prefs (line_id, project, signature, device) VALUES ('100:101', 'alpha', 1, 'wall')")
        self.mode('quiet')

    def event(self, name, session, turn='1'):
        b.handle_event(self.directory, {'hook_event_name': name, 'session_id': session, 'turn_id': turn},
                       launch=lambda _: None, now=self.clock.now)

    def mode(self, name, device='wall'):
        b.set_mode(self.directory, name, launch=lambda _: None, now=self.clock.now, device=device)

    def query(self, sql, *params):
        with contextlib.closing(b.connect_state(self.directory)) as db:
            return db.execute(sql, params).fetchall()

    def config(self):
        return json.loads((self.directory / 'config.json').read_text())

    def layout(self):
        return json.loads((self.directory / 'layout.json').read_text())

    def snapshot(self):
        """Every file in the state directory and the hooks file, plus the shared rows."""
        files = {path.name: path.read_bytes() for path in sorted(self.directory.iterdir())
                 if path.is_file() and not path.name.endswith(('.sqlite', '-journal', '-wal', '-shm'))}
        with contextlib.closing(b.connect_state(self.directory)) as db:
            tables = [name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            rows = {table: sorted(map(repr, db.execute('SELECT * FROM "' + table + '"'))) for table in tables}
        return files, rows, self.hooks.read_bytes()

    def enroll(self, **options):
        options.setdefault('ip', PANELS_IP)
        options.setdefault('token', PANELS_TOKEN)
        return enrollment.enroll(self.directory, b, **options)

    def run_command(self, *argv, stdin=''):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch('sys.stdin', io.StringIO(stdin)):
            code = enrollment.command([*argv, '--state-dir', str(self.directory)], b)
        return code, out.getvalue(), err.getvalue()


class EnrollTest(EnrollmentTest):
    # AC1: verified registration beside Lines without fresh setup.
    def test_enrolls_panels_beside_lines_without_touching_lines_or_tasks(self):
        files, rows, hooks = self.snapshot()
        summary = self.enroll()
        self.assertEqual(summary['device'], 'panels')
        self.assertEqual(summary['triangles'], 18)
        config = self.config()
        self.assertEqual(config['devices']['panels'], {'kind': 'panels', 'ip': PANELS_IP, 'token_ref': 'token@panels'})
        self.assertEqual(config['token@panels'], PANELS_TOKEN)
        before = json.loads(files['config.json'])
        self.assertEqual({k: v for k, v in config.items() if k not in ('devices', 'token@panels')},
                         {k: v for k, v in before.items() if k != 'devices'})
        self.assertEqual(config['devices']['wall'], before['devices']['wall'])
        layout = self.layout()
        self.assertEqual(layout['devices']['wall'], json.loads(files['layout.json'])['devices']['wall'])
        self.assertEqual(layout['devices']['panels']['kind'], 'panels')
        self.assertEqual(len(layout['devices']['panels']['elements']), 18)
        self.assertEqual(self.snapshot()[2], hooks)
        after = self.snapshot()[1]
        for table in ('sessions', 'activity', 'task_info', 'line_prefs', 'slots', 'comets', 'controller_credentials'):
            self.assertEqual(after[table], rows[table], table)
        self.assertEqual(b.get_status(self.directory)['mode'], 'quiet')
        # Only the verification read reached the new device; Lines was not contacted.
        self.assertEqual([(ip, method, endpoint) for ip, _, method, endpoint in self.fake.seen], [(PANELS_IP, 'GET', '')])

    def test_wrong_model_or_unusable_layout_changes_nothing(self):
        before = self.snapshot()
        self.fake.info[PANELS_IP]['model'] = 'NL59'
        with self.assertRaisesRegex(ValueError, 'NL22'):
            self.enroll()
        self.assertEqual(self.snapshot(), before)
        self.fake.info[PANELS_IP]['model'] = 'NL22'
        self.fake.info[PANELS_IP]['panelLayout']['layout']['positionData'][0]['shapeType'] = 7
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            self.enroll()
        self.assertEqual(self.snapshot(), before)

    def test_unreachable_device_writes_nothing(self):
        before = self.snapshot()
        self.fake.unreachable.add(PANELS_IP)
        with self.assertRaises(OSError):
            self.enroll()
        self.assertEqual(self.snapshot(), before)

    # AC4: conflicts never redirect an identity.
    def test_conflicting_identity_or_address_is_refused(self):
        self.enroll()
        before = self.snapshot()
        for options, reason in ((dict(device='wall'), 'reserved'), (dict(device='bad id'), 'Invalid device'),
                                (dict(device='second', ip=LINES_IP), 'already uses'),
                                (dict(device='second', ip=PANELS_IP), 'already uses'),
                                (dict(ip=OTHER_IP), 'another address'),
                                (dict(ip='8.8.8.8'), 'private IPv4'),
                                (dict(token='has space'), 'letters and numbers')):
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, reason):
                self.enroll(**options)
            self.assertEqual(self.snapshot(), before)

    def test_repeat_enrollment_replaces_only_the_credential(self):
        self.enroll()
        self.mode('quiet', 'panels')
        element = self.layout()['devices']['panels']['elements'][0]['id']
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO line_prefs (line_id, project, signature, device) VALUES (?, 'beta', 0, 'panels')", (element,))
        files, rows, hooks = self.snapshot()
        self.fake.info[PANELS_IP]['panelLayout']['layout']['positionData'].pop()
        summary = self.enroll(token='replacementCredential2')
        self.assertTrue(summary['repeat'])
        config = self.config()
        self.assertEqual(config['token@panels'], 'replacementCredential2')
        before = json.loads(files['config.json'])
        self.assertEqual({k: v for k, v in config.items() if k != 'token@panels'},
                         {k: v for k, v in before.items() if k != 'token@panels'})
        self.assertEqual(self.snapshot()[1], rows)
        self.assertEqual(self.snapshot()[0]['layout.json'], files['layout.json'])
        self.assertEqual(b.get_status(self.directory, 'panels')['mode'], 'quiet')

    def test_machine_credentials_are_unchanged(self):
        credentials = (self.directory / 'mcp-credentials.json').read_bytes()
        records = self.query('SELECT * FROM controller_credentials')
        self.enroll()
        self.assertEqual((self.directory / 'mcp-credentials.json').read_bytes(), credentials)
        self.assertEqual(self.query('SELECT * FROM controller_credentials'), records)

    def test_saved_geometry_loads_while_the_device_is_unreachable(self):
        self.enroll()
        self.fake.unreachable.add(PANELS_IP)
        config = b.load_config(self.directory, 'panels')
        self.assertEqual(len(config['elements']), 18)
        self.assertEqual(config['token'], PANELS_TOKEN)


class PrivacyTest(EnrollmentTest):
    # AC2: private storage, no credential in output or browser responses.
    def test_files_are_owner_only_and_output_never_contains_the_credential(self):
        token = self.directory.parent / 'panels-token'
        token.write_text(PANELS_TOKEN + '\n')
        code, out, err = self.run_command('device-enroll', '--ip', PANELS_IP, '--token-file', str(token))
        self.assertEqual(code, 0, err)
        self.assertNotIn(PANELS_TOKEN, out + err)
        for name in ('config.json', 'layout.json'):
            self.assertEqual(stat.S_IMODE((self.directory / name).stat().st_mode), 0o600, name)
        import wall_server
        app = wall_server.App(self.directory, b, launch=lambda *_: None)
        self.assertNotIn(PANELS_TOKEN, json.dumps(app.state()))
        self.fake.info[OTHER_IP] = {'name': 'Canvas', 'model': 'NL29'}
        code, out, err = self.run_command('device-enroll', '--device', 'other', '--ip', OTHER_IP, '--token-file', str(token))
        self.assertEqual(code, 1)
        self.assertNotIn(PANELS_TOKEN, out + err)

    def test_http_failure_reports_only_the_status(self):
        def refuse(config, method, endpoint='', payload=None):
            raise urllib.error.HTTPError(f'http://{config["ip"]}:16021/api/v1/{config["token"]}/', 401, 'Unauthorized', {}, None)
        with patch.object(b, 'light_request', refuse), patch('getpass.getpass', return_value=PANELS_TOKEN):
            code, out, err = self.run_command('device-enroll', '--ip', PANELS_IP)
        self.assertEqual(code, 1)
        self.assertIn('401', err)
        self.assertNotIn(PANELS_TOKEN, out + err)
        self.assertNotIn('panels', self.config()['devices'])

    def test_hidden_prompt_supplies_the_credential(self):
        with patch('getpass.getpass', return_value=PANELS_TOKEN) as prompt:
            code, out, err = self.run_command('device-enroll', '--ip', PANELS_IP)
        self.assertEqual(code, 0, err)
        prompt.assert_called_once()
        self.assertEqual(self.config()['token@panels'], PANELS_TOKEN)

    def test_pairing_obtains_the_credential_from_the_device(self):
        calls = []
        def pair(ip):
            calls.append(ip)
            return PANELS_TOKEN
        with patch.object(enrollment, 'pair', pair):
            code, out, err = self.run_command('device-enroll', '--ip', PANELS_IP, '--pair', stdin='\n')
        self.assertEqual(code, 0, err)
        self.assertEqual(calls, [PANELS_IP])
        self.assertIn('power button', out)
        self.assertNotIn(PANELS_TOKEN, out + err)
        self.assertEqual(self.config()['token@panels'], PANELS_TOKEN)

    def test_pair_posts_to_the_new_endpoint_without_a_proxy(self):
        requests = []
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *_): return False
        class Opener:
            def open(self, request, timeout):
                requests.append((request.full_url, request.get_method(), timeout))
                return Response(json.dumps({'auth_token': PANELS_TOKEN}).encode())
        with patch('urllib.request.build_opener', return_value=Opener()) as build:
            self.assertEqual(enrollment.pair(PANELS_IP), PANELS_TOKEN)
        self.assertEqual(requests, [(f'http://{PANELS_IP}:16021/api/v1/new', 'POST', 5)])
        self.assertEqual(build.call_args.args[0].proxies, {})
        class Closed:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 403, 'Forbidden', {}, None)
        with patch('urllib.request.build_opener', return_value=Closed()):
            with self.assertRaisesRegex(ValueError, 'pairing'):
                enrollment.pair(PANELS_IP)
        with self.assertRaisesRegex(ValueError, 'private IPv4'):
            enrollment.pair('8.8.8.8')

    def test_windows_mounted_state_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Windows'):
            enrollment.enroll(Path('/mnt/c/Users/fixture/CodexNanoleaf'), b, ip=PANELS_IP, token=PANELS_TOKEN)
        with self.assertRaisesRegex(ValueError, 'Windows'):
            enrollment.remove(Path('/mnt/c/Users/fixture/CodexNanoleaf'), b, 'panels')

    def test_installer_reads_its_token_file_through_the_shared_reader(self):
        import install_linux
        self.assertIs(install_linux.read_token, enrollment.read_token)


class FreeStartTest(EnrollmentTest):
    # AC3: dark until activated; activation replays nothing.
    def run_panels_worker(self):
        deadline = self.clock.now() + 25
        def advance(seconds):
            self.clock.sleep(seconds)
            self.assertLess(self.clock.now(), deadline, 'Worker did not release control')
        return b.run_worker(self.directory, sleep=advance, now=self.clock.now, read_unread=lambda: set(),
                            device='panels')

    def test_enrolled_device_stays_dark_until_activated(self):
        self.enroll()
        self.fake.seen.clear()
        self.run_panels_worker()
        self.assertEqual(self.fake.seen, [])
        self.assertEqual(b.get_status(self.directory, 'panels'), {'mode': 'free', 'pending': False, 'error': None})
        empty = self.directory.parent / 'empty-token'
        empty.write_text('')
        code, out, err = self.run_command('device-enroll', '--ip', PANELS_IP, '--token-file', str(empty))
        self.assertEqual(code, 1)  # An empty credential is refused before any request.
        self.assertEqual(self.fake.seen, [])

    def test_activation_replays_no_comet_or_wave(self):
        self.mode('work')
        self.event('Stop', 'a')
        self.assertEqual(self.query("SELECT session FROM comets WHERE device='wall'"), [('a',)])
        self.enroll()
        self.clock.sleep(30)
        self.mode('work', 'panels')
        self.assertEqual(self.query("SELECT session FROM comets WHERE device='panels'"), [])
        self.assertEqual(self.query("SELECT value FROM meta WHERE key='wave_cutoff@panels'"), [(str(self.clock.now()),)])
        self.assertEqual(self.query("SELECT session FROM comets WHERE device='wall'"), [('a',)])
        self.assertEqual(b.get_status(self.directory)['mode'], 'work')

    def test_output_names_activation_and_needs_no_restart(self):
        token = self.directory.parent / 'panels-token'
        token.write_text(PANELS_TOKEN)
        code, out, err = self.run_command('device-enroll', '--ip', PANELS_IP, '--token-file', str(token))
        self.assertEqual(code, 0, err)
        self.assertIn('mode work --device panels', out)
        self.assertIn('No service restart is needed', out)
        self.assertEqual({k: self.config()[k] for k in ('wall_port', 'controller_port', 'mcp_port')},
                         {'wall_port': 8765, 'controller_port': 41231, 'mcp_port': 41230})

    def test_stale_state_for_a_new_id_is_cleared_before_registration(self):
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            for key, value in (('mode@panels', 'work'), ('mode_revision@panels', '4'), ('control_error@panels', 'old')):
                db.execute('INSERT INTO meta VALUES (?, ?)', (key, value))
            db.execute("INSERT INTO comets (session, turn, queued, device) VALUES ('a', '1', 1, 'panels')")
        (self.directory / devices.scene_file('panels')).write_text('{}')
        self.enroll()
        self.assertEqual(b.get_status(self.directory, 'panels'), {'mode': 'free', 'pending': False, 'error': None})
        self.assertEqual(self.query("SELECT * FROM comets WHERE device='panels'"), [])
        self.assertFalse((self.directory / devices.scene_file('panels')).exists())

    def test_new_id_with_a_running_worker_is_refused(self):
        with contextlib.closing(sqlite3.connect(self.directory / devices.lock_file('panels'), timeout=0)) as lock:
            lock.execute('BEGIN EXCLUSIVE')
            with self.assertRaisesRegex(ValueError, 'worker'):
                self.enroll()
        self.assertNotIn('panels', self.config()['devices'])


class RemoveTest(EnrollmentTest):
    # AC4 and AC6: explicit removal leaves Lines and tasks alone.
    def setUp(self):
        super().setUp()
        self.enroll()

    def lines_state(self):
        rows = self.snapshot()[1]
        return ({table: [row for row in values if "'panels'" not in row] for table, values in rows.items() if table != 'meta'},
                self.config()['devices']['wall'], self.layout()['devices']['wall'], b.get_status(self.directory))

    def test_removes_a_free_device_and_everything_it_owned(self):
        self.mode('work', 'panels')
        element = self.layout()['devices']['panels']['elements'][0]['id']
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO line_prefs (line_id, project, device) VALUES (?, 'beta', 'panels')", (element,))
            db.execute("INSERT INTO meta VALUES ('mode_applied@panels', '1')")
        (self.directory / devices.scene_file('panels')).write_text('{}')
        self.mode('free', 'panels')
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('mode_applied@panels', '2')")
        before = self.lines_state()
        result = enrollment.remove(self.directory, b, 'panels')
        self.assertTrue(result['cleaned'])
        config = self.config()
        self.assertNotIn('panels', config['devices'])
        self.assertNotIn('token@panels', config)
        self.assertNotIn('panels', self.layout()['devices'])
        self.assertFalse((self.directory / devices.scene_file('panels')).exists())
        rows = self.snapshot()[1]
        self.assertFalse([row for values in rows.values() for row in values if "'panels'" in row or '@panels' in row])
        self.assertEqual(self.lines_state(), before)

    def test_refuses_before_the_free_handoff_unless_forced(self):
        self.mode('work', 'panels')
        with self.assertRaisesRegex(ValueError, 'mode free --device panels'):
            enrollment.remove(self.directory, b, 'panels')
        self.mode('free', 'panels')  # Pending: the worker has not applied Free yet.
        with self.assertRaisesRegex(ValueError, 'not been applied'):
            enrollment.remove(self.directory, b, 'panels')
        self.assertIn('panels', self.config()['devices'])
        self.assertTrue(enrollment.remove(self.directory, b, 'panels', force=True)['cleaned'])
        self.assertNotIn('panels', self.config()['devices'])

    def test_lines_and_unknown_ids_cannot_be_removed(self):
        before = self.snapshot()
        for device in ('wall', 'missing'):
            with self.subTest(device=device), self.assertRaises(ValueError):
                enrollment.remove(self.directory, b, device)
        self.assertEqual(self.snapshot(), before)

    def test_busy_worker_leaves_cleanup_for_a_rerun(self):
        with contextlib.closing(sqlite3.connect(self.directory / devices.lock_file('panels'), timeout=0)) as lock:
            lock.execute('BEGIN EXCLUSIVE')
            result = enrollment.remove(self.directory, b, 'panels', wait=0.2)
        self.assertFalse(result['cleaned'])
        self.assertNotIn('panels', self.config()['devices'])
        self.assertIn('panels', self.layout()['devices'])
        self.assertTrue(self.query("SELECT 1 FROM meta WHERE key='mode@panels'"))
        self.assertTrue(enrollment.remove(self.directory, b, 'panels')['cleaned'])
        self.assertNotIn('panels', self.layout()['devices'])
        self.assertFalse(self.query("SELECT 1 FROM meta WHERE key LIKE '%@panels'"))
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            enrollment.remove(self.directory, b, 'panels')

    def test_command_reports_removal(self):
        code, out, err = self.run_command('device-remove', '--device', 'panels')
        self.assertEqual(code, 0, err)
        self.assertIn('Removed', out)
        code, out, err = self.run_command('device-remove', '--device', 'wall')
        self.assertEqual(code, 1)



class DispatchTest(EnrollmentTest):
    def test_bridge_hands_device_commands_to_enrollment_with_their_exit_code(self):
        import sys
        argv = ['device-remove', '--device', 'panels', '--state-dir', str(self.directory)]
        with patch.object(sys, 'argv', ['bridge.py', *argv]), patch.object(enrollment, 'command', return_value=1) as command:
            with self.assertRaises(SystemExit) as exit:
                b.main()
        self.assertEqual(exit.exception.code, 1)
        self.assertEqual(command.call_args.args[0], argv)

if __name__ == '__main__':
    unittest.main()
