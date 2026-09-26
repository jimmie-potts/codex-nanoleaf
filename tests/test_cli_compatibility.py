"""Documented bridge.py command names and arguments, and startup without optional dependencies (#118)."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / 'bridge/bridge.py'

# Each documented command family, as its parser advertises it. Changing one is a CLI contract change.
FAMILIES = {
    ('--help',): {
        'choices': [['setup', 'hook', 'worker', 'mode', 'status', 'map', 'serve', 'style', 'map-status'],
                    ['work', 'free', 'quiet', 'classic', 'project']],
        'options': ['--json', '--port', '--no-open', '--device', '--check', '--demo', '--reset',
                    '--uninstall', '--notify', '--refresh', '--comet']},
    ('shared-status', '--help'): {
        'choices': [['shared-configure', 'shared-preflight', 'shared-select', 'shared-status', 'shared-acknowledge'],
                    ['legacy', 'shared']],
        'options': ['--state-dir', '--config', '--session', '--notice', '--retry']},
    ('hooks', '--help'): {
        'choices': [['remove', 'register']],
        'options': ['--codex-home']},
    ('controller-status', '--help'): {
        'choices': [['controller-configure', 'controller-token', 'controller-revoke', 'controller-serve',
                     'controller-status', 'controller-disable']],
        'options': ['--controller-id', '--device-id', '--source-id', '--principal', '--read-only', '--port']},
    ('device-enroll', '--help'): {'choices': [], 'options': ['--ip', '--device', '--token-file', '--pair']},
    ('device-address', '--help'): {'choices': [], 'options': ['--device', '--ip']},
    ('device-remove', '--help'): {'choices': [], 'options': ['--device', '--force']},
}
OPTIONAL = ('jsonschema', 'agent_state', 'controller_contract', 'nanoleaf_verified_contracts')

# Run bridge.py as the launcher does, with the optional listener and schema packages unavailable.
BOOT = r'''
import json, os, runpy, sys
class Unavailable:
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in ('jsonschema', 'agent_state'):
            raise ModuleNotFoundError(name)
sys.meta_path.insert(0, Unavailable())
script, record, *arguments = sys.argv[1:]
sys.argv = [script, *arguments]
code = 0
try:
    runpy.run_path(script, run_name='__main__')
except SystemExit as exit:
    code = exit.code if isinstance(exit.code, int) else (0 if exit.code is None else 1)
finally:
    with open(record, 'w') as output:
        json.dump(sorted(name for name in sys.modules if name.split('.')[0] in %r), output)
sys.exit(code)
''' % (OPTIONAL,)


def environment():
    # A clean path proves the entry point finds its own modules.
    return {key: value for key, value in os.environ.items() if key != 'PYTHONPATH'}


class CliCompatibilityTest(unittest.TestCase):
    def run_bridge(self, *arguments, stdin=''):
        return subprocess.run([sys.executable, str(BRIDGE), *arguments], input=stdin, capture_output=True,
                              text=True, timeout=20, env=environment(), cwd=tempfile.gettempdir())

    def test_documented_command_families_keep_their_names_and_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            for arguments, expected in FAMILIES.items():
                with self.subTest(family=arguments[0]):
                    result = self.run_bridge(*arguments, '--state-dir', temporary)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    usage = result.stdout
                    choices = [group.split(',') for group in re.findall(r'\{([a-z,-]+)\}', usage.split('\n\n')[0])]
                    self.assertEqual(choices, expected['choices'])
                    options = set(re.findall(r'(?<![\w-])(--[a-z][a-z-]*)', usage)) - {'--help', '--state-dir'}
                    self.assertEqual(options, set(expected['options']) - {'--state-dir'})

    def test_documented_commands_start_without_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / 'state'
            state.mkdir()
            codex = Path(temporary) / 'codex'
            commands = [
                # A hook initializes the state; status reads never do.
                (['hook'], 0, '{}'),
                (['map-status'], 0, None),
                (['status'], 0, None),
                (['status', '--json'], 0, None),
                (['shared-status'], 0, None),
                (['hooks', 'register', '--codex-home', str(codex)], 0, None),
                (['controller-configure', '--controller-id', 'local-controller', '--device-id', 'wall',
                  '--source-id', 'local-source'], 0, None),
                (['controller-status'], 0, None),
                # The listener needs the optional contract dependencies and reports that without a trace.
                (['controller-serve', '--port', '0'], 1, None),
            ]
            for arguments, code, stdin in commands:
                with self.subTest(command=' '.join(arguments[:2])):
                    record = Path(temporary) / 'loaded.json'
                    result = subprocess.run(
                        [sys.executable, '-c', BOOT, str(BRIDGE), str(record), *arguments, '--state-dir', str(state)],
                        input=stdin or '', capture_output=True, text=True, timeout=20, env=environment(),
                        cwd=temporary)
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    loaded = json.loads(record.read_text())
                    if arguments[0] == 'controller-serve':
                        self.assertIn('optional dependencies', result.stderr)
                        self.assertEqual(loaded, ['controller_contract'])
                    else:
                        self.assertEqual(loaded, [], 'Only the controller listener may load optional packages')
            self.assertEqual(json.loads(subprocess.run(
                [sys.executable, str(BRIDGE), 'status', '--state-dir', str(state)], capture_output=True,
                text=True, timeout=20, env=environment()).stdout)['mode'], 'work')


if __name__ == '__main__':
    unittest.main()
