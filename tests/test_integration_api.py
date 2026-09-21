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

    def test_python_typescript_consumer_fixtures(self):
        import integration_api
        from pathlib import Path
        import subprocess
        root = Path(__file__).resolve().parents[1]
        fixtures = json.loads((root / 'contracts/integration-v1/fixtures.json').read_text())
        for case in fixtures['requests']:
            with self.subTest(case=case['name']):
                try:
                    integration_api.validate(case['request']); valid = True
                except integration_api.Failure:
                    valid = False
                self.assertEqual(valid, case['valid'])
        result = subprocess.run(['node', '--experimental-strip-types', str(root / 'contracts/integration-v1/check.ts')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['requests'], len(fixtures['requests']))

    def test_wall_pending_desired_values_are_sanitized(self):
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute('INSERT INTO map_pending VALUES (1,?)', (json.dumps({'settings':{'style':'project'}, 'lines':{'101:102':{'project':'/private/project'}}, 'tasks':{'private-session':'/private/project'}}),))
        before = (self.directory / 'status.sqlite').read_bytes()
        view = self.app.integration_snapshot(self.token, 'device')
        self.assertEqual(view['wallPending']['settings'], {'style':'project'})
        self.assertEqual(view['wallPending']['elements'][0]['projectId'], view['projects'][0]['id'])
        self.assertEqual(view['wallPending']['tasks'][0]['taskId'], view['tasks'][0]['id'])
        self.assertNotIn('/private', json.dumps(view))
        self.assertEqual(before, (self.directory / 'status.sqlite').read_bytes())

    def test_all_operations_preserve_unrelated_state_and_scene(self):
        scene = b'{"scene":"PRIVATE_SCENE"}'
        (self.directory / 'scene-state.json').write_bytes(scene)
        view = self.app.integration_snapshot(self.token, 'device'); p = view['projects'][0]['id']; t = view['tasks'][0]['id']
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO receipts VALUES ('private-session','turn',10,0)")
        commands = [dict(kind='settings.set', style='project', coverage='status'),
                    dict(kind='elements.assign', elements=[dict(id='101:102', projectId=p, signature=1)]),
                    dict(kind='task.assign', taskId=t, projectId=p),
                    dict(kind='project.color', projectId=p, color='#AABBCC')]
        for command in commands:
            req = self.request(command)
            self.assertEqual(self.app.integration_admit(self.token, req)[0], 202)
            self.process()
            self.assertEqual(self.app.integration_admit(self.token, req)[1]['outcome'], 'applied')
        view = self.app.integration_snapshot(self.token, 'device')
        self.assertEqual(view['projects'][0]['color'], '#aabbcc')
        self.assertEqual(view['tasks'][0]['overrideProjectId'], p)
        self.assertEqual(view['elements'][0], dict(id='101:102',projectId=p,signature=1))
        self.assertEqual(view['elements'][1], dict(id='103:104',projectId=None,signature=0))
        self.assertEqual(view['source'], 'legacy')
        self.assertEqual((self.directory / 'scene-state.json').read_bytes(), scene)
        with contextlib.closing(self.state.readonly(self.directory)) as db:
            self.assertEqual(db.execute('SELECT started FROM activity').fetchone(), (42,))
            self.assertEqual(db.execute('SELECT observed FROM receipts').fetchone(), (0,))

    def test_concurrent_wall_edit_wins_without_overwrite(self):
        import wall_server
        import threading
        app = wall_server.App(self.directory, b, config=self.config, launch=lambda _:None)
        req = self.request(); barrier = threading.Barrier(2); results = []
        def native():
            barrier.wait(); results.append(self.app.integration_admit(self.token, req)[0])
        def wall():
            barrier.wait(); app.update('/api/settings', {'coverage':'status'})
        threads = [threading.Thread(target=native), threading.Thread(target=wall)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.process()
        view = self.app.integration_snapshot(self.token, 'device')
        self.assertIn(results[0], (202,409))
        self.assertEqual(view['settings'], dict(style='classic', coverage='status'))

    def test_capacity_expired_identity_and_deadline_do_not_apply(self):
        import time
        req = self.request()
        before = self.app.integration_snapshot(self.token, 'device')['nextRequestId']
        self.assertEqual(self.app.integration_admit(self.token, req, 65537)[0], 429)
        with self.assertRaises(TimeoutError):
            self.app.integration_admit(self.token, req, deadline=time.monotonic()-1)
        self.assertEqual(self.app.integration_snapshot(self.token, 'device')['nextRequestId'], before)
        self.app.integration_admit(self.token, req)
        self.assertEqual(self.app.integration_admit(self.token, self.request())[0], 429)
        self.process()
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute('DELETE FROM integration_requests')
        self.assertEqual(self.app.integration_admit(self.token, req)[0], 410)

    def test_launch_failure_and_cancel_after_commit_preserve_effect_evidence(self):
        req = self.request()
        self.app.launch = lambda _: (_ for _ in ()).throw(OSError('PRIVATE_PATH_TOKEN'))
        code, receipt = self.app.integration_admit(self.token, req)
        self.assertEqual(code, 503)
        self.assertEqual(receipt['priorEffects'], 'none')
        self.assertNotIn('PRIVATE', json.dumps(receipt))
        self.app.launch = lambda _: None
        req = self.request(); self.app.integration_admit(self.token, req); self.process()
        receipt = self.app.integration_cancel(self.token, 'device', req['requestId'])[1]
        self.assertEqual(receipt['outcome'], 'applied')
        self.assertEqual(receipt['priorEffects'], 'configuration')

    def test_shared_mapping_source_and_notices_survive_edits(self):
        import shared_input
        import test_shared_input
        env = test_shared_input.envelope(); session = env['snapshot']['sessions'][0]
        sid = shared_input.identity_key(session['identity']); pid = session.get('projectId') or 'chosen-project'
        session['projectId'] = pid
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("UPDATE shared_input SET source='shared',envelope=?,generation=2", (json.dumps(env),))
            db.execute('INSERT INTO projects VALUES (?,?,?,?)', ('shared-project-'+pid,pid,'#aabbcc','[]'))
            db.execute('INSERT INTO task_info VALUES (?,?,?,?,?,?,?)', (sid,'PRIVATE_SHARED_TITLE','PRIVATE_SHARED_ROOT','shared-project-'+pid,None,'turn',42))
        before = (self.directory / 'status.sqlite').read_bytes()
        view = self.app.integration_snapshot(self.token, 'device')
        task = next(t for t in view['tasks'] if 'sharedIdentity' in t)
        project = next(p for p in view['projects'] if 'sharedProjectId' in p)
        self.assertEqual(task['sharedIdentity'], session['identity'])
        self.assertEqual(project['sharedProjectId'], pid)
        self.assertNotIn('PRIVATE', json.dumps(view))
        self.assertEqual(before, (self.directory / 'status.sqlite').read_bytes())
        req = self.request(dict(kind='task.assign', taskId=task['id'], projectId=project['id']))
        self.app.integration_admit(self.token, req); self.process()
        with contextlib.closing(self.state.readonly(self.directory)) as db:
            current = shared_input.state(db)
            self.assertEqual(current['source'], 'shared')
            self.assertEqual(current['envelope'], env)

    def test_restart_expiry_rotation_disable_and_transport_hold(self):
        import integration_api
        import time
        req = self.request(); self.app.integration_admit(self.token, req)
        # Recreate only the listener facade; its reads must not execute queued work.
        self.app = self.service.App(self.directory, b, launch=lambda _:None)
        before = (self.directory / 'status.sqlite').read_bytes()
        self.assertEqual(integration_api.receipt(self.app,self.token,'device',req['requestId'])['outcome'], 'queued')
        self.assertEqual(before, (self.directory / 'status.sqlite').read_bytes())
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('controller_hold_revision','0')")
        self.process(time.time()+31)
        self.assertEqual(self.app.integration_admit(self.token,req)[1]['outcome'], 'failed')
        with contextlib.closing(self.state.readonly(self.directory)) as db:
            self.assertEqual(db.execute("SELECT value FROM meta WHERE key='controller_hold_revision'").fetchone(), ('0',))
        req = self.request(); self.app.integration_admit(self.token,req)
        self.token = self.service.issue(self.directory,b,'client',['read','control'])
        self.assertEqual(self.app.integration_admit(self.token,req)[1]['outcome'], 'cancelled')
        req = self.request(); self.app.integration_admit(self.token,req)
        self.service.command(['controller-disable','--state-dir',str(self.directory)], b)
        with contextlib.closing(self.state.readonly(self.directory)) as db:
            receipt=json.loads(db.execute('SELECT receipt FROM integration_requests WHERE sequence=?',(req['requestId']['sequence'],)).fetchone()[0])
            self.assertEqual(receipt['outcome'],'cancelled')

    def test_worker_cancel_race_has_atomic_evidence(self):
        import threading
        req = self.request(); self.app.integration_admit(self.token,req)
        barrier = threading.Barrier(2); outcomes=[]
        def cancel():
            barrier.wait(); outcomes.append(self.app.integration_cancel(self.token,'device',req['requestId'])[1])
        def apply():
            barrier.wait(); self.process()
        threads=[threading.Thread(target=cancel),threading.Thread(target=apply)]
        for t in threads:t.start()
        for t in threads:t.join()
        receipt=self.app.integration_admit(self.token,req)[1]
        self.assertIn(receipt['outcome'],('cancelled','applied'))
        expected='project' if receipt['outcome']=='applied' else 'classic'
        self.assertEqual(self.app.integration_snapshot(self.token,'device')['settings']['style'],expected)
        self.assertEqual(receipt['priorEffects'],'configuration' if expected=='project' else 'none')


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
