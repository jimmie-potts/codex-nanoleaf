"""#193: disposable synthetic wall runs for verification.

Each run seeds a named scenario into its own state directory, serves the actual wall server on
127.0.0.1 and drives task transitions through the actual hook handler. The light worker is a
stand-in, and every device path is refused and recorded. These tests prove the refusal with real
attempts, including an unguarded control, rather than by inspecting a screenshot.
"""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
import urllib.error
import urllib.request

from test_bridge import b  # noqa: F401  (puts bridge/ on the import path)
import devices

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'scripts/demo.py'
spec = importlib.util.spec_from_file_location('demo', DEMO)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
NOW = 50000.0
INSTALLED_PORTS = {8788, 8765, 8787, 8791, 41230, 41231}


def dump(directory):
    """Every table's rows, for comparing whole states."""
    with contextlib.closing(sqlite3.connect(directory / 'status.sqlite')) as db:
        tables = [name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {table: sorted(map(repr, db.execute(f'SELECT * FROM "{table}"'))) for table in tables}


def rows(directory, sql, parameters=()):
    with contextlib.closing(sqlite3.connect(directory / 'status.sqlite')) as db:
        return db.execute(sql, parameters).fetchall()


def boundary_entries(directory):
    log = directory / demo.BOUNDARY_LOG
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


class Directories(unittest.TestCase):
    def directory(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)


class ScenarioTest(Directories):
    def test_scenarios_name_and_describe_each_fixture(self):
        self.assertEqual(sorted(demo.SCENARIOS), ['empty', 'layout-unavailable', 'reference'])
        for name, scenario in demo.SCENARIOS.items():
            with self.subTest(scenario=name):
                self.assertIsInstance(scenario['description'], str)
                self.assertTrue(scenario['description'])

    def test_scenarios_command_lists_names_and_descriptions(self):
        result = subprocess.run([sys.executable, str(DEMO), 'scenarios'], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {name: s['description'] for name, s in demo.SCENARIOS.items()})

    def test_reference_matches_the_browser_fixture_with_the_hook_waits_behind_its_alerts(self):
        directory = self.directory()
        demo.seed(directory, 'reference', now=lambda: NOW)
        statuses = ['working', 'blocked', 'question', 'unread', 'working']
        self.assertEqual(rows(directory, 'SELECT id, status FROM sessions ORDER BY id'),
                         [(f'task-{i}', status) for i, status in enumerate(statuses)])
        # A blocked task waits on a permission and a question task on an asynchronous input,
        # so driven hook events move them exactly as a live task's would.
        self.assertEqual(rows(directory, 'SELECT session, turn, kind, tool FROM waits ORDER BY session'),
                         [('task-1', '1', 'permission', 'shell'), ('task-2', '1', 'async', 'request_user_input_async')])
        for device in ('wall', 'panels'):
            with self.subTest(device=device):
                placed = rows(directory, 'SELECT COUNT(*) FROM slots WHERE device=?', (device,))[0][0]
                self.assertGreaterEqual(placed, 4)
        self.assertEqual(demo.registered(directory), ['wall', 'panels'])

    def test_empty_seeds_both_devices_without_tasks(self):
        directory = self.directory()
        demo.seed(directory, 'empty', now=lambda: NOW)
        self.assertEqual(rows(directory, 'SELECT COUNT(*) FROM sessions'), [(0,)])
        self.assertEqual(demo.registered(directory), ['wall', 'panels'])

    def test_layout_unavailable_keeps_line_positions_but_saves_no_drawing_geometry(self):
        directory = self.directory()
        demo.seed(directory, 'layout-unavailable', now=lambda: NOW)
        saved = devices.layout_devices(json.loads((directory / 'layout.json').read_text()))
        self.assertTrue(all(element['position'] for element in saved['wall']['elements']))
        self.assertNotIn('zone_geometry', saved['wall'])
        self.assertNotIn('connector_geometry', saved['wall'])
        self.assertEqual(saved['panels']['kind'], 'panels')

    def test_seeding_is_deterministic_for_a_fixed_clock(self):
        first, second = self.directory(), self.directory()
        for directory in (first, second):
            demo.seed(directory, 'reference', now=lambda: NOW)
        self.assertEqual(dump(first), dump(second))

    def test_seed_refuses_an_unknown_scenario_or_an_existing_state(self):
        directory = self.directory()
        with self.assertRaises(ValueError):
            demo.seed(directory, 'no-such-scenario')
        self.assertEqual(list(directory.iterdir()), [], 'a refused seed writes nothing')
        demo.seed(directory, 'reference', now=lambda: NOW)
        before = dump(directory)
        with self.assertRaises(ValueError):
            demo.seed(directory, 'empty', now=lambda: NOW)
        self.assertEqual(dump(directory), before)


class DriveTest(Directories):
    def setUp(self):
        self.run = self.directory()
        demo.seed(self.run, 'reference', now=lambda: NOW)

    def status(self, task):
        return rows(self.run, 'SELECT status FROM sessions WHERE id=?', (task,))[0][0]

    def slot(self, task):
        return rows(self.run, "SELECT slot FROM slots WHERE session=? AND device='wall'", (task,))

    def test_complete_marks_the_task_unread_on_its_line_and_queues_each_devices_comet(self):
        before = self.slot('task-0')
        demo.drive(self.run, 'complete', now=lambda: NOW + 5)
        self.assertEqual(self.status('task-0'), 'unread')
        self.assertEqual(self.slot('task-0'), before, 'a completed task keeps its Line')
        self.assertEqual(rows(self.run, "SELECT device FROM comets WHERE session='task-0' ORDER BY device"),
                         [('panels',), ('wall',)])

    def test_approve_clears_the_permission_wait_and_the_red_alert(self):
        demo.drive(self.run, 'approve', now=lambda: NOW + 5)
        self.assertEqual(self.status('task-1'), 'working')
        self.assertEqual(rows(self.run, "SELECT COUNT(*) FROM waits WHERE session='task-1'"), [(0,)])

    def test_request_approval_and_resume_move_their_tasks(self):
        demo.drive(self.run, 'request-approval', now=lambda: NOW + 5)
        demo.drive(self.run, 'resume', now=lambda: NOW + 6)
        self.assertEqual((self.status('task-4'), self.status('task-3')), ('blocked', 'working'))

    def test_defect_transitions_leave_the_reference_expectation_unmet(self):
        demo.drive(self.run, 'defect-approve-other-tool', now=lambda: NOW + 5)
        demo.drive(self.run, 'defect-complete-stale-turn', now=lambda: NOW + 6)
        self.assertEqual((self.status('task-1'), self.status('task-0')), ('blocked', 'working'))

    def test_every_transition_is_described_and_an_unknown_one_is_refused(self):
        for name, transition in demo.TRANSITIONS.items():
            with self.subTest(transition=name):
                self.assertTrue(transition['description'])
                self.assertEqual(transition['defect'], name.startswith('defect-'))
        before = dump(self.run)
        with self.assertRaises(ValueError):
            demo.drive(self.run, 'no-such-transition')
        self.assertEqual(dump(self.run), before)

    def test_drive_command_applies_one_transition_under_the_boundary(self):
        result = subprocess.run([sys.executable, str(DEMO), 'drive', '--state-dir', str(self.run), 'complete'],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'transition': 'complete', 'tasks': {'task-0': 'unread'}})
        self.assertEqual(self.status('task-0'), 'unread')
        self.assertEqual(boundary_entries(self.run), [])


