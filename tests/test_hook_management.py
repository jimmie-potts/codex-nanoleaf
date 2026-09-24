import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bridge', ROOT / 'bridge/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class HookManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / 'codex'
        self.home.mkdir()
        self.hooks = self.home / 'hooks.json'
        self.original = {
            'description': 'preserve formatting-independent content',
            'hooks': {
                'PreToolUse': [{'hooks': [
                    {'type': 'command', 'command': 'hub-shared-hook', 'statusMessage': 'shared-hook'}
                ]}],
                'PostToolUse': [{'hooks': [
                    {'type': 'command', 'command': 'other-client', 'statusMessage': 'keep'}
                ]}],
                'Stop': [
                    {'hooks': [
                        {'type': 'command', 'command': 'trusted', 'statusMessage': 'mine'},
                        {'type': 'command', 'command': 'python3 /old/linux/bridge.py hook',
                         'commandWindows': 'powershell.exe -EncodedCommand abc',
                         'timeout': 5, 'statusMessage': bridge.MARKER},
                    ]},
                    {'matcher': 'Bash', 'hooks': [
                        {'type': 'command', 'command': 'hub', 'statusMessage': 'shared-hook'}
                    ]},
                ],
            },
        }
        self.hooks.write_text(json.dumps(self.original, indent=4) + '\n')

    def tearDown(self):
        self.temp.cleanup()

    def read(self):
        return json.loads(self.hooks.read_text())

    def raw_group(self, raw, event, group_index):
        text = raw.decode('utf-8-sig')
        root = bridge.json_spans(text)
        hooks = bridge.json_member(root, 'hooks')[3]
        groups = bridge.json_member(hooks, event)[3][3]
        node = groups[group_index]
        return text[node[1]:node[2]].encode()

    def test_remove_only_marked_hooks_and_make_private_backup(self):
        before = self.hooks.read_bytes()
        preserved = {event: self.raw_group(before, event, 0)
                     for event in ('PreToolUse', 'PostToolUse')}
        shared_group = self.raw_group(before, 'Stop', 1)
        bridge.manage_hooks(self.home, 'remove', script=Path('/opt/nanoleaf/bridge.py'))
        after = self.hooks.read_bytes()
        for event, raw_group in preserved.items():
            self.assertEqual(self.raw_group(after, event, 0), raw_group)
        self.assertEqual(self.raw_group(after, 'Stop', 1), shared_group)
        result = self.read()
        self.assertEqual(result['description'], self.original['description'])
        self.assertEqual(result['hooks']['Stop'][0]['hooks'], [self.original['hooks']['Stop'][0]['hooks'][0]])
        self.assertEqual(result['hooks']['Stop'][1], self.original['hooks']['Stop'][1])
        self.assertEqual(result['hooks']['PreToolUse'], self.original['hooks']['PreToolUse'])
        self.assertEqual(result['hooks']['PostToolUse'], self.original['hooks']['PostToolUse'])
        backups = list(self.home.glob('hooks.nanoleaf-backup-*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)
        if bridge.os.name != 'nt':
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_repeated_remove_and_register_are_idempotent(self):
        bridge.manage_hooks(self.home, 'remove', script=Path('/opt/nanoleaf/bridge.py'))
        after_remove = self.hooks.read_bytes()
        bridge.manage_hooks(self.home, 'remove', script=Path('/opt/nanoleaf/bridge.py'))
        self.assertEqual(self.hooks.read_bytes(), after_remove)
        bridge.manage_hooks(self.home, 'register', script=Path('/opt/nanoleaf/bridge.py'))
        after_register = self.read()
        self.assertEqual(sum(h.get('statusMessage') == bridge.MARKER
                             for group in after_register['hooks']['Stop']
                             for h in group.get('hooks', [])), 1)
        self.assertIn(self.original['hooks']['Stop'][0]['hooks'][1],
                      [h for group in after_register['hooks']['Stop'] for h in group.get('hooks', [])])
        self.assertEqual(after_register['hooks']['PreToolUse'][0], self.original['hooks']['PreToolUse'][0])
        self.assertEqual(after_register['hooks']['PostToolUse'][0], self.original['hooks']['PostToolUse'][0])
        self.assertTrue(bridge.has_legacy_hooks(self.home))
        self.assertEqual(after_register['hooks']['Stop'][1], self.original['hooks']['Stop'][1])
        self.assertEqual(self.raw_group(self.hooks.read_bytes(), 'PreToolUse', 0),
                         self.raw_group(after_remove, 'PreToolUse', 0))
        registered = self.hooks.read_bytes()
        bridge.manage_hooks(self.home, 'register', script=Path('/opt/nanoleaf/bridge.py'))
        self.assertEqual(self.hooks.read_bytes(), registered)

    def test_register_without_backup_adds_hooks_to_the_explicit_home(self):
        other = self.home / 'other-client'
        self.assertTrue(bridge.manage_hooks(other, 'register', script=Path('/opt/nanoleaf/bridge.py')))
        installed = json.loads((other / 'hooks.json').read_text())
        self.assertTrue(bridge.has_legacy_hooks(other))
        self.assertEqual(installed['hooks']['UserPromptSubmit'][0]['hooks'][0]['statusMessage'], bridge.MARKER)

    def test_register_preserves_complete_hook_positions_and_bytes(self):
        value = bridge.merge_hooks({}, 'python3 /trusted/bridge.py hook')
        value['hooks']['Stop'].append(self.original['hooks']['Stop'][1])
        self.hooks.write_text(json.dumps(value, indent=4) + '\n')
        before = self.hooks.read_bytes()
        self.assertFalse(bridge.manage_hooks(self.home, 'register', script=Path('/new/bridge.py')))
        self.assertEqual(self.hooks.read_bytes(), before)
        self.assertEqual(list(self.home.glob('hooks.nanoleaf-backup-*.json')), [])

    def test_round_trip_restores_group_and_mixed_handler_positions(self):
        value = bridge.merge_hooks({}, 'python3 /trusted/bridge.py hook')
        # A mixed group exercises handler indices; a following shared group
        # exercises group indices. Both belong to Codex's saved trust identity.
        value['hooks']['Stop'][0]['hooks'].insert(0, self.original['hooks']['Stop'][0]['hooks'][0])
        value['hooks']['Stop'].append(self.original['hooks']['Stop'][1])
        self.hooks.write_bytes(b'\xef\xbb\xbf' + (json.dumps(value, indent=4) + '\r\n').encode())
        before = self.hooks.read_bytes()
        bridge.manage_hooks(self.home, 'remove', script=Path('/new/bridge.py'))
        bridge.manage_hooks(self.home, 'register', script=Path('/new/bridge.py'))
        self.assertEqual(self.hooks.read_bytes(), before)

    def test_registration_preserves_edits_made_after_removal(self):
        bridge.manage_hooks(self.home, 'remove', script=Path('/new/bridge.py'))
        edited = self.read()
        edited['description'] = 'changed after removal'
        edited['hooks']['Stop'].append({'hooks': [{'type': 'command', 'command': 'new peer'}]})
        self.hooks.write_text(json.dumps(edited, indent=3))
        retained = self.hooks.read_bytes()
        bridge.manage_hooks(self.home, 'register', script=Path('/new/bridge.py'))
        self.assertEqual(self.read()['description'], edited['description'])
        for index in range(len(edited['hooks']['Stop'])):
            self.assertEqual(self.raw_group(self.hooks.read_bytes(), 'Stop', index),
                             self.raw_group(retained, 'Stop', index))
        self.assertTrue(bridge.has_legacy_hooks(self.home))

    def test_invalid_backups_are_skipped_before_restoring_positions(self):
        bridge.manage_hooks(self.home, 'remove', script=Path('/new/bridge.py'))
        removed = self.hooks.read_bytes()
        duplicate = (b'{"hooks":{},"hooks":' + json.dumps(self.original['hooks']).encode() + b'}')
        invalid_group = dict(self.original, hooks={**self.original['hooks'], 'Interrupt': [None]})
        backup = self.home / 'hooks.nanoleaf-backup-999999999999999999999.json'
        for raw in (b'{bad json', duplicate, json.dumps(invalid_group).encode()):
            with self.subTest(raw=raw):
                self.hooks.write_bytes(removed)
                backup.write_bytes(raw)
                bridge.manage_hooks(self.home, 'register', script=Path('/new/bridge.py'))
                self.assertEqual(self.read()['hooks']['Stop'], self.original['hooks']['Stop'])
                self.assertTrue(bridge.has_legacy_hooks(self.home))

    def test_malformed_hooks_are_left_byte_for_byte_untouched(self):
        for malformed in (b'{not json\n', b'', b'{', b'{"hooks":'):
            with self.subTest(malformed=malformed):
                self.hooks.write_bytes(malformed)
                with self.assertRaises(ValueError):
                    bridge.manage_hooks(self.home, 'remove', script=Path('/opt/nanoleaf/bridge.py'))
                self.assertEqual(self.hooks.read_bytes(), malformed)

    def test_failed_atomic_replacement_leaves_original_hooks_untouched(self):
        from unittest.mock import patch
        before = self.hooks.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('fixture replacement failure')):
            with self.assertRaises(OSError):
                bridge.manage_hooks(self.home, 'remove', script=Path('/opt/nanoleaf/bridge.py'))
        self.assertEqual(self.hooks.read_bytes(), before)
        self.assertEqual(list(self.home.glob('.hooks-*.tmp')), [])

    def test_register_completes_partial_hooks_and_preserves_existing_commands(self):
        self.assertFalse(bridge.has_legacy_hooks(self.home))
        before = self.hooks.read_bytes()
        bridge.manage_hooks(self.home, 'register', script=Path('/opt/nanoleaf/bridge.py'))
        self.assertTrue(bridge.has_legacy_hooks(self.home))
        marked = [h for group in self.read()['hooks']['Stop'] for h in group['hooks']
                  if h.get('statusMessage') == bridge.MARKER]
        self.assertEqual(marked, [self.original['hooks']['Stop'][0]['hooks'][1]])
        for index in (0, 1):
            self.assertEqual(self.raw_group(self.hooks.read_bytes(), 'Stop', index),
                             self.raw_group(before, 'Stop', index))

    @unittest.skipUnless(bridge.sys.platform == 'linux', 'Linux launcher contract')
    def test_installed_launcher_uses_its_custom_state_for_hook_lifecycle(self):
        import contextlib
        import shlex
        import subprocess
        import install_linux
        state_dir = self.home / 'custom-runtime'
        (state_dir / 'runtime').mkdir(parents=True)
        (state_dir / 'runtime' / 'bridge').symlink_to(ROOT / 'bridge', target_is_directory=True)
        launcher = install_linux.write_launcher(state_dir, Path(bridge.sys.executable))
        with contextlib.closing(bridge.connect_state(state_dir)) as db, db:
            db.execute("UPDATE shared_input SET source='shared' WHERE id=1")
        codex_home = self.home / 'launcher-codex'
        def run(operation):
            return subprocess.run([str(launcher), 'hooks', operation, '--codex-home', str(codex_home)],
                                  capture_output=True, text=True, timeout=5)
        result = run('register')
        self.assertEqual(result.returncode, 0, result.stderr)
        command = json.loads((codex_home / 'hooks.json').read_text())['hooks']['UserPromptSubmit'][0]['hooks'][0]['command']
        self.assertEqual(shlex.split(command)[-2:], ['--state-dir', str(state_dir)])
        before = (state_dir / 'status.sqlite').read_bytes()
        result = run('remove')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(bridge.has_legacy_hooks(codex_home))
        self.assertEqual((state_dir / 'status.sqlite').read_bytes(), before)
        result = run('register')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(bridge.has_legacy_hooks(codex_home))
        restored = json.loads((codex_home / 'hooks.json').read_text())['hooks']['UserPromptSubmit'][0]['hooks'][0]['command']
        self.assertEqual(restored, command)

    def test_duplicate_keys_are_rejected_before_mutation(self):
        duplicate = (b'{"hooks":{},"hooks":{"Stop":[{"hooks":[{"type":"command",'
                    b'"command":"old","statusMessage":"' + bridge.MARKER.encode() + b'"}]}]}}')
        self.hooks.write_bytes(duplicate)
        with self.assertRaisesRegex(ValueError, 'duplicate JSON object key'):
            bridge.manage_hooks(self.home, 'remove', script=Path('/opt/nanoleaf/bridge.py'))
        self.assertEqual(self.hooks.read_bytes(), duplicate)
        self.assertEqual(list(self.home.glob('hooks.nanoleaf-backup-*.json')), [])

    def test_duplicate_keys_are_rejected_even_when_removal_would_be_a_noop(self):
        duplicate = b'{"hooks":{},"hooks":{}}'
        self.hooks.write_bytes(duplicate)
        with self.assertRaisesRegex(ValueError, 'duplicate JSON object key'):
            bridge.manage_hooks(self.home, 'remove', script=Path('/opt/nanoleaf/bridge.py'))
        self.assertEqual(self.hooks.read_bytes(), duplicate)

    def test_shared_selection_refusal_is_content_free_and_names_registration(self):
        import shared_input
        from unittest.mock import patch
        class Bridge:
            os = bridge.os
            has_legacy_hooks = staticmethod(lambda _: False)
            windows_path = staticmethod(lambda value: value)
        with patch.object(shared_input, 'source_config', side_effect=AssertionError('must refuse before reading state')):
            with self.assertRaises(shared_input.FeedError) as raised:
                shared_input.select_source(self.home, Bridge(), 'legacy')
        self.assertIn('hooks register', str(raised.exception))

    def test_removal_refusal_in_legacy_mode_preserves_home(self):
        before = self.hooks.read_bytes()
        import contextlib
        from unittest.mock import patch
        with contextlib.closing(bridge.connect_state(self.home)):
            pass
        state = (self.home / 'status.sqlite').read_bytes()
        with patch.object(bridge, 'data_dir', return_value=self.home), \
             self.assertRaises(SystemExit):
            bridge.hooks_command(['remove', '--codex-home', str(self.home)])
        self.assertEqual(self.hooks.read_bytes(), before)
        self.assertEqual((self.home / 'status.sqlite').read_bytes(), state)
        self.assertEqual(list(self.home.glob('hooks.nanoleaf-backup-*.json')), [])

    def test_removal_in_shared_mode_preserves_runtime_state(self):
        import contextlib
        from unittest.mock import patch
        with contextlib.closing(bridge.connect_state(self.home)) as db, db:
            db.execute("UPDATE shared_input SET source='shared' WHERE id=1")
        state = (self.home / 'status.sqlite').read_bytes()
        with patch.object(bridge, 'data_dir', return_value=self.home):
            bridge.hooks_command(['remove', '--codex-home', str(self.home)])
        self.assertFalse(bridge.has_legacy_hooks(self.home))
        self.assertEqual((self.home / 'status.sqlite').read_bytes(), state)
        self.assertEqual(len(list(self.home.glob('hooks.nanoleaf-backup-*.json'))), 1)

    def test_removal_without_runtime_state_refuses_default_legacy_source(self):
        from unittest.mock import patch
        before = self.hooks.read_bytes()
        with patch.object(bridge, 'data_dir', return_value=self.home), \
             self.assertRaises(SystemExit):
            bridge.hooks_command(['remove', '--codex-home', str(self.home)])
        self.assertEqual(self.hooks.read_bytes(), before)
        self.assertFalse((self.home / 'status.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
