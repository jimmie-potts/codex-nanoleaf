import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from test_bridge import b
import wall_server


class LinuxHookTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux', 'Linux uses the fresh installer')
    def test_legacy_setup_cannot_initialize_linux_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, b.__file__, 'setup', '--state-dir', temporary],
                                    input='', capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('install_linux.py', result.stderr)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_setup_check_uses_selected_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'selected'
            default = Path(temporary) / 'default'
            args = b.argparse.Namespace(state_dir=target, check=True, demo=False, reset=False,
                                        notify=False, refresh=False, comet=False)
            with patch.object(b, 'data_dir', return_value=default), \
                    patch.object(b, 'load_config', return_value={'ip': '192.0.2.1', 'line_groups': []}) as load, \
                    patch.object(b, 'light_request', return_value={}), \
                    patch.object(b, 'SceneRestorer') as scene, \
                    contextlib.redirect_stdout(io.StringIO()):
                scene.return_value.state = {'scene': None}
                b.setup(args)
            load.assert_called_once_with(target)
            self.assertFalse(default.exists())

    def test_hook_honors_explicit_state_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'selected'
            default = Path(temporary) / 'default'
            target.mkdir()
            default.mkdir()
            event = {'hook_event_name': 'UserPromptSubmit', 'session_id': 'linux-task',
                     'turn_id': '1', 'cwd': '/home/example/project'}
            with patch.object(sys, 'argv', ['bridge.py', 'hook', '--state-dir', str(target)]), \
                    patch.object(sys, 'stdin', io.StringIO(json.dumps(event))), \
                    patch.object(b, 'data_dir', return_value=default), \
                    patch.object(b, 'launch_worker') as launch, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                b.main()
            self.assertEqual(json.loads(output.getvalue()), {})
            self.assertTrue((target / 'status.sqlite').exists())
            self.assertFalse((default / 'status.sqlite').exists())
            with contextlib.closing(b.connect_state(target)) as db:
                self.assertEqual(db.execute('SELECT id FROM sessions').fetchall(), [('linux-task',)])
            launch.assert_called_once_with(target)


class MapCommandTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        b.write_json(self.directory / 'config.json', {'ip': '192.0.2.1', 'token': 'fake'})
        b.write_json(self.directory / 'layout.json', {
            'line_groups': [[100, 101]], 'line_positions': [[0, 0]],
            'zone_geometry': {'orientation': 0, 'positionData': [
                {'panelId': 98, 'x': 0, 'y': -5, 'o': 0, 'shapeType': 16},
                {'panelId': 99, 'x': 0, 'y': 15, 'o': 0, 'shapeType': 16},
                {'panelId': 100, 'x': 0, 'y': 0, 'o': 0, 'shapeType': 18},
                {'panelId': 101, 'x': 0, 'y': 10, 'o': 0, 'shapeType': 18}]}})

    def command(self, *args):
        return [sys.executable, b.__file__, *args, '--state-dir', str(self.directory)]

    def start(self, port):
        process = subprocess.Popen(self.command('serve', '--port', str(port)),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def stop():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=5)
        self.addCleanup(stop)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.fail(process.communicate()[1])
            if wall_server.map_url(self.directory):
                return process
            time.sleep(.02)
        self.fail('Foreground map did not become healthy')

    def test_fixed_port_and_url_without_browser(self):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        self.start(port)
        self.assertEqual(wall_server.map_url(self.directory), f'http://127.0.0.1:{port}')
        with patch.object(sys, 'argv', self.command('map', '--no-open')[1:]), \
                patch.dict(sys.modules, {'bridge': b}), \
                patch.object(wall_server.webbrowser, 'open') as browser, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            b.main()
        browser.assert_not_called()
        self.assertEqual(output.getvalue().strip(), f'http://127.0.0.1:{port}')
        duplicate = subprocess.run(self.command('serve', '--port', str(port)),
                                   capture_output=True, text=True, timeout=5)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn('already running', duplicate.stderr)

    def test_occupied_configured_port_fails_without_receipt(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            b.write_json(self.directory / 'config.json', {
                'ip': '192.0.2.1', 'token': 'fake', 'wall_port': port})
            result = subprocess.run(self.command('serve'), capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(port), result.stderr)
        self.assertIn('already in use', result.stderr)
        self.assertFalse((self.directory / 'map-server.json').exists())

    def test_stale_receipt_does_not_accept_another_map_owner(self):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        self.start(port)
        receipt = json.loads((self.directory / 'map-server.json').read_text())
        receipt['instance'] = 'earlier-instance'
        b.write_json(self.directory / 'map-server.json', receipt)
        self.assertIsNone(wall_server.map_url(self.directory, port))

    def test_controller_conflicts_report_the_port_and_existing_owner(self):
        configure = subprocess.run(self.command('controller-configure', '--controller-id', 'local-controller',
                                   '--device-id', 'wall', '--source-id', 'local-source'),
                                   capture_output=True, text=True, timeout=5)
        self.assertEqual(configure.returncode, 0, configure.stderr)
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            result = subprocess.run(self.command('controller-serve', '--port', str(port)),
                                    capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(port), result.stderr)
        self.assertIn('already in use', result.stderr)
        self.assertFalse((self.directory / 'controller-server.json').exists())
        with contextlib.closing(sqlite3.connect(self.directory / 'controller-lock.sqlite')) as lock:
            lock.execute('BEGIN EXCLUSIVE')
            duplicate = subprocess.run(self.command('controller-serve', '--port', str(port)),
                                       capture_output=True, text=True, timeout=5)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn('already running', duplicate.stderr)


@unittest.skipUnless(sys.platform == 'linux', 'Native Linux installation')
class LinuxInstallTest(unittest.TestCase):
    def test_token_input_is_bounded_and_cannot_fall_back_to_echo(self):
        import getpass
        import install_linux
        import warnings
        with tempfile.TemporaryDirectory() as temporary:
            token = Path(temporary) / 'token'
            token.write_text('fixtureToken\n')
            self.assertEqual(install_linux.read_token(token), 'fixtureToken')
            token.write_text('x' * 1025)
            with self.assertRaisesRegex(ValueError, '1024'):
                install_linux.read_token(token)
            fifo = Path(temporary) / 'fifo'
            os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError, 'regular'):
                install_linux.read_token(fifo)
        def no_terminal(*_):
            warnings.warn('echo possible', getpass.GetPassWarning)
            return 'exposedToken'
        with patch.object(getpass, 'getpass', side_effect=no_terminal):
            with self.assertRaisesRegex(ValueError, 'token-file'):
                install_linux.read_token(None)

    def test_fresh_private_state_uses_supplied_device_and_metadata(self):
        import install_linux
        layout = json.loads((Path(b.__file__).parents[1] / 'tests/fixtures/lines-layout.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'state'
            metadata = Path(temporary) / 'desktop.json'
            titles = Path(temporary) / 'titles.jsonl'
            calls = []
            def request(config, method):
                calls.append((dict(config), method))
                return {'panelLayout': layout}
            install_linux.prepare_state(directory, '192.0.2.12', 'fixtureToken',
                                        desktop_state_path=metadata, title_index_path=titles,
                                        request=request)
            self.assertEqual(calls, [({'ip': '192.0.2.12', 'token': 'fixtureToken'}, 'GET')])
            config = b.load_config(directory)
            self.assertEqual(config['ip'], '192.0.2.12')
            self.assertEqual(config['desktop_state_path'], str(metadata))
            self.assertEqual(config['metadata_path'], str(metadata))
            self.assertEqual(config['title_index_path'], str(titles))
            self.assertEqual(config['wall_port'], 8765)
            self.assertEqual(config['controller_port'], 41231)
            self.assertEqual(config['mcp_port'], 41230)
            self.assertEqual(len(config['line_groups']), 15)
            self.assertIsNotNone(b.wall.connector_layout(config))
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
            for name in ('config.json', 'layout.json', 'status.sqlite'):
                self.assertEqual((directory / name).stat().st_mode & 0o777, 0o600)
            self.assertFalse(metadata.exists())
            self.assertFalse(titles.exists())
            self.assertFalse((directory / 'notification-lock.sqlite').exists())

    def test_invalid_or_nonempty_state_does_not_change_files(self):
        import install_linux
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            sentinel = directory / 'unrelated.txt'
            sentinel.write_text('keep')
            with self.assertRaisesRegex(ValueError, 'empty'):
                install_linux.prepare_state(directory, '192.0.2.12', 'fixtureToken')
            self.assertEqual(sentinel.read_text(), 'keep')
            with self.assertRaisesRegex(ValueError, 'Linux filesystem'):
                install_linux.linux_state_directory('/mnt/c/nanoleaf-fixture')
            linked = directory / 'mounted-link'
            linked.symlink_to('/mnt/c/nanoleaf-fixture', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Linux filesystem'):
                install_linux.linux_state_directory(linked)
            for kwargs in ({'wall_port': 0}, {'wall_port': 41231}, {'mcp_port': True}):
                with self.assertRaisesRegex(ValueError, 'distinct loopback ports'):
                    install_linux.prepare_state(directory / 'new', '192.0.2.12', 'fixtureToken', **kwargs)
            self.assertFalse((directory / 'new').exists())

    def test_runtime_launcher_and_hooks_use_same_linux_state(self):
        import install_linux
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'state with spaces'
            layout = json.loads((Path(b.__file__).parents[1] / 'tests/fixtures/lines-layout.json').read_text())
            install_linux.prepare_state(directory, '192.0.2.12', 'fixtureToken',
                                        request=lambda *_: {'panelLayout': layout})
            install_linux.copy_runtime(directory)
            launcher = install_linux.write_launcher(directory, Path(sys.executable))
            hooks_file = Path(temporary) / 'codex/hooks.json'
            hooks_file.parent.mkdir()
            other = {'type': 'command', 'command': 'keep-other', 'statusMessage': 'other'}
            b.write_json(hooks_file, {'custom': {'keep': True}, 'hooks': {
                'UserPromptSubmit': [{'hooks': [other, {'statusMessage': b.MARKER, 'command': 'old'}]}]}})
            install_linux.register_hooks(hooks_file, directory, Path(sys.executable))
            hooks = json.loads(hooks_file.read_text())
            self.assertEqual(hooks['custom'], {'keep': True})
            self.assertEqual(hooks['hooks']['UserPromptSubmit'][0]['hooks'], [other])
            for event in b.EVENTS:
                owned = [h for group in hooks['hooks'][event] for h in group['hooks']
                         if h.get('statusMessage') == b.MARKER]
                self.assertEqual(len(owned), 1)
                self.assertEqual(shlex.split(owned[0]['command']), [sys.executable,
                    str(directory / 'runtime/bridge/bridge.py'), 'hook', '--state-dir', str(directory)])
                self.assertNotIn('commandWindows', owned[0])
            result = subprocess.run([str(launcher), 'status'], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['mode'], 'work')
            self.assertTrue((directory / 'status.sqlite').exists())
            self.assertEqual((directory / 'status.sqlite').stat().st_mode & 0o777, 0o600)
            self.assertFalse(list((directory / 'runtime').rglob('*.ps1')))
            self.assertTrue((directory / 'runtime/mcp/package-lock.json').is_file())
            self.assertTrue((directory / 'runtime/vendor/jimmie-potts-device-mcp-1.0.0.tgz').is_file())

    def test_service_units_use_foreground_commands_and_do_not_start_services(self):
        import install_linux
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'state with spaces'
            directory.mkdir()
            units = Path(temporary) / 'units'
            b.write_json(directory / 'config.json', {'wall_port': 8765, 'controller_port': 41231, 'mcp_port': 41230})
            install_linux.write_service_units(directory, units, Path(sys.executable), Path('/native/node'))
            self.assertEqual(len(list(units.glob('*.service'))), 3)
            for name in ('wall', 'controller', 'mcp'):
                content = (units / f'codex-nanoleaf-{name}.service').read_text()
                self.assertIn('Type=simple', content)
                self.assertIn('UMask=0077', content)
                self.assertIn('Restart=on-failure', content)
                self.assertNotIn('.exe', content)
                self.assertIn(str(directory), content)
            wall = (units / 'codex-nanoleaf-wall.service').read_text()
            self.assertIn('"serve"', wall)
            self.assertIn('"--port" "8765"', wall)
            controller = (units / 'codex-nanoleaf-controller.service').read_text()
            self.assertIn('"controller-serve"', controller)
            self.assertIn('"--port" "41231"', controller)
            self.assertFalse((directory / 'notification-lock.sqlite').exists())
            with self.assertRaisesRegex(ValueError, 'already exists'):
                install_linux.write_service_units(directory, units, Path(sys.executable), Path('/native/node'))

    def test_machine_credentials_are_separate_and_private(self):
        import install_linux
        import controller_state
        import hashlib
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'state'
            layout = json.loads((Path(b.__file__).parents[1] / 'tests/fixtures/lines-layout.json').read_text())
            install_linux.prepare_state(directory, '192.0.2.12', 'fixtureToken',
                                        request=lambda *_: {'panelLayout': layout})
            install_linux.provision_machine_credentials(directory)
            config = json.loads((directory / 'mcp-config.json').read_text())
            principal = json.loads(Path(config['credentialsFile']).read_text())['principals'][0]
            client = (directory / 'mcp-client-token').read_text().strip()
            self.assertEqual(config['transport'], 'windows-http')
            self.assertEqual((config['port'], config['controllerPort']), (41230, 41231))
            self.assertEqual(principal['tokenSha256'], hashlib.sha256(client.encode()).hexdigest())
            self.assertNotEqual(client, principal['upstreamToken'])
            with contextlib.closing(b.connect_state(directory)) as db:
                self.assertEqual(controller_state.credential(db, principal['upstreamToken'])[0], 'codex')
                self.assertIsNone(controller_state.credential(db, client))
            for name in ('mcp-config.json', 'mcp-credentials.json', 'mcp-client-token'):
                self.assertEqual((directory / name).stat().st_mode & 0o777, 0o600)
            self.assertFalse((directory / 'notification-lock.sqlite').exists())

    def test_installer_help_exposes_linux_inputs(self):
        result = subprocess.run([sys.executable, str(Path(b.__file__).with_name('install_linux.py')), '--help'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in ('--ip', '--token-file', '--hooks-file', '--desktop-state-path', '--state-dir', '--node'):
            self.assertIn(flag, result.stdout)
