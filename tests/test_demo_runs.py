"""#193: disposable synthetic wall runs for verification.

Each run seeds a named scenario into its own state directory, serves the actual wall server on
127.0.0.1 and drives task transitions through the actual hook handler. The light worker is a
stand-in, and every device path is refused and recorded. These tests prove the refusal with real
attempts, including an unguarded control, rather than by inspecting a screenshot.

#194: a hub-paired run pairs with a stand-in Hub feed served here from
tests/fixtures/paired-hub-feed.json. Its boundary allows connections to that feed's port only;
attempts at an installed service's port run beneath tests/fixtures/backstop_demo.py, so a boundary
regression could not reach one.
"""
import contextlib
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.error
import urllib.request

from test_bridge import b  # noqa: F401  (puts bridge/ on the import path)
import devices

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'scripts/demo.py'
BACKSTOP = ROOT / 'tests/fixtures/backstop_demo.py'
FEED = json.loads((ROOT / 'tests/fixtures/paired-hub-feed.json').read_text())
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
        self.assertEqual(sorted(demo.SCENARIOS), ['empty', 'hub-paired', 'layout-unavailable', 'reference'])
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
        for scenario in ('reference', 'empty', 'layout-unavailable'):
            with self.subTest(scenario=scenario):
                first, second = self.directory(), self.directory()
                for directory in (first, second):
                    demo.seed(directory, scenario, now=lambda: NOW)
                self.assertEqual(dump(first), dump(second))

    def test_seed_marks_the_directory_it_created(self):
        directory = self.directory()
        demo.seed(directory, 'empty', now=lambda: NOW)
        self.assertEqual(json.loads((directory / demo.MARKER).read_text()), {'scenario': 'empty', 'seededBy': 'scripts/demo.py seed'})

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


def command(*arguments, env=None):
    return subprocess.run([sys.executable, str(DEMO), *arguments], capture_output=True, text=True, timeout=30,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **(env or {})), cwd=ROOT)


