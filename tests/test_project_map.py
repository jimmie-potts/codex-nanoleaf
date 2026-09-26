import contextlib
import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import test_scene_restore as fixtures
from test_bridge import b,decode
import transport
import database
import modes
import store
import project_map as w
import wall_server


class ProjectTest(unittest.TestCase):
    setUp=fixtures.SceneTest.setUp
    event=fixtures.SceneTest.event
    query=fixtures.SceneTest.query
    run_worker=fixtures.SceneTest.run_worker

    def projects(self):
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.executemany('INSERT INTO projects VALUES (?,?,?,?)',[
                ('a','Project A','#aa55ff','["/home/tester/projects/a"]'),('b','Project B','#33ccee','["C:/repo/b"]')])
        return wall_server.App(self.directory,self.config,launch=lambda _:None)

    def task(self,sid,project):
        self.event('UserPromptSubmit',sid)
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute('UPDATE task_info SET project=? WHERE session=?',(project,sid))

    def prepare(self):
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            b.prune_comets(db,self.clock.now(),store.control_state(db)['mode'])
            w.apply_pending(db)
            snap=b.dashboard(db,self.config,self.clock.now())
            cfg=copy.deepcopy(self.config);w.render_config(db,cfg,snap)
            return cfg,snap

    def assign(self,app,slots,project):
        app.update('/api/assign',{'lines':{w.line_id(self.config['line_groups'][i]):{'project':project} for i in slots}})

    def test_project_capacity_three_reserved_two_shared(self):
        app=self.projects();self.assign(app,range(3),'a');self.assign(app,range(5,15),'b')
        app.update('/api/settings',{'style':'project'})
        for i in range(5):self.task(str(i),'a')
        self.prepare()
        self.assertEqual({r[0] for r in self.query('SELECT slot FROM slots')},set(range(5)))
        self.task('overflow','a');self.prepare()
        self.assertEqual(self.query("SELECT slot FROM slots WHERE session='overflow'"),[])
        self.assertEqual(next(p for p in app.state()['projects'] if p['id']=='a')['waiting'],1)

    def test_classic_ignores_reservations_and_keeps_saved_settings(self):
        app=self.projects();self.assign(app,range(15),'b');self.task('a','a')
        self.prepare();self.assertEqual(self.query('SELECT slot FROM slots'),[(0,)])
        app.update('/api/settings',{'style':'project'});self.prepare()
        self.assertEqual(self.query('SELECT slot FROM slots'),[])
        app.update('/api/settings',{'style':'classic'});self.prepare()
        self.assertEqual(self.query('SELECT slot FROM slots'),[(0,)])
        self.assertEqual(len(self.query("SELECT * FROM line_prefs WHERE project='b'")),15)

    def test_reassignment_moves_task_without_resetting_epoch(self):
        app=self.projects();self.task('a','a');self.prepare()
        old=self.query('SELECT started FROM activity')
        app.update('/api/settings',{'style':'project'});self.assign(app,[0],'b');self.prepare()
        self.assertEqual(self.query('SELECT slot FROM slots'),[(1,)])
        self.assertEqual(self.query('SELECT started FROM activity'),old)

    def test_active_comet_defers_mapping_and_style(self):
        app=self.projects();self.task('a','a');self.event('Stop','a');self.prepare()
        with contextlib.closing(database.connect_state(self.directory)) as db,db: b.current_comet(db,self.clock.now())
        self.assign(app,[0],'b');app.update('/api/settings',{'style':'project'})
        self.assertIsNotNone(app.state()['pending']);self.assertEqual(app.state()['settings']['style'],'classic')
        self.clock.sleep(2);self.prepare()
        self.assertIsNone(app.state()['pending']);self.assertEqual(app.state()['settings']['style'],'project')
        self.assertEqual(self.query('SELECT slot FROM slots'),[(1,)])

    def test_split_base_status_half_and_swap(self):
        app=self.projects();self.task('a','a');app.update('/api/settings',{'style':'project','coverage':'status'})
        cfg,snap=self.prepare();payload=b.effect_payload(cfg,snap,1010,True);panels=decode(payload)
        self.assertTrue(all(f[:3]==[170,85,255] for f in panels[100]))
        self.assertTrue(all(f[0]==0 and f[2]==0 for f in panels[101]))
        app.update('/api/assign',{'lines':{w.line_id(self.config['line_groups'][0]):{'signature':1}}})
        cfg,snap=self.prepare();panels=decode(b.effect_payload(cfg,snap,1010,True))
        self.assertTrue(all(f[:3]==[170,85,255] for f in panels[101]))

    def test_whole_wave_and_comet_restore_project_color(self):
        app=self.projects();self.task('a','a');app.update('/api/settings',{'style':'project','coverage':'whole'})
        cfg,snap=self.prepare();delays=[b.travel_delays(cfg,i) for i in range(15)]
        self.assertEqual(b.zone_color(cfg,snap,0,0,1000.5,delays),(0,255,0))
        self.assertEqual(b.zone_color(cfg,snap,0,0,1003,delays),(170,85,255))
        cfg['_comet']={'source':0,'started':1004}
        self.assertEqual(b.zone_color(cfg,snap,0,0,1004.05,delays),(255,255,255))
        self.assertEqual(b.zone_color(cfg,snap,0,0,1006,delays),(170,85,255))
        cfg['_coverage']='status'
        self.assertEqual(b.zone_color(cfg,snap,0,0,1004.05,delays),(170,85,255))

    def test_idle_reserved_signature_and_quiet(self):
        app=self.projects();self.assign(app,[0],'a');self.task('b','b')
        app.update('/api/settings',{'style':'project'});cfg,snap=self.prepare();cfg['_mode']='quiet'
        frames=decode(b.effect_payload(cfg,snap,1000,True))
        self.assertEqual(frames[100][0][:3],[170,85,255]);self.assertEqual(frames[101][0][:3],list(b.BASELINE))
        self.assertEqual(len(frames[100]),1)

    def test_color_changes_do_not_restart_task(self):
        app=self.projects();self.task('a','a');app.update('/api/settings',{'style':'project'});cfg,snap=self.prepare()
        before=self.query('SELECT * FROM activity');app.update('/api/project',{'id':'a','color':'#123456'})
        cfg2,snap2=self.prepare();self.assertEqual(before,self.query('SELECT * FROM activity'));self.assertEqual(snap,snap2)
        self.assertNotEqual(cfg['_signatures'],cfg2['_signatures'])

    def test_legacy_untitled_tasks_use_distinct_session_suffixes(self):
        app=self.projects()
        for suffix in ('5b1e07c2','4227761b'):
            self.event('UserPromptSubmit','019a1234-0000-7000-8000-0000'+suffix)
        self.assertEqual(sorted(task['title'] for task in app.state()['tasks']),
                         ['Codex 4227761b','Codex 5b1e07c2'])

    def test_metadata_paths_titles_and_manual_override(self):
        app=self.projects();self.event('UserPromptSubmit','a',cwd='/mnt/c/repo/b/subdir')
        metadata=w.Metadata(self.directory,self.config);metadata.titles={'a':'Actual task title'}
        with contextlib.closing(database.connect_state(self.directory)) as db,db:metadata.sync(db)
        task=app.state()['tasks'][0];self.assertEqual(task['project'],'b');self.assertEqual(task['title'],'Actual task title')
        app.update('/api/task',{'id':'a','project':'a'});self.assertEqual(app.state()['tasks'][0]['project'],'a')
        app.update('/api/task',{'id':'a','project':None});self.assertEqual(app.state()['tasks'][0]['project'],'b')
        self.assertEqual(w.normalize('\\\\wsl.localhost\\Ubuntu\\home\\tester\\projects\\a'),'/home/tester/projects/a')

    def test_metadata_explicit_worktree_and_partial_state_retained(self):
        self.projects();self.task('s',None)
        path=self.directory/'desktop.json';index=self.directory/'index.jsonl'
        value={'local-projects':{'a':{'name':'A','rootPaths':['/repo']}},'thread-project-assignments':{'s':{'projectId':'a'}},'thread-workspace-root-hints':{'s':'/tmp/worktree'}}
        path.write_text(json.dumps(value));index.write_text(json.dumps({'id':'s','thread_name':'Task <name>'})+'\n')
        metadata=w.Metadata(self.directory,dict(self.config,metadata_path=str(path),title_index_path=str(index)))
        metadata.refresh()
        with contextlib.closing(database.connect_state(self.directory)) as db,db: metadata.sync(db)
        path.write_text('{');index.write_text('{')
        metadata.refresh()
        with contextlib.closing(database.connect_state(self.directory)) as db,db: metadata.sync(db)
        self.assertEqual(self.query('SELECT title,project FROM task_info'),[('Task <name>','a')])

    def test_turn_elapsed_not_status_elapsed(self):
        self.projects();self.task('a','a');self.clock.sleep(1);self.event('PermissionRequest','a',tool_name='Bash')
        self.assertEqual(self.query('SELECT started FROM task_info'),[(1000,)])
        self.clock.sleep(1)
        b.handle_event(self.directory,{'hook_event_name':'UserPromptSubmit','session_id':'a','turn_id':'2'},launch=lambda _:None,now=self.clock.now)
        self.assertEqual(self.query('SELECT started FROM task_info'),[(1002,)])

    def test_locate_waits_for_comet_and_free_rejects(self):
        app=self.projects();self.task('a','a');self.event('Stop','a');self.prepare()
        with contextlib.closing(database.connect_state(self.directory)) as db,db: b.current_comet(db,1000)
        app.update('/api/locate',{'line':w.line_id(self.config['line_groups'][3])})
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            self.assertIsNone(w.locate_state(db,self.config,1001,'work'));b.prune_comets(db,1002,'work')
            self.assertEqual(w.locate_state(db,self.config,1002,'work')['source'],3)
            self.assertIsNone(w.locate_state(db,self.config,1003,'work'))
        modes.set_mode(self.directory,'free',launch=lambda _:None)
        with self.assertRaises(ValueError):app.update('/api/locate',{'line':w.line_id(self.config['line_groups'][3])})

    def test_stable_ids_across_layout_reorder(self):
        app=self.projects();self.assign(app,[0],'a')
        cfg=copy.deepcopy(self.config);cfg['line_groups'].reverse()
        with contextlib.closing(database.connect_state(self.directory)) as db:self.assertEqual(w.owners(db,cfg)[-1][0],'a')

    def test_api_validation_and_no_credentials(self):
        app=self.projects();self.task('a','a')
        with self.assertRaises(ValueError):app.update('/api/settings',{'style':'bad'})
        with self.assertRaises(ValueError):app.update('/api/project',{'id':'a','color':'red; script'})
        with self.assertRaises(ValueError):app.update('/api/assign',{'lines':{'unknown':{'project':'a'}}})
        encoded=json.dumps(app.state());self.assertNotIn('PRIVATE_TEST_TOKEN',encoded);self.assertNotIn('PRIVATE CONTENT',encoded)

    def test_rendering_endpoint_is_readonly_and_restart_safe(self):
        app=self.projects()
        receipt={'apiVersion':'1.0','deviceId':'wall','lineGroups':[[100,101]],'mode':'work',
                 'brightness':30,'loop':True,'effect':{'write':{'animData':'1 100 1 0'}},
                 'animationEpochMs':1_000_000,'acceptedAtMs':1_000_650}
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('rendering_receipt',json.dumps(receipt)))
            db.execute("INSERT INTO line_prefs (line_id,project,signature,device) VALUES ('100:101','a',1,'wall')")
        before=(self.query('SELECT * FROM line_prefs'),self.query('SELECT * FROM sessions'),
                self.query('SELECT * FROM comets'),self.query('SELECT * FROM receipts'))
        server=ThreadingHTTPServer(('127.0.0.1',0),wall_server.handler(app,'test-secret'));server.app=app
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url=f'http://127.0.0.1:{server.server_port}'
        with patch.object(app.metadata,'refresh',side_effect=AssertionError('metadata refresh')), \
             patch.object(wall_server,'ensure_geometry',side_effect=AssertionError('geometry acquisition')), \
             patch.object(transport,'light_request',side_effect=AssertionError('controller request')), \
             patch.object(app,'launch',side_effect=AssertionError('worker launch')):
            with urlopen(url+'/api/rendering') as response:
                self.assertEqual(response.status,200)
                self.assertEqual(response.headers.get('Cache-Control'),'no-store')
                snapshot=json.load(response)
            request=Request(url+'/api/rendering',data=b'{"preview":"local-only"}',
                            headers={'Origin':url,'X-Wall-Token':'test-secret',
                                     'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as rejected:urlopen(request)
            self.assertEqual(rejected.exception.code,400);rejected.exception.close()
        self.assertEqual(snapshot['outcome'],'last-sent')
        self.assertEqual(snapshot['lastSuccessful'],receipt)
        self.assertEqual(self.query("SELECT value FROM meta WHERE key='rendering_receipt'"),
                         [(json.dumps(receipt),)])
        self.assertNotIn('PRIVATE_TEST_TOKEN',json.dumps(snapshot))
        self.assertEqual((self.query('SELECT * FROM line_prefs'),self.query('SELECT * FROM sessions'),
                          self.query('SELECT * FROM comets'),self.query('SELECT * FROM receipts')),before)
        restarted=wall_server.App(self.directory,config=self.config,launch=lambda _:None)
        self.assertEqual(restarted.rendering()['lastSuccessful'],receipt)

    def test_rendering_endpoint_reports_pending_failed_free_and_unknown(self):
        app=self.projects()
        receipt={'apiVersion':'1.0','deviceId':'wall','effect':{'write':{'animData':'frames'}}}
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('rendering_receipt',json.dumps(receipt)))
        self.assertEqual(app.rendering()['outcome'],'last-sent')
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('dirty','1')")
        self.assertEqual(app.rendering()['outcome'],'pending')
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute("DELETE FROM meta WHERE key='dirty'")
            db.execute("INSERT OR REPLACE INTO meta VALUES ('control_error','Light update failed; retrying.')")
        self.assertEqual(app.rendering()['outcome'],'failed')
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute("DELETE FROM meta WHERE key='control_error'")
            db.execute("INSERT OR REPLACE INTO meta VALUES ('mode','free')")
        self.assertEqual(app.rendering()['outcome'],'externally-controlled')
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute("DELETE FROM meta WHERE key='rendering_receipt'")
        self.assertEqual(app.rendering()['outcome'],'externally-controlled')
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute("DELETE FROM meta WHERE key='mode'")
        self.assertEqual(app.rendering()['outcome'],'unknown')

    def test_partial_effect_acceptance_keeps_prior_receipt_and_reports_failure(self):
        app=self.projects()
        receipt={'apiVersion':'1.0','deviceId':'wall','effect':{'write':{'animData':'previous'}}}
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('rendering_receipt',json.dumps(receipt)))
        calls=[]
        config={**self.config,'_mode':'work','_now':lambda:2000.0}
        def request(cfg,method,endpoint,payload=None):
            calls.append(endpoint)
            if endpoint=='/state': raise OSError('Brightness update failed after effect acceptance')
        config['_controller_request']=request

        with self.assertRaises(OSError):
            with contextlib.closing(database.connect_state(self.directory)) as db,db:
                b.update_display(db,config,[('working',1999.0)]+[None]*14,2000.0,False)

        self.assertEqual(calls,['/effects','/state'])
        self.assertEqual(json.loads(self.query("SELECT value FROM meta WHERE key='rendering_receipt'")[0][0]),receipt)
        with contextlib.closing(database.connect_state(self.directory)) as db,db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('control_error','Brightness update failed after effect acceptance')")
        snapshot=app.rendering()
        self.assertEqual(snapshot['outcome'],'failed')
        self.assertEqual(snapshot['lastSuccessful'],receipt)
        self.assertTrue(snapshot['failedAttempt'])

    def test_http_origin_host_and_token_checks(self):
        app=self.projects();server=ThreadingHTTPServer(('127.0.0.1',0),wall_server.handler(app,'test-secret'));server.app=app
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url=f'http://127.0.0.1:{server.server_port}'
        with urlopen(url+'/api/state') as response:self.assertEqual(response.status,200)
        with urlopen(url+'/api/rendering') as response:self.assertEqual(response.status,200)
        for headers in ({},{'Origin':'https://example.com','X-Wall-Token':'test-secret'},{'Origin':url,'X-Wall-Token':'wrong'}):
            request=Request(url+'/api/settings',data=b'{"style":"project"}',headers={'Content-Type':'application/json',**headers})
            with self.assertRaises(HTTPError) as error:urlopen(request)
            self.assertEqual(error.exception.code,403);error.exception.close()
        request=Request(url+'/api/settings',data=b'{"style":"project"}',headers={'Content-Type':'application/json','Origin':url,'X-Wall-Token':'test-secret'})
        with urlopen(request) as response:self.assertEqual(response.status,200)
        with self.assertRaises(HTTPError) as error:urlopen(Request(url+'/api/state',headers={'Host':'example.com'}))
        error.exception.close()
        with self.assertRaises(HTTPError) as error:urlopen(Request(url+'/api/rendering',headers={'Host':'example.com'}))
        self.assertEqual(error.exception.code,403);error.exception.close()

    def test_pending_half_edit_preserves_pending_owner(self):
        app=self.projects();self.task('a','a');self.event('Stop','a');self.prepare()
        with contextlib.closing(database.connect_state(self.directory)) as db,db:b.current_comet(db,1000)
        key=w.line_id(self.config['line_groups'][0])
        self.assign(app,[0],'b');app.update('/api/assign',{'lines':{key:{'signature':1}}})
        self.assertEqual(app.state()['pending']['lines'][key],{'project':'b','signature':1})
        self.clock.sleep(2);self.prepare()
        self.assertEqual(self.query('SELECT project,signature FROM line_prefs'),[('b',1)])

    def test_metadata_valid_json_wrong_shape_is_ignored(self):
        self.projects();self.task('s',None)
        path=self.directory/'desktop.json';index=self.directory/'index.jsonl'
        path.write_text('[]');index.write_text('[]\nnull\n{"id":"s","thread_name":"Valid"}\n')
        metadata=w.Metadata(self.directory,dict(self.config,metadata_path=str(path),title_index_path=str(index)))
        metadata.refresh()
        with contextlib.closing(database.connect_state(self.directory)) as db,db:metadata.sync(db)
        self.assertEqual(self.query('SELECT title FROM task_info'),[('Valid',)])
        self.assertEqual(w.normalize('\\\\wsl$\\Ubuntu\\mnt\\c\\REPO\\b\\..\\b'), 'c:/repo/b')

    def test_preferences_persist_after_reopen(self):
        app=self.projects();self.assign(app,[4],'a');app.update('/api/project',{'id':'a','color':'#113355'})
        app.update('/api/settings',{'style':'project','coverage':'status','rotation':270,'flip_y':1})
        reopened=wall_server.App(self.directory,self.config,launch=lambda _:None).state()
        self.assertEqual(reopened['settings'],{'style':'project','coverage':'status','rotation':270,'flip_x':0,'flip_y':1})
        self.assertEqual(next(p for p in reopened['projects'] if p['id']=='a')['color'],'#113355')
        self.assertEqual(self.query('SELECT project FROM line_prefs'),[('a',)])

    def test_idle_locate_returns_scene_after_one_second(self):
        app=self.projects();self.assign(app,[0],'a');app.update('/api/settings',{'style':'project'})
        app.update('/api/locate',{'line':w.line_id(self.config['line_groups'][0])})
        self.run_worker()
        frames=[(at,decode(payload)) for at,method,endpoint,payload in self.device.calls if method=='PUT' and endpoint=='/effects' and 'write' in payload]
        self.assertEqual(frames[0][1][100][0][:3],[255,255,255])
        self.assertEqual((self.device.selected,self.device.brightness),('Beach Waves',43))
        self.assertGreaterEqual(self.clock.now(),1001)
        self.assertEqual(self.query('SELECT * FROM locate'),[])

    def test_project_early_read_comet_finishes_before_scene_restore(self):
        app=self.projects();self.task('a','a');app.update('/api/settings',{'style':'project'})
        def finish():self.unread.add('a');self.event('Stop','a')
        self.run_worker([(1003,finish),(1003.5,lambda:self.unread.clear())])
        restorations=[at for at,method,endpoint,payload in self.device.calls if method=='PUT' and payload.get('select')=='Beach Waves']
        self.assertEqual(len(restorations),1);self.assertGreaterEqual(restorations[0],1005)
        self.assertEqual(self.query('SELECT * FROM comets'),[])

    def test_color_edit_invalidates_display_without_pulse_or_comet_replay(self):
        app=self.projects();self.task('a','a');app.update('/api/settings',{'style':'project','coverage':'status'})
        self.run_worker([(1003,lambda:app.update('/api/project',{'id':'a','color':'#113355'})),(1006,lambda:self.event('Interrupt','a'))])
        frames=[decode(payload) for at,method,endpoint,payload in self.device.calls if at>=1003 and method=='PUT' and endpoint=='/effects' and 'write' in payload]
        self.assertTrue(any(all(f[:3]==[17,51,85] for f in panels[100]) for panels in frames))
        self.assertFalse(any(any(f[:3]==[255,255,255] for f in panels[100]) for panels in frames))

    def test_status_coverage_keeps_unknown_project_half_blue(self):
        app=self.projects();self.task('unknown',None);app.update('/api/settings',{'style':'project','coverage':'status'})
        cfg,snap=self.prepare();cfg['_comet']={'source':0,'started':1000}
        actual=decode(b.effect_payload(cfg,snap,1000,False))
        self.assertTrue(all(f[:3]==list(b.BASELINE) for f in actual[100]))
        self.assertTrue(all(f[:3]==list(b.BASELINE) for f in actual[102]))
        self.assertNotEqual(actual[100],actual[101])

    def test_map_retries_missing_geometry(self):
        app=self.projects();app.geometry_retry=0
        from unittest.mock import patch
        with patch.object(wall_server,'ensure_geometry') as refresh_geometry:
            app.state();app.state()
            refresh_geometry.assert_called_once_with(self.directory,app.config,refresh=True,request=None)
