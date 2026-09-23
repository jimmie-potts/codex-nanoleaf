import copy
import json
from pathlib import Path
import unittest

from test_bridge import b

ROOT = Path(__file__).resolve().parents[1]

class SharedContractTest(unittest.TestCase):
    def test_released_fixture_corpus(self):
        import shared_input
        corpus = json.loads((ROOT / 'bridge/vendor/agent-state-1.0.0/package/fixtures/snapshots-v1.json').read_text())
        for case in corpus['cases']:
            with self.subTest(case=case['id']):
                self.assertEqual(shared_input.validate_snapshot(case['input'])['ok'], case['valid'])

import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def fixture():
    corpus = json.loads((ROOT / 'bridge/vendor/agent-state-1.0.0/package/fixtures/snapshots-v1.json').read_text())
    return copy.deepcopy(corpus['cases'][0]['input'])


def envelope(snapshot=None):
    return {'apiVersion': '1.0', 'ownerId': 'owner', 'connection': 'current',
            'snapshot': snapshot or fixture(), 'admissionRejected': 0, 'nextRequestId': 'request-1'}


class TransportTest(unittest.TestCase):
    def setUp(self):
        import shared_input as s
        self.s = s
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.token = Path(self.temp.name) / 'token'; self.token.write_text('a' * 43); self.token.chmod(0o600)
        self.value = envelope(); self.code = 200; self.requests = []
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                outer.requests.append((self.path, self.headers.get('Authorization')))
                body = getattr(outer, 'raw', None) or json.dumps(outer.value).encode()
                self.send_response(outer.code); self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if getattr(outer, 'drip', False):
                    import time
                    try:
                        for part in body:
                            self.wfile.write(bytes([part])); self.wfile.flush(); time.sleep(.05)
                    except (OSError, BrokenPipeError): pass
                else: self.wfile.write(body)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.config = {'version': 1, 'ownerId': 'owner', 'consumerId': 'nanoleaf',
                       'endpoint': f'http://127.0.0.1:{self.server.server_port}/api/monitor/v1',
                       'tokenFile': str(self.token), 'clearOnNewTurn': True,
                       'qualifiedSources': [{'provider': 'codex', 'client': 'desktop', 'hostId': 'host', 'sourceId': 'source'}],
                       'bindings': []}

    def test_authenticated_snapshot(self):
        result = self.s.fetch_snapshot(self.config)
        self.assertEqual(result, envelope())
        self.assertEqual(self.requests, [('/api/monitor/v1/sessions', 'Bearer ' + 'a'*43)])

    def test_invalid_feed_is_content_free(self):
        for mutation in ('owner', 'private', 'revision', 'redirect'):
            with self.subTest(mutation=mutation):
                self.value = envelope(); self.code = 200
                if mutation == 'owner': self.value['ownerId'] = 'other'
                if mutation == 'private': self.value['snapshot']['sessions'][0]['prompt'] = 'SECRET'
                if mutation == 'revision': self.value['snapshot']['revision'] = 1
                if mutation == 'redirect': self.code = 302
                with self.assertRaises(self.s.FeedError) as raised:
                    self.s.fetch_snapshot(self.config, minimum_revision=2)
                self.assertNotIn('SECRET', str(raised.exception))
                self.assertNotIn('a'*43, str(raised.exception))

    def test_total_deadline_bounds_dripping_body(self):
        import time
        self.drip=True
        started=time.monotonic()
        with patch.object(self.s,'TIMEOUT',.15), self.assertRaises(self.s.FeedError):
            self.s.fetch_snapshot(self.config)
        self.assertLess(time.monotonic()-started,.7)

    def test_duplicate_keys_and_size_limit(self):
        self.raw=b'{"apiVersion":"1.0","apiVersion":"1.0"}'
        with self.assertRaises(self.s.FeedError):self.s.fetch_snapshot(self.config)
        del self.raw
        with patch.object(self.s,'MAX_RESPONSE',32),self.assertRaises(self.s.FeedError):self.s.fetch_snapshot(self.config)

    def test_configuration_rejects_remote_targets_and_unqualified_sources(self):
        for key, value in [('endpoint','http://example.com/api/monitor/v1'), ('endpoint','http://127.0.0.1:42/api/monitor/v1?x=1'), ('clearOnNewTurn',False), ('qualifiedSources',[])]:
            with self.subTest(key=key,value=value):
                config = dict(self.config, **{key:value})
                with self.assertRaises(self.s.FeedError): self.s.validate_config(config)

