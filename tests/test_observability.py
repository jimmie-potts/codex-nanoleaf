"""Optional packaged host diagnostics, with isolated output and fake transports."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
import diagnostics


class DiagnosticsTest(unittest.TestCase):
    def test_disabled_is_inert_and_enabled_uses_canonical_records(self):
        lines = []
        disabled = diagnostics.start('nanoleaf-controller', environ={}, local_sink=lines.append)
        disabled.event('process.started')
        disabled.close()
        self.assertEqual(lines, [])
        host = diagnostics.start('nanoleaf-controller', environ={'BUNNY_DIAGNOSTICS':'1'}, local_sink=lines.append)
        with host.operation('bunny.controller', 'brightness'):
            host.receipt({'requestId':{'epoch':'a'*32,'sequence':1}, 'outcome':'queued'})
        host.close()
        records = [json.loads(line) for line in lines]
        self.assertTrue(records)
        self.assertTrue(all(r['resource']['service.name'] == 'nanoleaf-controller' for r in records))
        self.assertIn('queued', [r['attributes'].get('bunny.outcome') for r in records])
        self.assertTrue(all(diagnostics.load()[0].validate_record(r)['ok'] for r in records))

    def test_modified_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / 'vendor'
            shutil.copytree(diagnostics.ROOT, copied)
            (copied / 'package/python/bunny_observability/host.py').write_text('broken')
            with self.assertRaises(ValueError): diagnostics.verify(copied)

    def test_bad_configuration_and_missing_worker_sink_are_inert(self):
        for env in ({'BUNNY_DIAGNOSTICS':'1'}, {'BUNNY_DIAGNOSTICS':'1','BUNNY_OTLP_ORIGIN':'https://example.com'}):
            host = diagnostics.start('nanoleaf-worker', environ=env)
            self.assertFalse(host.enabled)
            with host.operation('bunny.controller','brightness'): pass
            host.close()



class WorkerDiagnosticsTest(unittest.TestCase):
    def test_fake_worker_preserves_receipt_and_emits_ticket(self):
        import test_controller_controls as controls
        from test_bridge import b
        fixture = controls.ControlsTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.mode('free')
        # Settle the existing Free handoff before admitting a one-shot command.
        fixture.run_worker()
        req, (code, queued) = fixture.command({'kind':'brightness.set', 'percent':37})
        self.assertEqual(code, 202)
        lines = []
        host = diagnostics.start('nanoleaf-controller', environ={'BUNNY_DIAGNOSTICS':'1'}, local_sink=lines.append)
        b.run_worker(fixture.directory, now=fixture.clock.now, sleep=fixture.clock.sleep,
                     read_unread=lambda: set(), request=fixture.device.request, diagnostic=host)
        host.close()
        receipt = fixture.app.admit(fixture.token, req)[1]
        self.assertEqual(receipt['outcome'], 'sent')
        records = [json.loads(line) for line in lines]
        matched = [r for r in records if r['attributes'].get('bunny.ticket.sequence') == req['requestId']['sequence']]
        self.assertTrue(matched)
        self.assertIn('transport-acknowledged', [r['attributes'].get('bunny.outcome') for r in matched])

class HTTPDiagnosticsTest(unittest.TestCase):
    def test_authenticated_concurrent_contexts_and_owned_thread(self):
        import http.client
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        import test_controller_api as api
        received = []
        class Collector(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{}')
        collector = ThreadingHTTPServer(('127.0.0.1', 0), Collector)
        thread = threading.Thread(target=collector.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (collector.shutdown(),collector.server_close(),thread.join()))
        lines = []
        host = diagnostics.start('nanoleaf-controller', environ={'BUNNY_DIAGNOSTICS':'1', 'BUNNY_TRACING':'1',
            'BUNNY_OTLP_ORIGIN':f'http://127.0.0.1:{collector.server_port}'}, local_sink=lines.append)
        self.addCleanup(host.close)
        fixture = api.ControllerHTTPTest(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        fixture.app.diagnostic = host
        path = '/controller/v1/snapshot?deviceId=device'
        identities = ['1'*32, '2'*32]
        statuses = []
        def request(identity):
            connection = http.client.HTTPConnection('127.0.0.1', fixture.server.server_port, timeout=3)
            try:
                connection.request('GET', path, headers={'Authorization':'Bearer '+fixture.token,
                    'traceparent':f'00-{identity}-{"3"*16}-01'})
                response = connection.getresponse();statuses.append(response.status);response.read()
            finally:connection.close()
        clients = [threading.Thread(target=request,args=(identity,)) for identity in identities]
        for client in clients:client.start()
        for client in clients:client.join()
        self.assertEqual(statuses,[200,200])
        self.assertEqual(fixture.http('GET',path,token=False,headers={'traceparent':f'00-{"4"*32}-{"3"*16}-01'})[0],401)
        with host.operation('bunny.controller','status',traceparent=f'00-{"5"*32}-{"6"*16}-01',authenticated=True,owned=True):
            captured=host.capture_context()
            def owned():
                with host.run_context(captured):
                    with host.operation('bunny.queue','status'):pass
            child=threading.Thread(target=owned);child.start();child.join()
        host.close()
        records=[json.loads(line) for line in lines]
        traces={r.get('trace_id') for r in records if 'trace_id' in r}
        self.assertEqual(traces,set(identities+['5'*32]))
        handoff=[r for r in records if r.get('trace_id')=='5'*32]
        self.assertEqual(len(handoff),2)
        spans=[s for payload in received for resource in payload.get('resourceSpans',[]) for scope in resource['scopeSpans'] for s in scope['spans']]
        self.assertEqual(len(spans),4)
        self.assertTrue(all(any(s['spanId']==r['span_id'] and s['traceId']==r['trace_id'] for s in spans) for r in records if 'trace_id' in r))

    def test_copied_consumer_conformance_and_no_dependency_disabled_import(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(diagnostics.ROOT, root/'vendor/observability-1.1.0')
            shutil.copyfile(Path(diagnostics.__file__), root/'diagnostics.py')
            result = subprocess.run([sys.executable,'-S','-c',"import diagnostics; assert not diagnostics.start('nanoleaf-worker',environ={}).enabled"], cwd=root, capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result = subprocess.run([sys.executable,'-m','unittest','discover','-s',str(root/'vendor/observability-1.1.0/package/tests'),'-p','test_conformance.py'], cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

class FailureDiagnosticsTest(unittest.TestCase):
    def test_absent_collector_preserves_one_write_and_uncertain_failure(self):
        import socket
        import test_controller_controls as controls
        from test_bridge import b
        # Reserve a loopback port without listening: no other owner's endpoint is contacted.
        with socket.socket() as unused:
            unused.bind(('127.0.0.1',0))
            for fail in (False, True):
                fixture=controls.ControlsTest();fixture.setUp()
                try:
                    fixture.mode('free');fixture.run_worker()
                    req,(code,_)=fixture.command({'kind':'brightness.set','percent':37})
                    self.assertEqual(code,202)
                    before=len(fixture.puts())
                    host=diagnostics.start('nanoleaf-worker',environ={'BUNNY_DIAGNOSTICS':'1','BUNNY_TRACING':'1',
                        'BUNNY_OTLP_ORIGIN':f'http://127.0.0.1:{unused.getsockname()[1]}'})
                    self.assertTrue(host.enabled)
                    self.addCleanup(host.close)
                    def request(*args,**kwargs):
                        if fail and args[1]=='PUT':
                            fixture.device.calls.append((fixture.clock.now(),args[1],args[2],args[3]))
                            raise TimeoutError('fake uncertain send')
                        return fixture.device.request(*args,**kwargs)
                    def run():
                        return b.run_worker(fixture.directory,now=fixture.clock.now,sleep=fixture.clock.sleep,
                            read_unread=lambda:set(),request=request,diagnostic=host)
                    if fail:
                        with self.assertRaises(TimeoutError):run()
                    else:run()
                    host.close()
                    receipt=fixture.app.admit(fixture.token,req)[1]
                    self.assertEqual(receipt['outcome'],'uncertain' if fail else 'sent')
                    self.assertEqual(diagnostics.outcome(receipt),'uncertain' if fail else 'transport-acknowledged')
                    self.assertEqual(len(fixture.puts())-before,1)
                    run()  # A failed/held or completed ticket cannot replay a device write.
                    self.assertEqual(len(fixture.puts())-before,1)
                    counts=host.counts()
                    self.assertGreater(counts['transports'][0]['failed'],0)
                finally:fixture.doCleanups()

    def test_stalled_sink_does_not_hold_the_device_command(self):
        import threading
        import time
        import test_controller_controls as controls
        from test_bridge import b
        fixture=controls.ControlsTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.mode('free');fixture.run_worker()
        req,(code,_)=fixture.command({'kind':'brightness.set','percent':37})
        self.assertEqual(code,202)
        release=threading.Event();entered=threading.Event()
        def sink(line):
            entered.set();release.wait(5)
        host=diagnostics.start('nanoleaf-controller',environ={'BUNNY_DIAGNOSTICS':'1'},local_sink=sink)
        try:
            self.assertTrue(entered.wait(1))
            before=len(fixture.puts())
            b.run_worker(fixture.directory,now=fixture.clock.now,sleep=fixture.clock.sleep,
                         read_unread=lambda:set(),request=fixture.device.request,diagnostic=host)
            self.assertEqual(fixture.app.admit(fixture.token,req)[1]['outcome'],'sent')
            self.assertEqual(len(fixture.puts())-before,1)
            started=time.monotonic();host.close()
            self.assertLess(time.monotonic()-started,1.5)
            self.assertGreater(host.counts()['logs']['dropped'],0)
        finally:
            release.set();host.close()

    def test_shared_packaged_failure_and_queue_checks(self):
        import subprocess
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(diagnostics.ROOT/'package/tests'),'-p','test_host.py'],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

class DetachedDiagnosticsTest(unittest.TestCase):
    def test_detached_cli_exports_without_stdout_or_stderr(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import os
        import subprocess
        import threading
        received=[]
        class Collector(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{}')
        server=ThreadingHTTPServer(('127.0.0.1',0),Collector)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            env={**os.environ,'BUNNY_DIAGNOSTICS':'1','BUNNY_TRACING':'1','BUNNY_OTLP_ORIGIN':f'http://127.0.0.1:{server.server_port}'}
            result=subprocess.run([sys.executable,str(Path(__file__).parent/'fixtures/observability_worker.py')],
                env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                close_fds=True,start_new_session=True,timeout=10)
            self.assertEqual(result.returncode,0)
            groups=[resource for payload in received for resource in payload.get('resourceLogs',[])]
            logs=[log for resource in groups for scope in resource['scopeLogs'] for log in scope['logRecords']]
            self.assertTrue(groups)
            for resource in groups:
                fields={a['key']:a['value'] for a in resource['resource']['attributes']}
                self.assertEqual(fields['service.name'],{'stringValue':'nanoleaf-worker'})
            attributes=[{a['key']:next(iter(a['value'].values())) for a in log['attributes']} for log in logs]
            self.assertIn('process.started',[log.get('eventName') for log in logs])
            self.assertIn('process.stopped',[log.get('eventName') for log in logs])
            commands=[a for a in attributes if a.get('bunny.outcome')=='transport-acknowledged']
            self.assertEqual(len(commands),1)
            self.assertIn('bunny.ticket.epoch',commands[0]);self.assertIn('bunny.ticket.sequence',commands[0])
        finally:
            server.shutdown();server.server_close();thread.join()


class ControllerLifecycleDiagnosticsTest(unittest.TestCase):
    def test_watchdog_reports_fatal_errors_but_retries_busy_without_failure(self):
        import sqlite3
        import threading
        from unittest.mock import patch
        import database
        import test_controller_state as fixtures
        for code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_IOERR, None):
            with self.subTest(code=code):
                fixture=fixtures.ControllerStateTest();fixture.setUp()
                lines=[]
                host=diagnostics.start('nanoleaf-controller',environ={'BUNNY_DIAGNOSTICS':'1'},local_sink=lines.append)
                calls=[0];retried=threading.Event();original=database.connect_state
                error=sqlite3.OperationalError('private synthetic failure') if code else RuntimeError('private synthetic failure')
                if code:error.sqlite_errorcode=code
                def connect(directory):
                    calls[0]+=1
                    if calls[0]==2:raise error
                    if calls[0]>2:retried.set()
                    return original(directory)
                try:
                    with patch.object(diagnostics,'start',return_value=host):
                        with fixture.watchdog_listener(connect) as listener:
                            if code in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED):
                                self.assertTrue(retried.wait(3))
                                self.assertFalse(listener.stopped.is_set())
                            else:self.assertTrue(listener.stopped.wait(3))
                    records=[json.loads(line) for line in lines]
                    events=[r['event_name'] for r in records]
                    self.assertEqual(events.count('process.failed'),0 if code in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED) else 1)
                    self.assertEqual(events[-1],'process.stopped')
                    self.assertNotIn('private synthetic failure',''.join(lines))
                finally:
                    host.close();fixture.doCleanups()


if __name__ == '__main__': unittest.main()