class Listener:
    """A loopback listener standing in for an installed service; it counts accepted connections."""
    def __init__(self):
        self.socket = socket.create_server(('127.0.0.1', 0))
        self.socket.settimeout(0.5)
        self.port = self.socket.getsockname()[1]

    def accepted(self):
        try:
            connection, _ = self.socket.accept()
        except TimeoutError:
            return 0
        connection.close()
        return 1

    def close(self):
        self.socket.close()


class BoundaryTest(Directories):
    """The process guard refuses every device path, including ones that bypass the request seam."""

    def attempt(self, directory, script, guarded=True):
        source = textwrap.dedent(f'''
            import importlib.util, json, socket, sys
            from pathlib import Path
            spec = importlib.util.spec_from_file_location('demo', {str(DEMO)!r})
            demo = importlib.util.module_from_spec(spec); spec.loader.exec_module(demo)
            directory = Path({str(directory)!r})
            boundary = demo.install_boundary(directory / demo.BOUNDARY_LOG) if {guarded!r} else None
            results = {{}}
            def attempt(name, action):
                try:
                    action(); results[name] = 'completed'
                except Exception as error:
                    results[name] = type(error).__name__ + ('/refused' if demo.refused(error) else '')
        ''') + textwrap.dedent(script) + '\nprint(json.dumps(results))\n'
        result = subprocess.run([sys.executable, '-c', source], capture_output=True, text=True, timeout=30,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip().splitlines()[-1]), boundary_entries(directory)

    def test_guard_refuses_light_transport_worker_launch_and_loopback_services(self):
        directory = self.directory()
        demo.seed(directory, 'reference', now=lambda: NOW)
        listener = Listener()
        self.addCleanup(listener.close)
        results, entries = self.attempt(directory, f'''
            import launcher, transport
            attempt('transport', lambda: transport.light_request({{'ip': '192.0.2.1', 'token': 'abc123'}}, 'PUT', '/effects', {{}}))
            attempt('worker', lambda: launcher.launch_worker(directory))
            attempt('service', lambda: socket.create_connection(('127.0.0.1', {listener.port}), timeout=1).close())
        ''')
        self.assertEqual(results, {'transport': 'URLError/refused', 'worker': 'DeviceBoundaryError/refused',
                                   'service': 'DeviceBoundaryError/refused'})
        self.assertEqual([(entry['kind'], entry['target'], entry['outcome']) for entry in entries],
                         [('socket.connect', '192.0.2.1:16021', 'refused'),
                          ('process', Path(sys.executable).name, 'refused'),
                          ('socket.connect', f'127.0.0.1:{listener.port}', 'refused')])
        self.assertEqual(listener.accepted(), 0, 'nothing reached the stand-in service')
        self.assertNotIn('abc123', (directory / demo.BOUNDARY_LOG).read_text(), 'the log never records a token')

    def test_control_an_unguarded_process_does_reach_the_listener(self):
        # Without this control the listener check above could pass by never observing anything.
        directory = self.directory()
        listener = Listener()
        self.addCleanup(listener.close)
        results, entries = self.attempt(directory, f'''
            attempt('service', lambda: socket.create_connection(('127.0.0.1', {listener.port}), timeout=1).close())
        ''', guarded=False)
        self.assertEqual((results, entries), ({'service': 'completed'}, []))
        self.assertEqual(listener.accepted(), 1)

    def test_a_map_geometry_read_that_bypasses_the_request_seam_is_still_refused(self):
        directory = self.directory()
        demo.seed(directory, 'layout-unavailable', now=lambda: NOW)
        results, entries = self.attempt(directory, '''
            import configuration, wall_server
            config = configuration.load_config(directory, request=boundary.light_request)
            results['geometry'] = wall_server.ensure_geometry(directory, config)
        ''')
        self.assertEqual(results, {'geometry': False})
        self.assertEqual([(entry['kind'], entry['target']) for entry in entries], [('socket.connect', '192.0.2.1:16021')])

    def test_the_request_trap_records_the_attempt_without_its_credential(self):
        directory = self.directory()
        results, entries = self.attempt(directory, '''
            attempt('trap', lambda: boundary.light_request({'ip': '192.0.2.2', 'token': 'secret42'}, 'PUT', '/state', {'on': {'value': True}}))
        ''')
        self.assertEqual(results, {'trap': 'DeviceBoundaryError/refused'})
        self.assertEqual([(e['kind'], e['method'], e['endpoint'], e['target'], e['outcome']) for e in entries],
                         [('light-request', 'PUT', '/state', '192.0.2.2', 'refused')])
        self.assertNotIn('secret42', (directory / demo.BOUNDARY_LOG).read_text())