import contextlib
from unittest.mock import patch


class SelectionTest(unittest.TestCase):
    def setUp(self):
        import shared_input as s
        self.s=s; self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name); self.instant=1000.0
        self.config={'version':1,'ownerId':'owner','consumerId':'nanoleaf',
                     'endpoint':'http://127.0.0.1:12345/api/monitor/v1','tokenFile':str(self.path/'token'),
                     'clearOnNewTurn':True,'qualifiedSources':[{'provider':'codex','client':'desktop','hostId':'host','sourceId':'source'}],
                     'bindings':[{'identity':fixture()['sessions'][0]['identity'],'legacySessionId':'legacy'}]}
        b.handle_event(self.path,{'session_id':'legacy','turn_id':'turn','hook_event_name':'UserPromptSubmit'},launch=lambda _:None,now=lambda:self.instant)
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute("INSERT INTO slots (session, slot) VALUES ('legacy',0)")
            db.execute("INSERT INTO projects VALUES ('project','LOCAL TITLE','#112233','[]')")
            db.execute("UPDATE task_info SET project='project',manual_project='project' WHERE session='legacy'")
        self.s.configure(self.path,b,self.config)

    def select(self, value=None):
        return self.s.select_source(self.path,b,'shared',fetch=lambda config,minimum_revision=0:value or envelope(),now=lambda:self.instant)

    def rows(self, sql):
        with contextlib.closing(b.connect_state(self.path)) as db:
            return db.execute(sql).fetchall()

    def test_atomic_cutover_identity_and_legacy_suppression(self):
        self.assertEqual(self.s.inspect(self.path)['source'],'legacy')
        value=envelope(); value['snapshot']['sessions'][0]['activity']='active'
        self.select(value); key=self.s.identity_key(fixture()['sessions'][0]['identity'])
        self.assertEqual(self.rows('SELECT id,status FROM sessions'),[(key,'working')])
        self.assertEqual(self.rows('SELECT session,slot FROM slots'),[(key,0)])
        self.assertEqual(self.rows('SELECT started FROM activity'),[(1000.0,)])
        b.handle_event(self.path,{'session_id':'legacy','turn_id':'bad','hook_event_name':'UserPromptSubmit'},launch=lambda _:None)
        self.assertEqual(self.rows('SELECT id,status FROM sessions'),[(key,'working')])
        view=self.s.inspect(self.path)
        self.assertEqual(view['source'],'shared'); self.assertNotIn('LOCAL TITLE',json.dumps(view))
        self.assertNotIn(str(self.path),json.dumps(view)); self.assertNotIn('tokenFile',json.dumps(view))
        self.assertEqual(self.rows('SELECT * FROM comets'),[])

    def test_failed_preflight_and_comet_reservation_preserve_legacy(self):
        with self.assertRaises(self.s.FeedError): self.s.select_source(self.path,b,'shared',fetch=lambda *a,**k:(_ for _ in ()).throw(self.s.FeedError('feed-unavailable')))
        self.assertEqual(self.s.inspect(self.path)['source'],'legacy')
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute("INSERT INTO comets (session, turn, queued, source, started) VALUES ('legacy','turn',1000,0,1000)")
        with self.assertRaises(self.s.FeedError):self.select()
        self.assertEqual(self.rows('SELECT id FROM sessions'),[('legacy',)])

    def test_rollback_preserves_mode_and_current_bound_assignment(self):
        self.select(); key=self.s.identity_key(fixture()['sessions'][0]['identity'])
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute('UPDATE slots SET slot=2 WHERE session=?',(key,))
            db.execute("INSERT OR REPLACE INTO meta VALUES ('mode','free')")
        self.s.select_source(self.path,b,'legacy',now=lambda:1005)
        self.assertEqual(self.rows('SELECT id,status FROM sessions'),[('legacy','working')])
        self.assertEqual(self.rows('SELECT session,slot FROM slots'),[('legacy',2)])
        self.assertEqual(self.rows("SELECT value FROM meta WHERE key='mode'"),[('free',)])
        self.assertEqual(self.s.inspect(self.path)['source'],'legacy')
        self.assertEqual(self.rows('SELECT * FROM comets'),[])

    def test_notices_read_and_same_project_concurrency(self):
        value=envelope(); value['snapshot']['sessions'][0]['activity']='active'
        self.select(value)
        value=copy.deepcopy(value);value['snapshot']['revision']=3
        session=value['snapshot']['sessions'][0];session['activity']='idle';session['notices'][0]['acknowledgedBy'].append('nanoleaf')
        self.s.accept(self.path,b,value,now=lambda:1001)
        self.assertEqual(self.rows('SELECT status FROM sessions'),[('idle',)])
        value['snapshot']['revision']=4;session['notices'][0]['acknowledgedBy']=['pixoo'];session['read']='read'
        self.s.accept(self.path,b,value,now=lambda:1002)
        self.assertEqual(self.rows('SELECT status FROM sessions'),[('idle',)])
        session['read']='unknown';session['projectId']='chosen';other=copy.deepcopy(session);other['identity']['sessionId']='other'
        value['snapshot']['sessions'].append(other);value['snapshot']['revision']=5
        self.s.accept(self.path,b,value,now=lambda:1003)
        self.assertEqual(len(self.rows('SELECT id FROM sessions')),2)
        self.assertEqual(len(self.rows('SELECT DISTINCT project FROM task_info')),1)

    def test_inspection_missing_state_does_not_create_files(self):
        fresh=self.path/'fresh';fresh.mkdir()
        self.assertEqual(self.s.inspect(fresh)['source'],'legacy')
        self.assertEqual(list(fresh.iterdir()),[])

