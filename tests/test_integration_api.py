import contextlib
import importlib
import json
import unittest
from unittest.mock import patch
import test_controller_state as baseline
from test_bridge import b


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        baseline.ControllerStateTest.setUp(self)
        self.config = {'line_groups': [[101, 102], [103, 104]]}
        b.write_json(self.directory / 'config.json', self.config)
        b.write_json(self.directory / 'layout.json', {'line_groups': self.config['line_groups']})
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO projects VALUES ('/private/project', 'PRIVATE_TITLE', '#112233', '[\"/private/root\"]')")
            db.execute("INSERT INTO task_info VALUES ('private-session','PRIVATE_TASK','/private/root','/private/project',NULL,'turn',42)")
            db.execute("INSERT INTO sessions VALUES ('private-session','turn','working',42)")

    def test_snapshot_is_private_and_byte_pure(self):
        before = (self.directory / 'status.sqlite').read_bytes()
        with patch.object(b, 'load_config', side_effect=AssertionError('not a pure read')), patch.object(b, 'launch_worker', side_effect=AssertionError('read launched work')):
            view = self.app.integration_snapshot(self.token, 'device')
        raw = json.dumps(view)
        for secret in ('/private', 'PRIVATE_TITLE', 'PRIVATE_TASK', 'private-session', self.token):
            self.assertNotIn(secret, raw)
        self.assertEqual(view['apiVersion'], 'nanoleaf.integration/1.0')
        self.assertEqual(view['elements'][0]['id'], '101:102')
        self.assertEqual(view['settings']['style'], 'classic')
        self.assertEqual(before, (self.directory / 'status.sqlite').read_bytes())
        self.assertEqual(view['revision'], self.app.integration_snapshot(self.token, 'device')['revision'])

    def request(self, command=None):
        view = self.app.integration_snapshot(self.token, 'device')
        return dict(apiVersion=view['apiVersion'], controllerId='controller', deviceId='device',
                    requestId=view['nextRequestId'], expectedRevision=view['revision'],
                    command=command or {'kind': 'settings.set', 'style': 'project'})

    def process(self, now=None):
        import integration_api
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            integration_api.process(db, b, self.config, now=now)

    def test_admission_replay_apply_and_revision(self):
        request = self.request()
        code, receipt = self.app.integration_admit(self.token, request)
        self.assertEqual(code, 202)
        self.assertEqual(receipt['outcome'], 'queued')
        self.assertEqual(self.app.integration_admit(self.token, request), (code, receipt))
        self.assertEqual(self.app.integration_admit(self.token, dict(request, command={'kind':'settings.set','coverage':'status'}))[0], 409)
        self.process()
        code, receipt = self.app.integration_admit(self.token, request)
        self.assertEqual(code, 200)
        self.assertEqual(receipt['outcome'], 'applied')
        self.assertEqual(receipt['priorEffects'], 'configuration')
        self.assertEqual(receipt['physicalOutcome'], 'unknown')
        view = self.app.integration_snapshot(self.token, 'device')
        self.assertEqual(view['settings']['style'], 'project')
        self.assertNotEqual(request['expectedRevision'], view['revision'])
        with contextlib.closing(self.state.readonly(self.directory)) as db:
            self.assertEqual(db.execute('SELECT started FROM activity').fetchone(), (42,))

    def test_principal_scope_and_cross_client_conflict(self):
        req = self.request()
        reader = self.service.issue(self.directory, b, 'reader', ['read'])
        self.assertEqual(self.app.integration_admit(reader, req)[0], 403)
        self.assertEqual(self.app.integration_admit(self.token, dict(req, deviceId='other'))[0], 403)
        self.assertEqual(self.app.integration_admit(self.token, req)[0], 202)
        other = self.service.issue(self.directory, b, 'other', ['read', 'control'])
        self.assertEqual(self.app.integration_admit(other, req)[0], 403)
        b.set_mode(self.directory, 'quiet', launch=lambda _: None)
        self.process()
        result = self.app.integration_admit(self.token, req)[1]
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(result['failure']['code'], 'revision-conflict')
        self.assertEqual(result['priorEffects'], 'none')

    def test_deferred_cancel_revoke_and_expiry(self):
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO comets VALUES ('task','turn',1,0,2)")
        req = self.request()
        self.app.integration_admit(self.token, req)
        self.process()
        self.assertEqual(self.app.integration_admit(self.token, req)[1]['outcome'], 'queued')
        code, receipt = self.app.integration_cancel(self.token, 'device', req['requestId'])
        self.assertEqual(code, 200)
        self.assertEqual(receipt['outcome'], 'cancelled')
        req = self.request()
        self.app.integration_admit(self.token, req)
        self.service.revoke(self.directory, b, 'client')
        self.process()
        self.assertEqual(self.app.integration_admit(self.token, req)[0], 401)
        self.token = self.service.issue(self.directory, b, 'client', ['read','control'])
        req = self.request()
        self.app.integration_admit(self.token, req)
        import time
        self.process(time.time() + 31)
        receipt = self.app.integration_admit(self.token, req)[1]
        self.assertEqual(receipt['failure']['code'], 'request-expired')
        self.assertEqual(receipt['priorEffects'], 'none')

    def test_actual_worker_applies_configuration(self):
        b.write_json(self.directory / 'layout.json', dict(self.config, line_positions=[[0,0],[10,0]]))
        req = self.request()
        self.app.integration_admit(self.token, req)
        sent = []
        b.run_worker(self.directory, send=lambda *args: sent.append(args), read_unread=lambda: None, scene_factory=None)
        self.assertEqual(self.app.integration_admit(self.token, req)[1]['outcome'], 'applied')


class IntegrationHTTPTest(unittest.TestCase):
    setUp = IntegrationTest.setUp
    request = IntegrationTest.request
    process = IntegrationTest.process
    def test_http_extension_guards_and_receipt_reads(self):
        import test_controller_api
        import threading
        self.server = self.service.make_server(self.app)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join()))
        http = lambda *a, **kw: test_controller_api.ControllerHTTPTest.http(self, *a, **kw)
        path = '/controller/integration/v1/snapshot?deviceId=device'
        self.assertEqual(http('GET', path, token=False)[0], 401)
        self.assertEqual(http('GET', path, headers={'Origin':'https://bad.example'})[0], 403)
        self.assertEqual(http('GET', path)[0], 200)
        req = self.request()
        self.assertEqual(http('POST', '/controller/integration/v1/commands', req)[0], 202)
        self.process()
        ticket = req['requestId']
        code, receipt = http('GET', f"/controller/integration/v1/receipt?deviceId=device&epoch={ticket['epoch']}&sequence={ticket['sequence']}")
        self.assertEqual(code, 200)
        self.assertEqual(receipt['outcome'], 'applied')
