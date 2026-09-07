"""The helper has no installed bridge or device dependencies."""
import importlib.util
from pathlib import Path
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'mcp' / 'windows-controller-http.py'

class McpHelperTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.spec_from_file_location('mcp_http_helper', HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_rejects_non_loopback_destination_fields(self):
        helper = self.module()
        with self.assertRaises(ValueError):
            helper.validate({'operation': 'snapshot', 'port': 12345, 'deviceId': 'wall', 'token': 'a' * 43, 'url': 'http://example.com'})

    def test_raw_command_body_rejects_before_http(self):
        helper = self.module()
        with self.assertRaises(ValueError):
            helper.validate({'operation': 'command', 'port': 12345, 'deviceId': 'wall', 'token': 'a' * 43, 'request': {'raw': 'reset'}})

    def test_request_is_bounded_and_duplicate_keys_reject(self):
        helper = self.module()
        with self.assertRaises(ValueError):
            helper.parse('{"port":1,"port":2}')
        with self.assertRaises(ValueError):
            helper.parse('[' * 34 + '0' + ']' * 34)

if __name__ == '__main__':
    unittest.main()

class McpHelperHttpTests(unittest.TestCase):
    def test_fixed_http_route_authentication_and_no_redirect(self):
        import http.server
        import threading
        from unittest.mock import patch
        helper = McpHelperTests().module()
        seen = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get('Authorization'), self.headers.get('Host')))
                self.send_response(302 if len(seen) == 2 else 200)
                self.send_header('Location', 'http://unconfigured.invalid')
                self.end_headers()
                self.wfile.write(b'{"ready":true}')
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = {'operation': 'snapshot', 'port': server.server_port, 'deviceId': 'wall', 'token': 'a' * 43}
            with patch.dict('os.environ', {'HTTP_PROXY': 'http://unconfigured.invalid', 'HTTPS_PROXY': 'http://unconfigured.invalid'}):
                self.assertEqual(helper.exchange(request), {'status': 200, 'body': {'ready': True}})
                with self.assertRaises(ValueError):
                    helper.exchange(request)
            self.assertEqual(seen[0], ('/controller/v1/snapshot?deviceId=wall', 'Bearer ' + 'a' * 43, '127.0.0.1:' + str(server.server_port)))
            self.assertEqual(len(seen), 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
