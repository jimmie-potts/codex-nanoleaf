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

    @unittest.skipIf(sys.platform=='win32','WSL forwarding is exercised on Linux')
    def test_installed_controller_commands_forward_before_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/'User/AppData/Local/CodexNanoleaf';directory.mkdir(parents=True)
            shutil.copyfile(b.__file__,directory/'bridge.py')
            for name in ('project_map.py','shared_input.py','devices.py'):
                shutil.copyfile(Path(b.__file__).with_name(name),directory/name)
            for command in ('controller-configure','controller-token','controller-revoke','controller-serve','controller-status','controller-disable','shared-configure','shared-preflight','shared-select','shared-status','shared-acknowledge'):
                result=subprocess.run([sys.executable,str(directory/'bridge.py'),command],capture_output=True,text=True)
                self.assertIn('Windows runtime is unavailable',result.stderr)
                self.assertFalse((directory/'status.sqlite').exists())
