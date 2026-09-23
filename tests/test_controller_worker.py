import unittest
import contextlib
import json
from unittest.mock import patch
import test_scene_restore as scenes
from test_bridge import b
import controller_server as server


class ControllerWorkerTest(unittest.TestCase):
    run_worker=scenes.SceneTest.run_worker
    query=scenes.SceneTest.query
    def setUp(self):
        scenes.SceneTest.setUp(self)
        server.configure(self.directory,b,'controller','device','source')
        self.token=server.issue(self.directory,b,'client',['read','control'])
        self.app=server.App(self.directory,b,launch=lambda _:None)

    def command(self,mode):
        snap=self.app.snapshot()
        req=dict(apiVersion='1.0',controllerId='controller',deviceId='device',requestId=snap['nextRequestId'],
                 expectedConfigurationRevision=snap['configurationRevision'],expectedGeneration=snap['generation'],command=dict(kind='mode.set',mode=mode))
        return self.app.admit(self.token,req)

    def last(self):return self.app.snapshot()['state']['lastOutcome']['receipt']

    def test_machine_quiet_records_actual_transmission(self):
        self.command('Quiet')
        self.run_worker([(1001,lambda:b.set_mode(self.directory,'free',launch=lambda _:None,now=self.clock.now))])
        receipt=json.loads(self.query('SELECT receipt FROM controller_requests WHERE sequence=0')[0][0])
        self.assertEqual(receipt['outcome'],'sent')
        self.assertEqual(receipt['priorEffects'],'confirmed-transmission')
        self.assertTrue(receipt['completedOperations'])

    def test_same_free_noop_never_sends(self):
        b.set_mode(self.directory,'free',launch=lambda _:None,now=self.clock.now);self.run_worker()
        self.device.calls.clear();code,receipt=self.command('Free')
        self.assertEqual(receipt['outcome'],'cancelled');self.assertEqual(receipt['priorEffects'],'none')
        self.assertEqual(self.device.calls,[])

    def test_uncertain_transport_is_not_retried_by_worker(self):
        self.command('Quiet')
        self.device.fail=lambda method,endpoint,payload:method=='PUT'
        with self.assertRaises(OSError):self.run_worker()
        self.assertEqual(self.last()['outcome'],'uncertain')
        calls=list(self.device.calls)
        self.run_worker()
        self.assertEqual(self.device.calls,calls)

    def test_worker_restart_marks_attempt_uncertain(self):
        self.command('Quiet')
        with contextlib.closing(b.connect_state(self.directory)) as db,db:
            receipt=json.loads(db.execute('SELECT receipt FROM controller_requests').fetchone()[0])
            receipt['uncertainOperations']=['transport-1']
            db.execute("UPDATE controller_requests SET phase='attempting',receipt=?",(json.dumps(receipt),))
        self.run_worker()
        self.assertEqual(self.last()['outcome'],'uncertain');self.assertEqual(self.device.calls,[])

    def test_cli_worker_automatic_retry_keeps_hold_and_explicit_same_mode_retries(self):
        import sys
        self.command('Quiet')
        self.device.fail=lambda method,endpoint,payload:method=='PUT'
        original=b.run_worker
        def run(directory,device='wall',feed=None):
            return original(directory,sleep=self.clock.sleep,now=self.clock.now,read_unread=lambda:self.unread,device=device,feed=feed)
        with patch.object(sys,'argv',['bridge.py','worker','--state-dir',str(self.directory)]), patch.object(b,'run_worker',side_effect=run) as worker, patch.object(b.time,'sleep',return_value=None):
            b.main()
        self.assertEqual(worker.call_count,2)
        self.assertEqual(sum(method=='PUT' for _,method,_,_ in self.device.calls),1)
        b.set_mode(self.directory,'quiet',launch=lambda _:None,now=self.clock.now)
        self.run_worker([(1001,lambda:b.set_mode(self.directory,'free',launch=lambda _:None,now=self.clock.now))])
        self.assertGreater(sum(method=='PUT' for _,method,_,_ in self.device.calls),1)

    def test_partial_failure_retains_completed_operations(self):
        b.handle_event(self.directory,dict(hook_event_name='UserPromptSubmit',session_id='a',turn_id='1'),launch=lambda _:None,now=self.clock.now)
        self.command('Quiet')
        self.device.fail=lambda method,endpoint,payload:method=='PUT' and endpoint=='/state'
        with self.assertRaises(OSError):self.run_worker()
        receipt=self.last()
        self.assertEqual(receipt['outcome'],'partially-applied')
        self.assertEqual(receipt['priorEffects'],'confirmed-transmission')
        self.assertEqual(receipt['completedOperations'],['transport-1'])
        self.assertEqual(receipt['uncertainOperations'],['transport-2'])
        self.assertTrue(self.app.contract.validate('receipt',receipt))

    def test_revoked_unsent_mode_cannot_run_as_legacy_work(self):
        self.command('Quiet');server.revoke(self.directory,b,'client')
        self.run_worker()
        self.assertEqual(self.device.calls,[])

    def test_revocation_during_observe_cannot_fall_back_to_legacy_send(self):
        self.command('Quiet')
        revoked=False
        def request(config,method,endpoint='',payload=None):
            nonlocal revoked
            if method=='GET' and not revoked:
                revoked=True
                server.revoke(self.directory,b,'client')
            return self.device.request(config,method,endpoint,payload)
        with patch.object(b,'light_request',request):self.run_worker()
        self.assertTrue(revoked)
        self.assertEqual([call for call in self.device.calls if call[1]=='PUT'],[])
        self.assertEqual(self.last()['priorEffects'],'none')

    def test_expiry_during_unread_cannot_fall_back_to_legacy_send(self):
        import controller_state as state
        self.command('Quiet')
        def unread():
            with contextlib.closing(b.connect_state(self.directory)) as db,db:
                state.recover(db,now=float('inf'))
            return self.unread
        b.run_worker(self.directory,sleep=self.clock.sleep,now=self.clock.now,read_unread=unread)
        self.assertEqual([call for call in self.device.calls if call[1]=='PUT'],[])
        self.assertEqual(self.last()['priorEffects'],'none')

    def test_disable_during_observe_cannot_fall_back_to_legacy_send(self):
        self.command('Quiet');disabled=False
        def request(config,method,endpoint='',payload=None):
            nonlocal disabled
            if method=='GET' and not disabled:
                disabled=True
                server.command(['controller-disable','--state-dir',str(self.directory)],b)
            return self.device.request(config,method,endpoint,payload)
        with patch.object(b,'light_request',request):self.run_worker()
        self.assertTrue(disabled)
        self.assertEqual([call for call in self.device.calls if call[1]=='PUT'],[])
        self.assertEqual(self.last()['priorEffects'],'none')
