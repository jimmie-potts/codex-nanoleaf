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
from unittest.mock import Mock, patch

from test_bridge import b
import codex_hooks
import configuration
import database
import jsonfile
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
            device = lambda *_: {}
            with patch.object(configuration, 'data_dir', return_value=default), \
                    patch.object(configuration, 'load_config', return_value={'ip': '192.0.2.1', 'line_groups': []}) as load, \
                    patch.object(b, 'SceneRestorer') as scene, \
                    contextlib.redirect_stdout(io.StringIO()):
                scene.return_value.state = {'scene': None}
                b.setup(args, request=device)
            load.assert_called_once_with(target, 'wall', request=device)
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
                    patch.object(configuration, 'data_dir', return_value=default), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                launch = Mock()
                b.main(launch=launch)
            self.assertEqual(json.loads(output.getvalue()), {})
            self.assertTrue((target / 'status.sqlite').exists())
            self.assertFalse((default / 'status.sqlite').exists())
            with contextlib.closing(database.connect_state(target)) as db:
                self.assertEqual(db.execute('SELECT id FROM sessions').fetchall(), [('linux-task',)])
            launch.assert_called_once_with(target)


class MapCommandTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        jsonfile.write_json(self.directory / 'config.json', {'ip': '192.0.2.1', 'token': 'fake'})
        jsonfile.write_json(self.directory / 'layout.json', {
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
                patch('webbrowser.open') as browser, \
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
            jsonfile.write_json(self.directory / 'config.json', {
                'ip': '192.0.2.1', 'token': 'fake', 'wall_port': port})
            result = subprocess.run(self.command('serve'), capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(port), result.stderr)
        # Windows may report access denied when a socket owns the port exclusively.
        self.assertRegex(result.stderr, 'already in use|Cannot bind')
        self.assertFalse((self.directory / 'map-server.json').exists())

    def test_stale_receipt_does_not_accept_another_map_owner(self):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        self.start(port)
        receipt = json.loads((self.directory / 'map-server.json').read_text())
        receipt['instance'] = 'earlier-instance'
        jsonfile.write_json(self.directory / 'map-server.json', receipt)
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
        self.assertRegex(result.stderr, 'already in use|Cannot bind')
        self.assertFalse((self.directory / 'controller-server.json').exists())
        with contextlib.closing(sqlite3.connect(self.directory / 'controller-lock.sqlite')) as lock:
            lock.execute('BEGIN EXCLUSIVE')
            duplicate = subprocess.run(self.command('controller-serve', '--port', str(port)),
                                       capture_output=True, text=True, timeout=5)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn('already running', duplicate.stderr)


@unittest.skipUnless(sys.platform == 'linux', 'Native Linux installation')
class LinuxInstallTest(unittest.TestCase):
    def test_state_requires_a_supported_local_filesystem(self):
        import install_linux
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'state'
            for filesystem in ('nfs', 'nfs4', 'fuse.sshfs', 'ceph', 'cifs', 'unknown'):
                mounts = f'root / ext4 rw 0 0\nserver {temporary} {filesystem} rw 0 0\n'
                with self.subTest(filesystem=filesystem), patch.object(Path, 'read_text', return_value=mounts):
                    with self.assertRaisesRegex(ValueError, 'local Linux filesystem'):
                        install_linux.linux_state_directory(directory)
            # Stacked mounts can repeat a path; a remote type must not be
            # hidden by lexicographic ordering of its local counterpart.
            for records in (('xfs', 'nfs4'), ('nfs4', 'xfs')):
                mounts = ''.join(f'device {temporary} {kind} rw 0 0\n' for kind in records)
                with self.subTest(records=records), patch.object(Path, 'read_text', return_value=mounts):
                    with self.assertRaisesRegex(ValueError, 'local Linux filesystem'):
                        install_linux.linux_state_directory(directory)
            # Select the longest matching mount: a local directory can sit
            # below a remote parent, and /tmp-other must not match /tmp.
            mounts = (f'server / nfs4 rw 0 0\nlocal {temporary} ext4 rw 0 0\n'
                      f'server {temporary}-other nfs4 rw 0 0\n')
            with patch.object(Path, 'read_text', return_value=mounts):
                self.assertEqual(install_linux.linux_state_directory(directory), directory)
            self.assertFalse(directory.exists())

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
            config = configuration.load_config(directory)
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

    def test_copied_runtime_serves_all_wall_scripts(self):
        import install_linux
        import re
        from urllib.request import ProxyHandler, build_opener
        layout = json.loads((Path(b.__file__).parents[1] / 'tests/fixtures/lines-layout.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'state'
            install_linux.prepare_state(directory, '192.0.2.12', 'fixtureToken',
                                        request=lambda *_: {'panelLayout': layout})
            install_linux.copy_runtime(directory)
            launcher = install_linux.write_launcher(directory, Path(sys.executable))
            process = subprocess.Popen([str(launcher), 'serve', '--port', '0'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 5
                url = None
                while time.monotonic() < deadline and process.poll() is None:
                    url = wall_server.map_url(directory)
                    if url:
                        break
                    time.sleep(.02)
                self.assertIsNotNone(url, 'Copied map did not become healthy')
                opener = build_opener(ProxyHandler({}))
                with opener.open(url, timeout=3) as response:
                    scripts = re.findall(r'<script src="([^"]+)"', response.read().decode())
                self.assertTrue(scripts, 'The installed map must load its renderer')
                for script in scripts:
                    with self.subTest(script=script), opener.open(url + script, timeout=3) as response:
                        self.assertEqual(response.headers.get_content_type(), 'text/javascript')
                        self.assertEqual(response.read(),
                                         Path(b.__file__).with_name(Path(script).name).read_bytes())
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=5)

    def test_copied_runtime_holds_and_starts_every_shared_module(self):
        """AC4/AC6 of #118: packaging evidence from an isolated copy, not an installed upgrade."""
        import install_linux
        source = Path(b.__file__).parent
        layout = json.loads((source.parent / 'tests/fixtures/lines-layout.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'state'
            install_linux.prepare_state(directory, '192.0.2.12', 'fixtureToken',
                                        request=lambda *_: {'panelLayout': layout})
            runtime = install_linux.copy_runtime(directory) / 'bridge'
            modules = sorted(path.stem for path in source.glob('*.py') if path.name != 'install_linux.py')
            self.assertEqual(sorted(path.stem for path in runtime.glob('*.py')), modules)
            clean = {key: value for key, value in os.environ.items() if key != 'PYTHONPATH'}
            # Every module imports from the copy alone, without the source tree on the path.
            probe = ('import importlib, json, sys; sys.path.insert(0, sys.argv[1]); '
                     'print(json.dumps({m: importlib.import_module(m).__file__ for m in sys.argv[2:]}))')
            result = subprocess.run([sys.executable, '-I', '-c', probe, str(runtime), *modules],
                                    capture_output=True, text=True, timeout=20, cwd=temporary, env=clean)
            self.assertEqual(result.returncode, 0, result.stderr)
            for module, path in json.loads(result.stdout).items():
                self.assertEqual(Path(path).parent, runtime, module)
            launcher = install_linux.write_launcher(directory, Path(sys.executable))
            codex = Path(temporary) / 'codex'
            for arguments in (['--help'], ['status'], ['map-status'], ['shared-status'], ['shared-select', '--help'],
                              ['hooks', 'register', '--codex-home', str(codex)], ['controller-status', '--help'],
                              ['controller-configure', '--controller-id', 'local-controller', '--device-id', 'wall',
                               '--source-id', 'local-source'], ['controller-status'], ['device-enroll', '--help']):
                with self.subTest(command=' '.join(arguments)):
                    result = subprocess.run([str(launcher), *arguments], capture_output=True, text=True,
                                            timeout=20, cwd=temporary, env=clean)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            hooks = json.loads((codex / 'hooks.json').read_text())
            command = hooks['hooks']['Stop'][0]['hooks'][0]['command']
            self.assertEqual(shlex.split(command)[1], str(runtime / 'bridge.py'))

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
            jsonfile.write_json(hooks_file, {'custom': {'keep': True}, 'hooks': {
                'UserPromptSubmit': [{'hooks': [other, {'statusMessage': codex_hooks.MARKER, 'command': 'old'}]}]}})
            install_linux.register_hooks(hooks_file, directory, Path(sys.executable))
            hooks = json.loads(hooks_file.read_text())
            self.assertEqual(hooks['custom'], {'keep': True})
            self.assertEqual(hooks['hooks']['UserPromptSubmit'][0]['hooks'], [other])
            for event in codex_hooks.EVENTS:
                owned = [h for group in hooks['hooks'][event] for h in group['hooks']
                         if h.get('statusMessage') == codex_hooks.MARKER]
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
            jsonfile.write_json(directory / 'config.json', {'wall_port': 8765, 'controller_port': 41231, 'mcp_port': 41230})
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
            self.assertEqual(config['transport'], 'loopback-http')
            self.assertEqual((config['port'], config['controllerPort']), (41230, 41231))
            self.assertEqual(principal['tokenSha256'], hashlib.sha256(client.encode()).hexdigest())
            self.assertNotEqual(client, principal['upstreamToken'])
            with contextlib.closing(database.connect_state(directory)) as db:
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
