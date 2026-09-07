import contextlib
import importlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from test_bridge import b


class ControllerStateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.state = importlib.import_module('controller_state')
        self.service = importlib.import_module('controller_server')
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO activity VALUES ('task','turn','working',42)")
        self.service.configure(self.directory, b, 'controller', 'device', 'source')
        self.token = self.service.issue(self.directory, b, 'client', ['read','control'])
        self.app = self.service.App(self.directory, b, launch=lambda _: None)

    def request(self, mode='Quiet'):
        s = self.app.snapshot()
        return dict(apiVersion='1.0', controllerId='controller', deviceId='device', requestId=s['nextRequestId'],
                    expectedConfigurationRevision=s['configurationRevision'], expectedGeneration=s['generation'],
                    command={'kind':'mode.set','mode':mode})

    def test_snapshot_is_pure_and_strict(self):
        before = (self.directory/'status.sqlite').read_bytes()
        snap = self.app.snapshot()
        self.assertTrue(self.app.contract.validate('snapshot', snap))
        self.assertEqual(snap['state']['observation'], {'status':'unknown'})
        self.assertEqual((self.directory/'status.sqlite').read_bytes(), before)
        self.assertFalse(snap['capabilities']['brightness']['supported'])

    def test_atomic_duplicate_conflict_and_browser_staleness(self):
        request = self.request()
        first = self.app.admit(self.token, request)
        self.assertEqual(first[1]['outcome'], 'queued')
        self.assertEqual(self.app.admit(self.token, request), first)
        changed = dict(request, command={'kind':'mode.set','mode':'Free'})
        self.assertEqual(self.app.admit(self.token, changed)[0], 409)
        stale = self.request('Free')
        b.set_mode(self.directory,'work', launch=lambda _: None)
        self.assertEqual(self.app.admit(self.token, stale)[1]['failure']['code'], 'revision-conflict')
        with contextlib.closing(b.connect_state(self.directory)) as db:
            self.assertEqual(db.execute('SELECT started FROM activity').fetchone(), (42,))

    def test_two_clients_reserve_at_most_one(self):
        req = self.request(); other = dict(req, command={'kind':'mode.set','mode':'Free'})
        results=[]
        threads=[threading.Thread(target=lambda r=r: results.append(self.app.admit(self.token,r))) for r in (req,other)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sorted(r[0] for r in results), [202,409])

    def test_revocation_precedes_replay(self):
        req=self.request(); self.app.admit(self.token,req)
        self.service.revoke(self.directory,b,'client')
        self.assertEqual(self.app.admit(self.token,req)[0],401)

    def test_capacity_before_reservation_semantic_failure_retained_and_expired(self):
        request=self.request()
        request['expectedConfigurationRevision']=900
        code,receipt=self.app.admit(self.token,request)
        self.assertEqual(code,409);self.assertEqual(self.app.admit(self.token,request),(200,receipt))
        next_request=self.request()
        next_request['requestId']['sequence']+=1
        self.assertEqual(self.app.admit(self.token,next_request)[1]['failure']['code'],'request-order')
        before=self.app.snapshot()['nextRequestId']
        self.assertEqual(self.app.admit(self.token,self.request(),65537)[1]['failure']['code'],'capacity')
        self.assertEqual(self.app.snapshot()['nextRequestId'],before)
        with contextlib.closing(b.connect_state(self.directory)) as db,db:db.execute('DELETE FROM controller_requests')
        self.assertEqual(self.app.admit(self.token,request)[1]['failure']['code'],'request-expired')

    def test_feed_bounds_and_clock_restart_preserve_old_evidence(self):
        cursor=self.app.snapshot()['cursor']
        for i in range(40):b.set_mode(self.directory,'quiet' if i%2 else 'work',launch=lambda _:None)
        events=self.app.feed(cursor)
        self.assertEqual(len(events),1);self.assertEqual(events[0]['kind'],'resync')
        self.assertEqual(self.app.feed(self.app.snapshot()['cursor']),[])
        with contextlib.closing(self.state.readonly(self.directory)) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM controller_events').fetchone()[0],32)

    def test_pending_deadline_and_launch_failure_are_bounded(self):
        request=self.request();self.app.admit(self.token,request)
        with contextlib.closing(b.connect_state(self.directory)) as db,db:
            created=db.execute('SELECT created FROM controller_requests').fetchone()[0]
            self.state.recover(db,now=created+31)
        self.assertEqual(self.app.snapshot()['state']['lastOutcome']['receipt']['failure']['code'],'transport-failure')
        app=self.service.App(self.directory,b,launch=lambda _: (_ for _ in ()).throw(OSError('private/path token')))
        code,receipt=app.admit(self.token,self.request('Free'))
        self.assertEqual(code,503);self.assertEqual(receipt['priorEffects'],'none')
        self.assertNotIn('private',json.dumps(receipt))

    def test_generation_recheck_between_operations_preserves_prior_transmission(self):
        request=self.request();self.app.admit(self.token,request)
        with contextlib.closing(b.connect_state(self.directory)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            execution=self.state.Execution(db,b.control_state(db)['revision'])
            sent=[];execution.call(lambda:sent.append('first'))
            db.commit()
            b.set_mode(self.directory,'free',launch=lambda _:None)
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(self.state.Cancelled):execution.call(lambda:sent.append('second'))
            self.assertEqual(sent,['first'])
            receipt=json.loads(db.execute('SELECT receipt FROM controller_requests').fetchone()[0])
            self.assertEqual(receipt['outcome'],'cancelled');self.assertEqual(receipt['priorEffects'],'confirmed-transmission')

    def test_revocation_between_operations_holds_mode_and_retains_evidence(self):
        self.app.admit(self.token,self.request())
        with contextlib.closing(b.connect_state(self.directory)) as db,db:
            db.execute('BEGIN IMMEDIATE');execution=self.state.Execution(db,b.control_state(db)['revision'])
            execution.call(lambda:None);db.commit()
            self.service.revoke(self.directory,b,'client')
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaises(self.state.Cancelled):execution.call(lambda:self.fail('Revoked operation sent.'))
            receipt=json.loads(db.execute('SELECT receipt FROM controller_requests').fetchone()[0])
            self.assertEqual(receipt['outcome'],'cancelled');self.assertEqual(receipt['priorEffects'],'confirmed-transmission')
            self.assertTrue(self.state.held(db,b.control_state(db)['revision']))

    def test_owning_listener_restart_rotates_clock_not_old_transmission_evidence(self):
        from unittest.mock import patch
        with contextlib.closing(b.connect_state(self.directory)) as db,db:
            data=self.state.read(db);old_clock=self.state.clock(data)
            data['lastSuccessfulSend']=dict(status='known',requestId=self.state.ticket(data,0),clock=old_clock,operationIds=['transport-1'])
            self.state.save(db,data)
        previous=self.app.snapshot()['sampleClock']['epoch']
        for _ in range(2):
            started=threading.Event();original=b.write_json
            def notify(path,value):original(path,value);started.set()
            with patch.object(b,'write_json',side_effect=notify):
                thread=threading.Thread(target=self.service.serve,args=(self.directory,b),daemon=True);thread.start()
                self.assertTrue(started.wait(5))
                try:
                    snap=self.app.snapshot()
                    self.assertNotEqual(snap['sampleClock']['epoch'],previous)
                    self.assertEqual(snap['state']['lastSuccessfulSend']['clock'],old_clock)
                    previous=snap['sampleClock']['epoch']
                finally:
                    with contextlib.closing(b.connect_state(self.directory)) as db,db:
                        data=self.state.read(db);data['stopped']=True;self.state.save(db,data)
                    thread.join(3)
                    self.assertFalse(thread.is_alive())

    def test_snapshot_and_feed_use_one_read_transaction(self):
        from unittest.mock import patch
        # WAL lets the concurrent writer commit while the reader retains its snapshot.
        with contextlib.closing(b.connect_state(self.directory)) as db:db.execute('PRAGMA journal_mode=WAL')
        for observe in (self.app.snapshot,lambda:self.app.feed(None)[0]['snapshot']):
            before=self.app.snapshot();request=self.request('Quiet' if before['state']['desired']['mode']['value']=='Work' else 'Work')
            original=self.state.read;written=False
            def read_then_write(db):
                nonlocal written
                result=original(db)
                if not written:
                    written=True
                    self.app.admit(self.token,request)
                return result
            with patch.object(self.state,'read',read_then_write):observed=observe()
            for field in ('configurationRevision','generation','nextRequestId','cursor','state'):
                self.assertEqual(observed[field],before[field],field)
            self.assertNotEqual(self.app.snapshot()['generation'],before['generation'])

    def test_deadline_during_validation_or_before_commit_rolls_back(self):
        from unittest.mock import patch
        for hook in ('validation','commit'):
            with self.subTest(hook=hook):
                before=self.app.snapshot();request=self.request();clock=[0]
                target=self.app.contract if hook=='validation' else self.state
                name='admit' if hook=='validation' else 'event'
                original=getattr(target,name)
                def expire(*args,**kwargs):
                    result=original(*args,**kwargs);clock[0]=6;return result
                with patch.object(self.service.time,'monotonic',lambda:clock[0]),patch.object(target,name,expire),patch.object(self.app,'launch') as launch:
                    with self.assertRaises(TimeoutError):self.app.admit(self.token,request,deadline=5)
                    launch.assert_not_called()
                after=self.app.snapshot()
                for field in ('configurationRevision','generation','nextRequestId','cursor','state'):
                    self.assertEqual(after[field],before[field],field)

    def test_committed_admission_survives_deadline_before_launch_returns(self):
        from unittest.mock import patch
        request=self.request();clock=[0]
        def launch(_):clock[0]=6
        with patch.object(self.service.time,'monotonic',lambda:clock[0]),patch.object(self.app,'launch',launch):
            code,receipt=self.app.admit(self.token,request,deadline=5)
        self.assertEqual(code,202);self.assertEqual(receipt['outcome'],'queued')
        self.assertEqual(self.app.snapshot()['state']['pending'][0]['requestId'],request['requestId'])

    def test_commit_wait_respects_remaining_admission_budget(self):
        import sqlite3
        import time
        from unittest.mock import patch
        before=self.app.snapshot();request=self.request()
        with contextlib.closing(self.state.readonly(self.directory)) as reader:
            self.state.read(reader)  # Keep a rollback-journal reader across commit.
            with patch.object(self.app,'launch') as launch:
                with self.assertRaises(sqlite3.OperationalError):
                    self.app.admit(self.token,request,deadline=time.monotonic()+.1)
                launch.assert_not_called()
        after=self.app.snapshot()
        for field in ('configurationRevision','generation','nextRequestId','cursor','state'):
            self.assertEqual(after[field],before[field],field)

    @contextlib.contextmanager
    def watchdog_listener(self, connect=None):
        from unittest.mock import patch
        class Listener:
            server_port=43210
            def __init__(self):self.started=threading.Event();self.stopped=threading.Event()
            def serve_forever(self,**kwargs):self.started.set();self.stopped.wait(15)
            def shutdown(self):self.stopped.set()
            def server_close(self):pass
        listener=Listener()
        with patch.object(self.service,'make_server',return_value=listener),patch.object(b,'connect_state',connect or b.connect_state):
            thread=threading.Thread(target=self.service.serve,args=(self.directory,b),daemon=True);thread.start()
            self.assertTrue(listener.started.wait(5))
            try:yield listener
            finally:
                listener.shutdown();thread.join(4)
                self.assertFalse(thread.is_alive())

    def test_watchdog_retries_real_writer_contention_then_expires_and_disables(self):
        import time
        from unittest.mock import patch
        self.app.admit(self.token,self.request())
        with contextlib.closing(b.connect_state(self.directory)) as db,db:
            db.execute('UPDATE controller_requests SET created=?',(time.time()-31,))
        attempted=threading.Event();original=b.connect_state
        def connect(directory):
            attempted.set();return original(directory)
        with self.watchdog_listener() as listener:
            with contextlib.closing(original(self.directory)) as writer:
                writer.execute('BEGIN IMMEDIATE')
                with patch.object(b,'connect_state',connect):
                    self.assertTrue(attempted.wait(2))
                    self.assertFalse(listener.stopped.wait(3.1),'Transient writer contention stopped the listener.')
                writer.rollback()
            deadline=time.monotonic()+3
            while self.app.snapshot()['state']['pending'] and time.monotonic()<deadline:time.sleep(.05)
            self.assertEqual(self.app.snapshot()['state']['lastOutcome']['receipt']['failure']['code'],'transport-failure')
            self.service.command(['controller-disable','--state-dir',str(self.directory)],b)
            self.assertTrue(listener.stopped.wait(3),'Disable was not observed after retry.')

    def test_watchdog_retries_locked_but_stops_on_other_failures(self):
        import sqlite3
        for code in (sqlite3.SQLITE_LOCKED,sqlite3.SQLITE_BUSY | (2<<8),sqlite3.SQLITE_IOERR,None):
            with self.subTest(code=code):
                calls=[0];retried=threading.Event();original=b.connect_state
                error=sqlite3.OperationalError('Synthetic database failure') if code else RuntimeError('Synthetic fatal failure')
                if code:error.sqlite_errorcode=code
                def connect(directory):
                    calls[0]+=1
                    if calls[0]==2:raise error
                    if calls[0]>2:retried.set()
                    return original(directory)
                with self.watchdog_listener(connect) as listener:
                    if code is not None and code & 255 in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED):
                        self.assertTrue(retried.wait(3),'Transient error was not retried.')
                        self.assertFalse(listener.stopped.is_set())
                    else:
                        self.assertTrue(listener.stopped.wait(3),'Fatal error did not stop listener.')
                        self.assertFalse(retried.is_set())