class StateOwnershipTest(Directories):
    """serve and drive run only over a directory that seed marked, never over the installation's state."""

    def test_serve_and_drive_refuse_a_directory_seed_did_not_mark(self):
        directory = self.directory()
        demo.seed(directory, 'reference', now=lambda: NOW)
        (directory / demo.MARKER).unlink()
        before = dump(directory)
        for arguments in (['serve', '--state-dir', str(directory), '--port', '0'], ['drive', '--state-dir', str(directory), 'complete']):
            with self.subTest(command=arguments[0]):
                result = command(*arguments)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn('Refusing the state directory: it has no demo-run.json from demo.py seed.', result.stderr)
        with self.assertRaisesRegex(ValueError, 'no demo-run.json'):
            demo.drive(directory, 'complete')
        self.assertEqual(dump(directory), before)
        self.assertFalse((directory / 'map-server.json').exists())
        self.assertFalse((directory / demo.BOUNDARY_LOG).exists())

    def test_every_command_refuses_the_installation_state_directory(self):
        # A private HOME stands in for the user's; the real installation is never read or written.
        home = self.directory()
        probe = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, "bridge"); import configuration; print(configuration.data_dir().resolve())'],
                               capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, HOME=str(home)))
        installed = Path(probe.stdout.strip())
        if home not in installed.parents:
            self.skipTest(f'this checkout has its own bridge/config.json, so the installation directory is not under HOME')
        seeded = self.directory()
        demo.seed(seeded, 'reference', now=lambda: NOW)
        installed.mkdir(parents=True)
        for path in seeded.iterdir():
            (installed / path.name).write_bytes(path.read_bytes())
        before = dump(installed)
        nested = installed / 'nested'
        for arguments in (['serve', '--state-dir', str(installed), '--port', '0'], ['drive', '--state-dir', str(installed), 'complete'],
                          ['seed', '--state-dir', str(nested)]):
            with self.subTest(command=arguments[0]):
                if arguments[0] == 'seed':
                    nested.mkdir()
                result = command(*arguments, env={'HOME': str(home)})
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("demo.py: error: Refusing the state directory: it is the installation's own state.", result.stderr)
                self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(dump(installed), before, 'the installation state is unchanged')
        self.assertEqual(sorted(path.name for path in installed.iterdir()), sorted([path.name for path in seeded.iterdir()] + ['nested']))
        self.assertEqual(list(nested.iterdir()), [])


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

    def test_a_stand_in_that_contacts_the_device_still_completes_but_attempts_each_device(self):
        attempts = []

        def record(config, method, endpoint='', payload=None):
            attempts.append((config['ip'], method, endpoint))
            raise demo.DeviceBoundaryError('refused')
        demo.drive(self.run, 'defect-complete-contacts-device', now=lambda: NOW + 5, request=record)
        self.assertEqual(self.status('task-0'), 'unread')
        self.assertEqual(sorted(attempts), [('192.0.2.1', 'PUT', '/effects'), ('192.0.2.2', 'PUT', '/effects')])

    def test_every_transition_is_described_and_an_unknown_one_is_refused(self):
        for name, transition in demo.TRANSITIONS.items():
            with self.subTest(transition=name):
                self.assertTrue(transition['description'])
                self.assertEqual(transition['defect'], name.startswith('defect-'))
        before = dump(self.run)
        with self.assertRaises(ValueError):
            demo.drive(self.run, 'no-such-transition')
        self.assertEqual(dump(self.run), before)

    def test_paired_defects_are_refused_on_a_standalone_run(self):
        before = dump(self.run)
        for name in ('defect-poll-installed-hub', 'defect-paired-light-request'):
            with self.subTest(transition=name), self.assertRaisesRegex(ValueError, 'applies only to a hub-paired run'):
                demo.drive(self.run, name)
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

    def attempt(self, directory, script, guarded=True, before=''):
        source = textwrap.dedent(f'''
            import importlib.util, json, socket, sys
            from pathlib import Path
            spec = importlib.util.spec_from_file_location('demo', {str(DEMO)!r})
            demo = importlib.util.module_from_spec(spec); spec.loader.exec_module(demo)
            directory = Path({str(directory)!r})
        ''') + textwrap.dedent(before) + textwrap.dedent(f'''
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

    # Paths that raise no socket or process audit event: a spawned child, foreign code through ctypes
    # and, where Python has them, subinterpreters. A call through a function resolved before the guard
    # raises an audit event only from Python 3.14; Python 3.12 lets it through, which the development
    # guide states. The demo and bridge never import ctypes, so no such function exists before the guard.
    CALL_AUDITED = sys.version_info >= (3, 14)
    PRE_GUARD = '''
        import ctypes, multiprocessing, struct
        libc = ctypes.CDLL(None)
        foreign_connect = libc.connect
    '''

    def unaudited_attempts(self, port, guarded):
        return f'''
            def sockaddr():
                return struct.pack('=H', socket.AF_INET) + struct.pack('!H', {port}) + socket.inet_aton('127.0.0.1') + bytes(8)
            def through(connect):
                sock = socket.socket()
                try:
                    if connect(sock.fileno(), sockaddr(), 16) != 0: raise OSError('connect failed')
                finally:
                    sock.close()
            def spawned():
                child = multiprocessing.get_context('spawn').Process(target=socket.create_connection, args=(('127.0.0.1', {port}), 5))
                child.start(); child.join(20)
                if child.exitcode != 0: raise OSError(f'child exited {{child.exitcode}}')
            def interpreter():
                from concurrent import interpreters
                created = interpreters.create()
                try:
                    created.exec("import socket; socket.create_connection(('127.0.0.1', {port}), 5).close()")
                finally:
                    created.close()
            if {self.CALL_AUDITED or not guarded!r}: attempt('ctypes-call', lambda: through(foreign_connect))
            attempt('ctypes-lookup', lambda: through(libc['connect']))
            attempt('ctypes-load', lambda: through(ctypes.CDLL(None).connect))
            attempt('spawn', spawned)
            if importlib.util.find_spec('concurrent.interpreters'): attempt('subinterpreter', interpreter)
        '''

    def test_guard_refuses_spawn_foreign_code_and_subinterpreters(self):
        directory = self.directory()
        listener = Listener()
        self.addCleanup(listener.close)
        results, entries = self.attempt(directory, self.unaudited_attempts(listener.port, True), before=self.PRE_GUARD)
        expected = {'ctypes-lookup': 'DeviceBoundaryError/refused', 'ctypes-load': 'DeviceBoundaryError/refused', 'spawn': 'DeviceBoundaryError/refused'}
        kinds = [('ctypes.dlsym', 'connect'), ('ctypes.dlopen', 'this process'), ('process', Path(sys.executable).name)]
        if self.CALL_AUDITED:
            expected['ctypes-call'] = 'DeviceBoundaryError/refused'
            kinds.insert(0, ('ctypes.call_function', 'foreign function'))
        if importlib.util.find_spec('concurrent.interpreters'):
            expected['subinterpreter'] = 'DeviceBoundaryError/refused'
            kinds.append(('subinterpreter', '_interpreters.create'))
        self.assertEqual(results, expected)
        self.assertEqual([(entry['kind'], entry['target']) for entry in entries], kinds)
        self.assertEqual(listener.accepted(), 0, 'nothing reached the stand-in service')

    def test_control_unguarded_spawn_foreign_code_and_subinterpreters_do_reach_the_listener(self):
        directory = self.directory()
        listener = Listener()
        self.addCleanup(listener.close)
        results, entries = self.attempt(directory, self.unaudited_attempts(listener.port, False), guarded=False, before=self.PRE_GUARD)
        self.assertEqual(set(results.values()), {'completed'}, results)
        self.assertEqual(entries, [])
        self.assertEqual(sum(listener.accepted() for _ in range(len(results) + 1)), len(results))

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



def write_credentials(directory, mode=0o600):
    """The orchestrator's two credential files: one 43-character token each, no trailing newline."""
    tokens = {demo.FEED_TOKEN: secrets.token_urlsafe(32), demo.CONTROLLER_TOKEN: secrets.token_urlsafe(32)}
    for name, value in tokens.items():
        (directory / name).write_text(value)
        (directory / name).chmod(mode)
    return tokens


class StandInHub:
    """The paired Hub run's monitor feed: the one route the wall reads, answering only its feed credential and header."""

    def __init__(self, feed_token):
        self.envelope = copy.deepcopy(FEED['envelope'])
        self.status = 200
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.requests.append(self.path)
                ok = (self.path == '/api/monitor/v1/sessions?snapshotVersion=1.2' and self.headers.get('X-Pixoo-Request') == '1'
                      and self.headers.get('Authorization') == 'Bearer ' + feed_token)
                status = outer.status if ok else 401
                body = json.dumps(outer.envelope if status == 200 else {'error': 'rejected'}).encode()
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        # The kernel could hand out an installed service's port while that service is down; the wall refuses one.
        while True:
            self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            if self.server.server_port not in INSTALLED_PORTS:
                break
            self.server.server_close()
        self.port = self.server.server_port
        self.origin = f'http://127.0.0.1:{self.port}/'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(url, credential=None, body=None):
    """One request as the Hub's controller client makes it; returns the status and JSON body."""
    headers = {**({'Authorization': 'Bearer ' + credential} if credential else {}), **({'Content-Type': 'application/json'} if body else {})}
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=headers)
    try:
        with opener().open(request, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        with error:
            return error.code, json.loads(error.read() or b'null')


def until(read, condition, seconds=15):
    deadline = time.monotonic() + seconds
    while True:
        value = read()
        if condition(value) or time.monotonic() > deadline:
            return value
        time.sleep(0.2)


class PairedSeedTest(Directories):
    """A hub-paired seed registers the Hub's controller credential and follows the paired feed, or writes nothing."""

    def setUp(self):
        self.runtime = self.directory()
        self.data = self.runtime / 'data'
        self.data.mkdir()

    def test_the_seed_pairs_the_controller_and_shared_input_and_keeps_no_token(self):
        tokens = write_credentials(self.runtime)
        demo.seed(self.data, 'hub-paired', now=lambda: NOW, hub_feed='http://127.0.0.1:45001/', credentials=self.runtime)
        import controller_state
        with contextlib.closing(sqlite3.connect(self.data / 'status.sqlite')) as db:
            identity = controller_state.read(db)['identity']
            credentials = db.execute('SELECT principal, digest, scopes, active FROM controller_credentials').fetchall()
            source, config = db.execute('SELECT source, config FROM shared_input WHERE id=1').fetchone()
        self.assertEqual({key: identity[key] for key in ('controllerId', 'deviceId', 'sourceId')},
                         {'controllerId': 'wall-controller', 'deviceId': 'wall', 'sourceId': 'wall'})
        self.assertEqual(credentials, [('hub', hashlib.sha256(tokens[demo.CONTROLLER_TOKEN].encode()).hexdigest(), '["read","control"]', 1)])
        self.assertEqual(source, 'shared')
        self.assertEqual(json.loads(config), {
            'version': 1, 'ownerId': 'verify-owner', 'consumerId': 'nanoleaf', 'endpoint': 'http://127.0.0.1:45001/api/monitor/v1',
            'tokenFile': str((self.runtime / demo.FEED_TOKEN).resolve()), 'clearOnNewTurn': True,
            'qualifiedSources': [{'provider': 'codex', 'client': 'cli', 'hostId': 'verify-host', 'sourceId': 'verify-source'}], 'bindings': []})
        self.assertEqual(rows(self.data, 'SELECT COUNT(*) FROM sessions'), [(0,)], 'the Hub owns the tasks')
        self.assertEqual(rows(self.data, "SELECT COUNT(*) FROM projects WHERE id IN ('a','b','c')"), [(0,)], 'the Hub owns the projects')
        self.assertEqual(demo.registered(self.data), ['wall', 'panels'])
        self.assertEqual(json.loads((self.data / demo.MARKER).read_text()),
                         {'scenario': 'hub-paired', 'seededBy': 'scripts/demo.py seed', 'pairedPort': 45001})
        for path in self.data.rglob('*'):
            if path.is_file():
                for value in tokens.values():
                    self.assertNotIn(value.encode(), path.read_bytes(), f'{path.name} holds a credential')

    def test_a_seed_without_usable_credentials_or_hub_origin_writes_nothing(self):
        cases = []
        def missing():
            pass
        def exposed():
            write_credentials(self.runtime, mode=0o640)
        def malformed():
            write_credentials(self.runtime)
            (self.runtime / demo.CONTROLLER_TOKEN).write_text('not-a-token')
        def linked():
            write_credentials(self.runtime)
            (self.runtime / demo.FEED_TOKEN).rename(self.runtime / 'elsewhere')
            (self.runtime / demo.FEED_TOKEN).symlink_to(self.runtime / 'elsewhere')
        for prepare, origin, message in (
                (missing, 'http://127.0.0.1:45001/', 'hub-paired needs a private hub-feed-token file in the run directory.'),
                (exposed, 'http://127.0.0.1:45001/', 'hub-paired needs a private hub-feed-token file in the run directory.'),
                (malformed, 'http://127.0.0.1:45001/', 'hub-paired needs a private hub-controller-token file in the run directory.'),
                (linked, 'http://127.0.0.1:45001/', 'hub-paired needs a private hub-feed-token file in the run directory.'),
                (write_credentials, 'http://127.0.0.1:45001', "hub-feed must be the paired Hub run's origin, http://127.0.0.1:<port>/."),
                (write_credentials, 'http://localhost:45001/', "hub-feed must be the paired Hub run's origin, http://127.0.0.1:<port>/."),
                (write_credentials, 'http://127.0.0.1:99999/', "hub-feed must be the paired Hub run's origin, http://127.0.0.1:<port>/."),
                (write_credentials, 'http://127.0.0.1:8788/', "hub-feed names an installed service's port.")):
            with self.subTest(prepare=prepare.__name__, origin=origin):
                for path in self.runtime.iterdir():
                    if path != self.data:
                        path.unlink()
                prepare() if prepare is not write_credentials else write_credentials(self.runtime)
                with self.assertRaises(demo.PairingError) as raised:
                    demo.seed(self.data, 'hub-paired', hub_feed=origin, credentials=self.runtime)
                self.assertEqual(str(raised.exception), message)
                self.assertEqual(list(self.data.iterdir()), [], 'a refused seed writes nothing')
        result = command('seed', '--state-dir', str(self.data), '--scenario', 'hub-paired', '--hub-feed', 'http://127.0.0.1:8788/',
                         '--credentials', str(self.runtime))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.splitlines()[-1], "demo.py: error: hub-feed names an installed service's port.")
        self.assertNotIn(str(self.runtime), result.stderr)
        with self.assertRaises(demo.PairingError):
            demo.seed(self.data, 'reference', hub_feed='http://127.0.0.1:45001/', credentials=self.runtime)
        self.assertEqual(list(self.data.iterdir()), [])


class PairedBoundaryTest(Directories):
    """The paired boundary allows TCP to 127.0.0.1 on the paired port only, and never an installed service's port."""

    def attempt(self, directory, paired_port, script):
        source = textwrap.dedent(f'''
            import importlib.util, json, socket, sys
            from pathlib import Path
            spec = importlib.util.spec_from_file_location('backstop', {str(BACKSTOP)!r})
            sys.argv = [{str(BACKSTOP)!r}, 'scenarios']
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                backstop = importlib.util.module_from_spec(spec); spec.loader.exec_module(backstop)
            demo = backstop.demo
            directory = Path({str(directory)!r})
            boundary = demo.install_boundary(directory / demo.BOUNDARY_LOG, {paired_port!r})
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
        backstop = directory.parent / 'backstop.jsonl'
        self.assertFalse(backstop.exists(), backstop.read_text() if backstop.exists() else '')
        return json.loads(result.stdout.strip().splitlines()[-1]), boundary_entries(directory)

    def test_only_the_paired_port_is_reachable_and_each_connection_is_recorded_as_allowed(self):
        directory = self.directory() / 'data'
        directory.mkdir()
        paired, other = Listener(), Listener()
        self.addCleanup(paired.close)
        self.addCleanup(other.close)
        results, entries = self.attempt(directory, paired.port, f'''
            attempt('paired', lambda: socket.create_connection(('127.0.0.1', {paired.port}), timeout=1).close())
            attempt('other', lambda: socket.create_connection(('127.0.0.1', {other.port}), timeout=1).close())
            attempt('installed', lambda: socket.create_connection(('127.0.0.1', 8788), timeout=1).close())
            def datagram():
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try: sock.sendto(b'x', ('127.0.0.1', {paired.port}))
                finally: sock.close()
            attempt('datagram', datagram)
        ''')
        self.assertEqual(results, {'paired': 'completed', 'other': 'DeviceBoundaryError/refused',
                                   'installed': 'DeviceBoundaryError/refused', 'datagram': 'DeviceBoundaryError/refused'})
        self.assertEqual([(entry['kind'], entry['target'], entry['outcome']) for entry in entries],
                         [('socket.connect', f'127.0.0.1:{paired.port}', 'allowed'),
                          ('socket.connect', f'127.0.0.1:{other.port}', 'refused'),
                          ('socket.connect', '127.0.0.1:8788', 'refused'),
                          ('socket.sendto', f'127.0.0.1:{paired.port}', 'refused')])
        self.assertEqual((paired.accepted(), other.accepted()), (1, 0))

    def test_an_installed_port_is_never_allowed_even_when_named_as_paired(self):
        directory = self.directory() / 'data'
        directory.mkdir()
        self.assertIsNone(demo.Boundary(directory / demo.BOUNDARY_LOG, 8788).paired)
        results, entries = self.attempt(directory, 8788, '''
            attempt('installed', lambda: socket.create_connection(('127.0.0.1', 8788), timeout=1).close())
        ''')
        self.assertEqual(results, {'installed': 'DeviceBoundaryError/refused'})
        self.assertEqual([(entry['target'], entry['outcome']) for entry in entries], [('127.0.0.1:8788', 'refused')])


class PairedRun:
    """`demo.py serve` of a hub-paired run beneath the test backstop, with its controller listener."""

    def __init__(self, directory, port=0, controller_port=0):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(directory.parent))
        self.directory = directory
        self.process = subprocess.Popen([sys.executable, '-u', str(BACKSTOP), 'serve', '--state-dir', str(directory), '--port', str(port),
                                         '--controller-port', str(controller_port)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment, cwd=ROOT)
        self.ready = json.loads(self.process.stdout.readline())
        self.url = self.ready['url']
        self.port = int(self.url.rsplit(':', 1)[1])
        self.controller = self.ready['endpoints']['controller']

    def state(self, path='/verify/state'):
        return call(self.url + path)[1]

    def stop(self):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
        output, errors = self.process.communicate(timeout=10)
        return self.process.returncode, output, errors


class PairedServeTest(Directories):
    def pair(self, hub=None, tokens=None):
        self.runtime = self.directory()
        self.data = self.runtime / 'data'
        self.data.mkdir()
        self.tokens = tokens or write_credentials(self.runtime)
        if tokens:
            for name, value in tokens.items():
                (self.runtime / name).write_text(value)
                (self.runtime / name).chmod(0o600)
        self.hub = hub or StandInHub(self.tokens[demo.FEED_TOKEN])
        if not hub:
            self.addCleanup(self.hub.close)
        demo.seed(self.data, 'hub-paired', hub_feed=self.hub.origin, credentials=self.runtime)

    def serve(self, **ports):
        run = PairedRun(self.data, **ports)
        self.addCleanup(lambda: run.process.poll() is None and run.stop())
        return run

    def test_a_paired_run_paints_the_hub_feed_and_serves_the_hub_its_controller_api(self):
        self.pair()
        run = self.serve()
        self.assertEqual(json.loads((self.data / 'map-server.json').read_text())['boundary'], 'paired')
        state = until(run.state, lambda value: value['feed']['connection'] == 'current')
        self.assertEqual({key: state['feed'][key] for key in ('source', 'connection', 'revision', 'ownerId', 'error')},
                         {'source': 'shared', 'connection': 'current', 'revision': 7, 'ownerId': 'verify-owner', 'error': None})
        tasks = run.state('/api/state')['tasks']
        key = lambda session: 'shared-' + hashlib.sha256(json.dumps([session[k] for k in ('provider', 'client', 'hostId', 'sourceId', 'sessionId')],
                                                                    separators=(',', ':')).encode()).hexdigest()
        names = {key(session['identity']): session['identity']['sessionId'] for session in FEED['envelope']['snapshot']['sessions']}
        self.assertEqual({names[task['id']]: [task['status'], task['title']] for task in tasks}, FEED['expected'])
        self.assertTrue(all(task['line'] and task['statusEvidence'] == 'current' for task in tasks))
        # The Hub's calls, with its credential and without.
        self.assertEqual(call(run.controller + 'controller/v1/devices')[0], 401)
        status, devices = call(run.controller + 'controller/v1/devices', self.tokens[demo.CONTROLLER_TOKEN])
        self.assertEqual((status, [d['identity']['controllerId'] for d in devices['devices']]), (200, ['wall-controller']))
        status, snapshot = call(run.controller + 'controller/integration/v1/snapshot?deviceId=wall', self.tokens[demo.CONTROLLER_TOKEN])
        self.assertEqual(status, 200)
        command_body = {'apiVersion': snapshot['apiVersion'], 'controllerId': 'wall-controller', 'deviceId': 'wall',
                        'requestId': snapshot['nextRequestId'], 'expectedRevision': snapshot['revision'],
                        'command': {'kind': 'settings.set', 'style': 'project'}}
        self.assertEqual(call(run.controller + 'controller/integration/v1/commands', self.tokens[demo.CONTROLLER_TOKEN], command_body)[0], 202)
        state = until(run.state, lambda value: value['integration']['applied'] == 1)
        self.assertEqual(state['integration'], {'applied': 1, 'queued': 0, 'failed': 0})
        self.assertEqual(run.state('/api/state')['settings']['style'], 'project')
        code, output, errors = run.stop()
        self.assertEqual(code, 0, errors)
        entries = boundary_entries(self.data)
        self.assertTrue(entries)
        self.assertEqual({(entry['kind'], entry['target'], entry['outcome']) for entry in entries},
                         {('socket.connect', f'127.0.0.1:{self.hub.port}', 'allowed')})
        self.assertTrue(all(request == '/api/monitor/v1/sessions?snapshotVersion=1.2' for request in self.hub.requests))
        for value in self.tokens.values():
            self.assertNotIn(value, output + errors)
        self.assertFalse((self.runtime / 'backstop.jsonl').exists())

    def test_a_hub_that_rejects_the_feed_credential_leaves_the_wall_serving_until_it_accepts(self):
        self.pair()
        self.hub.status = 401
        run = self.serve()
        state = until(run.state, lambda value: value['feed']['error'] == 'feed-rejected')
        self.assertEqual((state['feed']['connection'], state['feed']['revision']), ('unavailable', None))
        self.assertEqual(run.state('/api/state')['tasks'], [])
        self.hub.status = 200
        state = until(run.state, lambda value: value['feed']['connection'] == 'current')
        self.assertEqual(state['feed']['revision'], 7)
        self.assertEqual(len(run.state('/api/state')['tasks']), 5)

    def test_a_relaunch_keeps_the_controller_port_and_a_standalone_scenario_accepts_no_hub_credential(self):
        self.pair()
        run = self.serve()
        controller = int(run.controller.rsplit(':', 1)[1].rstrip('/'))
        self.assertEqual(run.stop()[0], 0)
        for path in self.data.iterdir():
            path.unlink()
        demo.seed(self.data, 'reference')
        standalone = self.serve(port=run.port, controller_port=controller)
        self.assertEqual((standalone.port, standalone.controller), (run.port, f'http://127.0.0.1:{controller}/'))
        self.assertEqual(call(standalone.controller + 'controller/v1/devices', self.tokens[demo.CONTROLLER_TOKEN])[0], 401)
        self.assertEqual(standalone.state()['feed']['source'], 'legacy')
        self.assertEqual(standalone.stop()[0], 0)
        self.assertEqual(boundary_entries(self.data), [], 'a standalone scenario still contacts nothing')

    def test_a_controller_port_in_use_fails_the_start_with_a_named_cause(self):
        self.pair()
        taken = Listener()
        self.addCleanup(taken.close)
        process = subprocess.run([sys.executable, '-u', str(DEMO), 'serve', '--state-dir', str(self.data), '--port', '0',
                                  '--controller-port', str(taken.port)], capture_output=True, text=True, timeout=30, cwd=ROOT,
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertNotEqual(process.returncode, 0)
        self.assertRegex(process.stderr.splitlines()[-1], r'^controller_server\.ListenerUnavailable: Port \d+ is already in use\.')


class PairedDriveTest(Directories):
    def setUp(self):
        self.runtime = self.directory()
        self.data = self.runtime / 'data'
        self.data.mkdir()
        write_credentials(self.runtime)
        demo.seed(self.data, 'hub-paired', hub_feed='http://127.0.0.1:45001/', credentials=self.runtime)

    def drive(self, transition):
        return subprocess.run([sys.executable, str(BACKSTOP), 'drive', '--state-dir', str(self.data), transition],
                              capture_output=True, text=True, timeout=30, cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))

    def test_hook_transitions_are_refused_because_the_hub_owns_task_state(self):
        before = dump(self.data)
        with self.assertRaisesRegex(ValueError, 'The Hub owns task state in hub-paired'):
            demo.drive(self.data, 'complete')
        self.assertEqual(dump(self.data), before)

    def test_polling_the_installed_hub_is_refused_and_recorded_before_any_byte_is_sent(self):
        result = self.drive('defect-poll-installed-hub')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'transition': 'defect-poll-installed-hub', 'tasks': {}})
        self.assertEqual([(entry['kind'], entry['target'], entry['outcome']) for entry in boundary_entries(self.data)],
                         [('socket.connect', '127.0.0.1:8788', 'refused')])
        self.assertFalse((self.runtime / 'backstop.jsonl').exists(), 'the boundary, not the backstop, refused it')

    def test_a_paired_writer_that_sends_the_effect_is_refused_for_each_device(self):
        result = self.drive('defect-paired-light-request')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted((entry['kind'], entry['method'], entry['endpoint'], entry['target'], entry['outcome'])
                                for entry in boundary_entries(self.data)),
                         [('light-request', 'PUT', '/effects', '192.0.2.1', 'refused'), ('light-request', 'PUT', '/effects', '192.0.2.2', 'refused')])


if __name__ == '__main__':
    unittest.main()