class RecoveryTest(SelectionTest):
    def test_loss_freezes_colors_and_reconnect_preserves_epoch(self):
        value=envelope();value['snapshot']['sessions'][0]['activity']='active';self.select(value)
        epoch=self.rows('SELECT started FROM activity')
        generation=self.s.source_config(self.path,b)['generation']
        self.s.failed(self.path,b,generation)
        config={'line_groups':[[100,101]],'line_positions':[[0,0]],'_mode':'work'}
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            snapshot=b.dashboard(db,config,1001)
            self.s.render_config(db,config)
        from test_bridge import decode as decode_effect
        panels=decode_effect(b.effect_payload(config,snapshot,1001,True))
        self.assertEqual({tuple(frame[:3]) for frame in panels[100]}, {b.COLORS['working']})
        self.s.accept(self.path,b,value,now=lambda:1002,resync=True)
        self.assertEqual(self.rows('SELECT started FROM activity'),epoch)
        self.assertEqual(self.rows('SELECT * FROM comets'),[])

    def test_uncertain_snapshot_retains_last_color_and_recovery_no_old_comet(self):
        value=envelope();value['snapshot']['sessions'][0]['activity']='active';self.select(value)
        value=copy.deepcopy(value);value['snapshot']['revision']=3
        session=value['snapshot']['sessions'][0];session['activity']='idle'
        session['restartUncertain']=True;session['freshness']='uncertain'
        self.s.accept(self.path,b,value,now=lambda:1001)
        self.assertEqual(self.rows('SELECT status FROM sessions'),[('working',)])
        self.assertEqual(self.rows('SELECT * FROM comets'),[])

    def test_stale_peer_does_not_suppress_healthy_outward_wave(self):
        value=envelope();healthy=value['snapshot']['sessions'][0];healthy['activity']='active'
        stale=copy.deepcopy(healthy);stale['identity']['sessionId']='stale'
        stale['freshness']='uncertain';stale['restartUncertain']=True
        value['snapshot']['sessions'].append(stale);self.select(value)
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute('INSERT INTO slots (session, slot) VALUES (?,1)',(self.s.identity_key(stale['identity']),))
        value=copy.deepcopy(value);value['snapshot']['revision']+=1
        value['snapshot']['sessions'][0]['turn']={'status':'known','id':'next'}
        self.s.accept(self.path,b,value,now=lambda:1001)
        layout={'line_groups':[[100,101],[102,103],[104,105]],'line_positions':[[0,0],[1,0],[2,0]],'_mode':'work'}
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            snapshot=b.dashboard(db,layout,1002);self.s.render_config(db,layout)
        delays=[b.travel_delays(layout,i) for i in range(3)]
        expected=b.pixel_color([snapshot[0],None,None],2,1002,delays)
        self.assertNotEqual(expected,b.BASELINE)
        self.assertEqual(b.zone_color(layout,snapshot,2,0,1002,delays),expected)

    def test_recovered_session_keeps_epoch_without_replaying_outward_wave(self):
        value=envelope();value['snapshot']['sessions'][0]['activity']='active';self.select(value)
        value=copy.deepcopy(value);value['snapshot']['revision']+=1
        session=value['snapshot']['sessions'][0];session['turn']={'status':'known','id':'next'}
        self.s.accept(self.path,b,value,now=lambda:1001)
        session['freshness']='uncertain';session['restartUncertain']=True
        self.s.accept(self.path,b,value,now=lambda:1001.1)
        session['freshness']='current';session['restartUncertain']=False
        self.s.accept(self.path,b,value,now=lambda:1001.2)
        layout={'line_groups':[[100,101],[102,103]],'line_positions':[[0,0],[1,0]],'_mode':'work'}
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            snapshot=b.dashboard(db,layout,1002);self.s.render_config(db,layout)
        delays=[b.travel_delays(layout,i) for i in range(2)]
        self.assertEqual(self.rows('SELECT started FROM activity'),[(1001,)])
        self.assertEqual(b.zone_color(layout,snapshot,1,0,1002,delays),b.BASELINE)
        self.assertEqual(b.zone_color(layout,snapshot,0,0,1002,delays),b.pixel_color(snapshot,0,1002,delays))

    def test_read_during_comet_retains_source_until_finish(self):
        value=envelope();self.select(value)
        key=self.s.identity_key(value['snapshot']['sessions'][0]['identity'])
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute('INSERT INTO comets (session, turn, queued, source, started) VALUES (?,?,?,0,?)',(key,'turn',1000,1000))
        value=copy.deepcopy(value);value['snapshot']['revision']+=1
        value['snapshot']['sessions'][0]['read']='read'
        self.s.accept(self.path,b,value,now=lambda:1000.5)
        self.assertEqual(self.rows('SELECT session,source,started FROM comets'),[(key,0,1000)])
        self.assertEqual(self.rows('SELECT status FROM sessions'),[('idle',)])

    def test_new_turn_cancels_active_old_notice_comet(self):
        value=envelope();self.select(value)
        key=self.s.identity_key(value['snapshot']['sessions'][0]['identity'])
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute('INSERT INTO comets (session, turn, queued, source, started) VALUES (?,?,?,0,?)',(key,'turn',1000,1000))
        value=copy.deepcopy(value);value['snapshot']['revision']+=1
        session=value['snapshot']['sessions'][0]
        session['turn']={'status':'known','id':'next'};session['activity']='active'
        session['notices'][0]['acknowledgedBy'].append('nanoleaf')
        self.s.accept(self.path,b,value,now=lambda:1001)
        self.assertEqual(self.rows('SELECT * FROM comets'),[])
        self.assertEqual(self.rows('SELECT status FROM sessions'),[('working',)])

    def test_delayed_poll_cannot_overwrite_rollback(self):
        self.select()
        generation=self.s.source_config(self.path,b)['generation']
        self.s.select_source(self.path,b,'legacy',now=lambda:1001)
        self.assertFalse(self.s.accept(self.path,b,envelope(),generation=generation))
        self.s.failed(self.path,b,generation)
        self.assertEqual(self.rows('SELECT id FROM sessions'),[('legacy',)])
        self.assertEqual(self.s.inspect(self.path)['source'],'legacy')

    def test_worker_polls_in_free_without_reading_local_metadata(self):
        value=envelope();value['snapshot']['sessions'][0]['activity']='active';self.select(value)
        b.write_json(self.path/'config.json',{'ip':'192.0.2.1','token':'fake'})
        b.write_json(self.path/'layout.json',{'line_groups':[[100,101]],'line_positions':[[0,0]]})
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('mode','free')")
        calls=[]
        def fetch(config,minimum_revision=0):
            calls.append(1)
            if len(calls)==2:raise KeyboardInterrupt()
            return value
        with patch.object(self.s,'fetch_snapshot',side_effect=fetch), patch.object(b.wall.Metadata,'refresh',side_effect=AssertionError('local metadata read')), self.assertRaises(KeyboardInterrupt):
            b.run_worker(self.path,send=lambda *a: self.fail('Free light write'),scene_factory=None,read_unread=lambda:self.fail('legacy unread read'))
        self.assertEqual(len(calls),2)