class Run:
    """One served run: `demo.py serve` over a seeded state directory, as the verification unit runs it."""
    def __init__(self, directory, port=0):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(directory.parent))
        self.process = subprocess.Popen([sys.executable, '-u', str(DEMO), 'serve', '--state-dir', str(directory), '--port', str(port)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment, cwd=ROOT)
        self.line = self.process.stdout.readline()
        self.ready = json.loads(self.line)
        self.url = self.ready['url']
        self.port = int(self.url.rsplit(':', 1)[1])

    def get(self, path):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(self.url + path, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def json(self, path):
        status, body = self.get(path)
        return status, json.loads(body)

    def stop(self):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
        output, errors = self.process.communicate(timeout=10)
        return self.process.returncode, self.line + output, errors


class ServeTest(Directories):
    def serve(self, scenario, directory=None, port=0):
        if directory is None:
            directory = self.directory() / 'data'
            directory.mkdir()
            demo.seed(directory, scenario)
        run = Run(directory, port)
        self.addCleanup(lambda: run.process.poll() is None and run.stop())
        return directory, run

    def test_a_served_run_answers_its_map_health_and_state_without_device_attempts(self):
        directory, run = self.serve('reference')
        self.assertRegex(run.url, r'^http://127\.0\.0\.1:\d+$')
        self.assertNotIn(run.port, INSTALLED_PORTS | {0})
        # The installed map's own receipt names this process, so a probe can tell it from any other listener.
        receipt = json.loads((directory / 'map-server.json').read_text())
        self.assertEqual(receipt, {'port': run.port, 'instance': run.ready['instance'], 'boundary': 'refusing'})
        self.assertEqual(run.json('/health'), (200, {'service': 'codex-nanoleaf-map', 'instance': run.ready['instance']}))
        status, page = run.get('/')
        self.assertEqual(status, 200)
        self.assertIn('<title>Nanoleaf · Wall map</title>', page.decode())
        status, state = run.json('/api/state')
        self.assertEqual((status, len(state['lines']), len(state['tasks']), [d['id'] for d in state['devices']]),
                         (200, 15, 5, ['wall', 'panels']))
        self.assertIsNone(state['geometry_error'])
        self.assertEqual(run.json('/api/state?device=panels')[1]['kind'], 'panels')
        code, output, errors = run.stop()
        self.assertEqual(code, 0, errors)
        self.assertEqual(boundary_entries(directory), [], 'no device path was attempted')
        token = page.decode().split("const token='", 1)[1].split("'", 1)[0]
        self.assertEqual(len(token), 64)
        self.assertNotIn(token, output + errors, 'the page token is never printed')
        self.assertNotIn(token, (directory / 'map-server.json').read_text())
        self.assertTrue((directory / 'status.sqlite').exists(), 'the caller owns the state directory')

    def test_a_run_without_saved_geometry_shows_the_map_error_and_refuses_the_device_read(self):
        directory, run = self.serve('layout-unavailable')
        status, state = run.json('/api/state')
        self.assertEqual(status, 200)
        self.assertEqual(state['geometry_error'], 'Layout unavailable. Check the light connection; the map will retry.')
        self.assertEqual([(e['kind'], e['method'], e['target'], e['outcome']) for e in boundary_entries(directory)],
                         [('light-request', 'GET', '192.0.2.1', 'refused')])
        self.assertIsNone(run.process.poll(), 'the map keeps serving after a refused request')

    def test_a_reseeded_run_relaunches_on_its_recorded_port(self):
        # The shared core reseeds by stopping the application, emptying its data directory,
        # seeding and relaunching on the same port.
        directory, run = self.serve('reference')
        port = run.port
        self.assertEqual(run.stop()[0], 0)
        for path in directory.iterdir():
            path.unlink()
        demo.seed(directory, 'empty')
        _, again = self.serve('empty', directory=directory, port=port)
        self.assertEqual(again.port, port)
        self.assertEqual(len(again.json('/api/state')[1]['tasks']), 0)

    def test_two_runs_share_nothing(self):
        first_dir, first = self.serve('reference')
        second_dir, second = self.serve('reference')
        self.assertNotEqual(first.port, second.port)
        before = dump(second_dir)
        demo.drive(first_dir, 'complete')
        statuses = lambda run: {task['id']: task['status'] for task in run.json('/api/state')[1]['tasks']}
        self.assertEqual((statuses(first)['task-0'], statuses(second)['task-0']), ('unread', 'working'))
        self.assertEqual(dump(second_dir), before)

    def test_the_default_demo_still_serves_a_temporary_reference_state(self):
        process = subprocess.Popen([sys.executable, '-u', str(DEMO), '--port', '0'], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, cwd=ROOT,
                                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        try:
            url = json.loads(process.stdout.readline())['url']
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url + '/api/state', timeout=5) as response:
                self.assertEqual(len(json.load(response)['tasks']), 5)
        finally:
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0)


if __name__ == '__main__':
    unittest.main()
