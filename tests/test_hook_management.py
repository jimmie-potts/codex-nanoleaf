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
        self.assertEqual(after_register['hooks']['PreToolUse'], self.original['hooks']['PreToolUse'])
        self.assertEqual(after_register['hooks']['PostToolUse'], self.original['hooks']['PostToolUse'])
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

    def test_malformed_hooks_are_left_byte_for_byte_untouched(self):
        malformed = b'{not json\n'
        self.hooks.write_bytes(malformed)
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            bridge.manage_hooks(self.home, 'remove', script=Path('/opt/nanoleaf/bridge.py'))
        self.assertEqual(self.hooks.read_bytes(), malformed)

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
