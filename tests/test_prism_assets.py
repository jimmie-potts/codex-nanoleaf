from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch

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
        for name in ('prism.js','prism-adapters.js'):
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