class CommandTest(SelectionTest):
    def test_status_is_pure_and_configure_does_not_select(self):
        import io
        output=io.StringIO()
        with patch.object(b.sys,'argv',['bridge.py','shared-status','--state-dir',str(self.path)]),contextlib.redirect_stdout(output):
            b.main()
        self.assertEqual(json.loads(output.getvalue())['source'],'legacy')

    def test_acknowledgment_persists_exact_request_and_never_marks_read(self):
        self.config['controlTokenFile']=str(self.path/'control-token')
        self.s.configure(self.path,b,self.config);self.select()
        key=self.s.identity_key(fixture()['sessions'][0]['identity'])
        notice='a'*64; requests=[]
        def post(config,suffix,body=None,control=False):
            requests.append(copy.deepcopy(body))
            if len(requests)==1:raise self.s.FeedError('feed-unavailable')
            return {'ok':True,'revision':3,'outcome':'applied'}
        with patch.object(self.s,'fetch_snapshot',return_value=envelope()),patch.object(self.s,'request',side_effect=post):
            with self.assertRaises(self.s.FeedError):self.s.acknowledge(self.path,b,key,notice)
            with self.assertRaises(self.s.FeedError):self.s.acknowledge(self.path,b,key,notice)
            self.s.acknowledge(self.path,b,key,notice,retry=True)
        self.assertEqual(len(requests),2);self.assertEqual(requests[0],requests[1])
        self.assertEqual(requests[0]['consumerId'],'nanoleaf')
        self.assertEqual(requests[0]['requestId'],'request-1')
        self.assertEqual(self.rows('SELECT status FROM sessions'),[( 'unread',)])
        self.assertEqual(self.s.source_config(self.path,b)['envelope']['snapshot']['sessions'][0]['read'],'unknown')

