import http.client
import json
import socket
import threading
import unittest
import test_controller_state as state_tests


class ControllerHTTPTest(unittest.TestCase):
    request=state_tests.ControllerStateTest.request
    def setUp(self):
        state_tests.ControllerStateTest.setUp(self)
        self.server=self.service.make_server(self.app)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def http(self,method,path,body=None,token=True,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        self.addCleanup(connection.close)
        h={'Authorization':'Bearer '+self.token} if token else {}
        h.update(headers or {})
        if body is not None:h['Content-Type']='application/json'
        connection.request(method,path,json.dumps(body) if body is not None else None,h)
        response=connection.getresponse();return response.status,json.loads(response.read())

    def test_http_auth_host_origin_and_privacy(self):
        path='/controller/v1/snapshot?deviceId=device'
        self.assertEqual(self.http('GET',path,token=False)[0],401)
        self.assertEqual(self.http('GET',path,headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.http('GET',path,headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.http('GET',path,headers={'Sec-Fetch-Site':'cross-site'})[0],403)
        code,snapshot=self.http('GET',path);self.assertEqual(code,200)
        self.assertTrue(self.app.contract.validate('snapshot',snapshot))
        self.assertNotIn(self.token,json.dumps(snapshot))

    def test_http_command_feed_and_revocation(self):
        cursor=self.app.snapshot()['cursor']
        code,receipt=self.http('POST','/controller/v1/commands',self.request());self.assertEqual(code,202)
        self.assertTrue(self.app.contract.validate('receipt',receipt))
        code,events=self.http('GET',f"/controller/v1/feed?deviceId=device&epoch={cursor['epoch']}&sequence={cursor['sequence']}")
        self.assertEqual(code,200);self.assertTrue(events)
        self.assertTrue(all(self.app.contract.validate('feed',event) for event in events))
        self.service.revoke(self.directory,b=self.app.b,principal='client')
        self.assertEqual(self.http('GET','/controller/v1/devices')[0],401)

    def test_http_strict_parser_and_body_limit(self):
        code,_=self.http('POST','/controller/v1/commands',dict(self.request(),raw='secret'))
        self.assertEqual(code,400)
        code,_=self.http('POST','/controller/v1/commands',{'large':'x'*65536})
        self.assertEqual(code,429)
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        self.addCleanup(connection.close)
        connection.request('POST','/controller/v1/commands','{"a":1,"a":2}',{'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        self.assertEqual(connection.getresponse().status,400)

    def test_browser_mode_post_invalidates_native_snapshot(self):
        from http.server import ThreadingHTTPServer
        from types import SimpleNamespace
        from unittest.mock import patch
        import wall_server
        native=self.request()
        browser=ThreadingHTTPServer(('127.0.0.1',0),wall_server.handler(SimpleNamespace(b=self.app.b,directory=self.directory),'wall-test-token'))
        browser.app=SimpleNamespace(b=self.app.b)
        worker=threading.Thread(target=browser.serve_forever,daemon=True);worker.start()
        try:
            connection=http.client.HTTPConnection('127.0.0.1',browser.server_port,timeout=3)
            origin=f'http://127.0.0.1:{browser.server_port}'
            with patch.object(self.app.b,'launch_worker',return_value=None):
                connection.request('POST','/api/mode',json.dumps({'mode':'free'}),{'Origin':origin,'X-Wall-Token':'wall-test-token','Content-Type':'application/json'})
                response=connection.getresponse();self.assertEqual(response.status,200);response.read()
            connection.close()
            code,receipt=self.http('POST','/controller/v1/commands',native)
            self.assertEqual(code,409);self.assertEqual(receipt['failure']['code'],'revision-conflict')
        finally:browser.shutdown();browser.server_close();worker.join()

    def test_read_scope_and_actual_simultaneous_command_clients(self):
        token=self.service.issue(self.directory,self.app.b,'reader',['read'])
        self.assertEqual(self.http('POST','/controller/v1/commands',self.request(),headers={'Authorization':'Bearer '+token})[0],403)
        request=self.request();other=dict(request,command={'kind':'mode.set','mode':'Free'})
        results=[]
        threads=[threading.Thread(target=lambda value=value:results.append(self.http('POST','/controller/v1/commands',value))) for value in (request,other)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sorted(code for code,_ in results),[202,409])

    def test_thread_and_feed_admission_limits(self):
        for _ in range(32):self.assertTrue(self.server.slots.acquire(False))
        try:
            connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
            connection.request('GET','/controller/v1/devices')
            self.assertEqual(connection.getresponse().status,429);connection.close()
        finally:
            for _ in range(32):self.server.slots.release()
        for _ in range(16):self.assertTrue(self.server.feed_slots.acquire(False))
        try:self.assertEqual(self.http('GET','/controller/v1/feed?deviceId=device')[0],429)
        finally:
            for _ in range(16):self.server.feed_slots.release()

    def test_incomplete_body_times_out_without_reservation(self):
        before=self.app.snapshot()['nextRequestId']
        client=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=3)
        try:
            client.sendall((f'POST /controller/v1/commands HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\nAuthorization: Bearer {self.token}\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n{{').encode())
            self.assertEqual(client.recv(1024),b'')
        finally:client.close()
        self.assertEqual(self.app.snapshot()['nextRequestId'],before)
