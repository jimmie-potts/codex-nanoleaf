from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch

from test_bridge import b
import wall_server


class PrismAssetTest(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),wall_server.handler(None,'PRIVATE_CSRF'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def test_packaged_components_are_local_and_protected(self):
        for name in ('prism.js','prism-adapters.js','prism-labels.js'):
            with self.subTest(name=name),urlopen(self.url+'/assets/'+name) as response:
                self.assertEqual(response.status,200)
                self.assertEqual(response.headers.get_content_type(),'text/javascript')
                self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
                self.assertEqual(response.headers['Cache-Control'],'no-store')
                self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
                text=response.read().decode()
                self.assertNotIn('PRIVATE_CSRF',text)
                self.assertGreater(len(text),100)
        for target in ('/assets/../bridge.py','/assets/%2e%2e/bridge.py','/assets/bridge.py','/assets/layout.json','/assets/prism.js/extra'):
            with self.assertRaises(HTTPError) as failure:urlopen(self.url+target)
            self.assertEqual(failure.exception.code,404)
            failure.exception.close()
        with self.assertRaises(HTTPError) as failure:
            urlopen(Request(self.url+'/assets/prism.js',headers={'Host':'evil.example'}))
        self.assertEqual(failure.exception.code,403)
        failure.exception.close()

    def test_missing_component_does_not_expose_a_private_path(self):
        with patch.object(Path,'read_bytes',side_effect=FileNotFoundError('PRIVATE_PATH')):
            with self.assertRaises(HTTPError) as failure:urlopen(self.url+'/assets/prism.js')
        self.assertEqual(failure.exception.code,503)
        self.assertNotIn(b'PRIVATE_PATH',failure.exception.read())
        failure.exception.close()

    def test_copied_wall_runs_in_a_foreground_process_without_device_or_windows_helpers(self):
        import json
        import shutil
        import subprocess
        import sys
        import tempfile
        import time
        source=Path(wall_server.__file__).parent
        raw=json.loads((source.parent/'tests/fixtures/lines-layout.json').read_text())
        groups=b.pair_lines(raw)
        with tempfile.TemporaryDirectory() as temporary:
            package=Path(temporary)/'package';package.mkdir()
            state=Path(temporary)/'state';state.mkdir()
            for name in ('bridge.py','devices.py','effects.py','project_map.py','shared_input.py','wall_server.py','integration_api.py', 'controller_state.py','controller_contract.py','wall.html','prism.js','prism-adapters.js','prism-labels.js'):
                shutil.copy2(source/name,package/name)
            (state/'config.json').write_text(json.dumps({'ip':'192.0.2.1','token':'PRIVATE_PACKAGE_TOKEN'}))
            (state/'layout.json').write_text(json.dumps({'line_groups':groups,'line_positions':[[i,0] for i in range(15)],'zone_geometry':{'positionData':raw['layout']['positionData'],'orientation':raw['globalOrientation']['value']}}))
            boot="import bridge as b\ndef forbidden(*a,**k): raise AssertionError('Unexpected device or worker call')\nb.light_request=forbidden\nb.launch_worker=forbidden\nb.subprocess.Popen=forbidden\nb.main()"
            child=subprocess.Popen([sys.executable,'-c',boot,'serve','--state-dir',str(state)],cwd=package,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+10
                while not (state/'map-server.json').exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.05)
                self.assertIsNone(child.poll(),'Packaged foreground server stays running')
                address='http://127.0.0.1:'+str(json.loads((state/'map-server.json').read_text())['port'])
                with urlopen(address+'/api/state',timeout=3) as response:
                    payload=response.read();status=json.loads(payload)
                self.assertEqual(len(status['connector_layout']['lines']),15)
                self.assertNotIn(b'PRIVATE_PACKAGE_TOKEN',payload)
                for name in ('prism.js','prism-adapters.js','prism-labels.js'):
                    with urlopen(address+'/assets/'+name,timeout=3) as response:
                        self.assertEqual(response.headers.get_content_type(),'text/javascript')
                        self.assertEqual(response.read(),(package/name).read_bytes())
            finally:
                child.terminate()
                child.communicate(timeout=10)
