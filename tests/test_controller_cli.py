import contextlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_bridge import b
import database


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
            # Copy the runtime modules as the Linux installer does.
            for path in Path(b.__file__).parent.glob('*.py'):
                if path.name!='install_linux.py': shutil.copyfile(path,directory/path.name)
            state=Path(temporary)/'state';state.mkdir()
            with contextlib.closing(database.connect_state(state)): pass
            result=subprocess.run([sys.executable,str(directory/'bridge.py'),'status','--state-dir',str(state)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('Windows',result.stderr)
            self.assertEqual(json.loads(result.stdout)['mode'],'work')
            self.assertTrue((state/'status.sqlite').exists())


class RegisterCredentialTest(unittest.TestCase):
    """#194: register() accepts a caller-supplied credential, stored only as its digest; issue() uses it."""

    def setUp(self):
        import controller_server
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.server = controller_server
        controller_server.configure(self.directory, 'wall-controller', 'wall', 'wall')

    def credentials(self):
        with contextlib.closing(database.connect_state(self.directory)) as db:
            return db.execute('SELECT principal,digest,scopes,active FROM controller_credentials').fetchall()

    def test_a_valid_token_is_stored_only_as_its_digest(self):
        import hashlib
        token = 'A' * 20 + '_-' + 'z9' * 10 + 'q'
        self.assertEqual(len(token), 43)
        self.server.register(self.directory, 'hub', ['read', 'control'], token)
        self.assertEqual(self.credentials(), [('hub', hashlib.sha256(token.encode()).hexdigest(), '["read","control"]', 1)])
        self.assertNotIn(token.encode(), (self.directory / 'status.sqlite').read_bytes())

    def test_malformed_tokens_and_invalid_principals_or_scopes_store_nothing(self):
        valid = 'b' * 43
        for principal, scopes, token in (('hub', ['read'], 'b' * 44), ('hub', ['read'], 'b' * 42), ('hub', ['read'], 'b' * 42 + '='),
                                         ('hub', ['read'], 'b' * 42 + '/'), ('hub', ['read'], None), ('hub', ['read'], 43),
                                         ('bad principal', ['read'], valid), ('', ['read'], valid), ('hub', [], valid),
                                         ('hub', ['read', 'admin'], valid)):
            with self.subTest(principal=principal, scopes=scopes, token=token), self.assertRaises(ValueError):
                self.server.register(self.directory, principal, scopes, token)
        self.assertEqual(self.credentials(), [])

    def test_issue_mints_a_token_register_accepts(self):
        token = self.server.issue(self.directory, 'client', ['read'])
        self.assertRegex(token, r'^[A-Za-z0-9_-]{43}$')
        self.assertEqual([row[0] for row in self.credentials()], ['client'])
