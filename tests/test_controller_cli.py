import contextlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_bridge import b


class ControllerCLITest(unittest.TestCase):
    def test_configure_token_status_and_revoke(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            def run(*args):
                result=subprocess.run([sys.executable,str(Path(b.__file__)),*args,'--state-dir',str(directory)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr);return result.stdout
            run('controller-configure','--controller-id','controller','--device-id','device','--source-id','source')
            token=run('controller-token','--principal','client').strip();self.assertGreater(len(token),30)
            status=json.loads(run('controller-status'));self.assertEqual(status['identity']['deviceId'],'device')
            self.assertNotIn(token,json.dumps(status))
            self.assertEqual(status['serviceHealth'],'unknown')
            run('controller-revoke','--principal','client')

    def test_installed_commands_under_a_windows_shaped_path_open_only_local_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/'User/AppData/Local/CodexNanoleaf';directory.mkdir(parents=True)
            shutil.copyfile(b.__file__,directory/'bridge.py')
            for name in ('project_map.py','shared_input.py','devices.py','effects.py','panels.py'):
                shutil.copyfile(Path(b.__file__).with_name(name),directory/name)
            state=Path(temporary)/'state';state.mkdir()
            with contextlib.closing(b.connect_state(state)): pass
            result=subprocess.run([sys.executable,str(directory/'bridge.py'),'status','--state-dir',str(state)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('Windows',result.stderr)
            self.assertEqual(json.loads(result.stdout)['mode'],'work')
            self.assertTrue((state/'status.sqlite').exists())