class ReleaseTest(unittest.TestCase):
    def test_pinned_archive_and_extracted_files(self):
        import hashlib
        import tarfile
        package=ROOT/'bridge/vendor/agent-state-1.0.0'
        archive=package/'jimmie-potts-agent-state-1.0.0.tgz'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),'ae589d311e282c3356579c85507a3aa973ab7990e06e062143aeb08d8d2dcc99')
        with tarfile.open(archive) as tar:
            for path in (package/'package').rglob('*'):
                if not path.is_file() or '__pycache__' in path.parts:continue
                with self.subTest(path=str(path.relative_to(package))):
                    self.assertEqual(path.read_bytes(),tar.extractfile(path.relative_to(package).as_posix()).read())

    def test_released_owner_clears_only_nanoleaf_on_evidenced_new_turn(self):
        import subprocess
        import tarfile
        with tempfile.TemporaryDirectory() as temporary:
            archive=ROOT/'bridge/vendor/agent-state-1.0.0/jimmie-potts-agent-state-1.0.0.tgz'
            with tarfile.open(archive) as tar:tar.extractall(temporary,filter='data')
            module=(Path(temporary)/'package/dist/index.js').as_uri()
            program='''
import {createAgentState,MemoryStorage} from MODULE;
const owner=await createAgentState({storage:new MemoryStorage(),ownerId:'owner',consumers:[{id:'nanoleaf',clearOnNewTurn:true},{id:'pixoo',clearOnNewTurn:false}],clock:()=>1000});
const identity={provider:'codex',client:'desktop',hostId:'host',sourceId:'source',sessionId:'session'};
let sequence=0;
for(const [kind,turn] of [['turn.started','one'],['turn.ended','one'],['turn.started','two']]) {
 const result=await owner.ingest({apiVersion:'1.0',identity,turn:{status:'known',id:turn},parent:{status:'unknown'},event:{kind},observedAtMs:1000,ordering:{status:'known',epoch:'epoch',sequence:++sequence}});
 if(!result.ok)throw Error('ingestion failed');
}
console.log(JSON.stringify(owner.snapshot()));await owner.shutdown();
'''.replace('MODULE',json.dumps(module))
            result=subprocess.run(['node','--input-type=module','-e',program],cwd=temporary,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            snapshot=json.loads(result.stdout)
            import shared_input as s
            self.assertTrue(s.validate_snapshot(snapshot)['ok'])
            session=snapshot['sessions'][0]
            self.assertEqual(session['notices'][0]['acknowledgedBy'],['nanoleaf'])
            self.assertEqual(session['read'],'unknown')
            self.assertEqual(s.semantic_status(session,'nanoleaf'),'working')

class StartupTest(SelectionTest):
    def test_wall_start_resumes_only_selected_shared_worker(self):
        import wall_server
        config={'line_groups':[[100,101]],'line_positions':[[0,0]]}
        launches=[]
        wall_server.App(self.path,b,config=config,launch=lambda path:launches.append(path))
        self.assertEqual(launches,[])
        self.select()
        wall_server.App(self.path,b,config=config,launch=lambda path:launches.append(path))
        self.assertEqual(launches,[self.path])


class DeviceSwitchTest(unittest.TestCase):
    # #43 AC2 and AC3: switching keeps each device's bound placement; comets follow device modes.
    setUp=SelectionTest.setUp; select=SelectionTest.select; rows=SelectionTest.rows

    def test_switching_preserves_bound_placements_on_every_device(self):
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute("INSERT INTO slots (session, slot, device) VALUES ('legacy',4,'panels')")
        self.select(); key=self.s.identity_key(fixture()['sessions'][0]['identity'])
        self.assertEqual(sorted(self.rows('SELECT session,slot,device FROM slots')),[(key,0,'wall'),(key,4,'panels')])
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute("UPDATE slots SET slot=7 WHERE session=? AND device='panels'",(key,))
            db.execute("UPDATE slots SET slot=2 WHERE session=? AND device='wall'",(key,))
        self.s.select_source(self.path,b,'legacy',now=lambda:1005)
        self.assertEqual(sorted(self.rows('SELECT session,slot,device FROM slots')),[('legacy',2,'wall'),('legacy',7,'panels')])

    def test_shared_completion_queues_comets_on_registered_work_devices(self):
        b.write_json(self.path/'config.json',{'ip':'192.0.2.1','token':'fake','panelsToken':'other','devices':{
            'panels':{'kind':'panels','ip':'192.0.2.2','token_ref':'panelsToken'}}})
        b.set_mode(self.path,'quiet',launch=lambda _:None,device='panels')
        def complete(revision):
            active=envelope(); first=active['snapshot']['sessions'][0]; notice=first['notices'].pop()
            first['activity']='active'; active['snapshot']['revision']=revision
            done=copy.deepcopy(active); done['snapshot']['revision']=revision+1
            second=done['snapshot']['sessions'][0]; second['activity']='idle'; second['notices']=[notice]
            return active,done
        active,done=complete(1)
        self.select(active)
        self.s.accept(self.path,b,done,now=lambda:1001)
        self.assertEqual(self.rows('SELECT device FROM comets'),[('wall',)])
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute('DELETE FROM comets')
        b.set_mode(self.path,'work',launch=lambda _:None,device='panels')
        active,done=complete(3)
        self.s.accept(self.path,b,active,now=lambda:1002)
        self.s.accept(self.path,b,done,now=lambda:1003)
        self.assertEqual(sorted(self.rows('SELECT device FROM comets')),[('panels',),('wall',)])
