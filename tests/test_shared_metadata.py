import contextlib
import copy
import json
from unittest.mock import patch

from test_bridge import b
import unittest
import test_shared_input as fixtures
from test_shared_input import envelope
import project_map as wall


class SharedMetadataTest(unittest.TestCase):
    select=fixtures.SelectionTest.select
    rows=fixtures.SelectionTest.rows
    # Reuse fixture helpers without rerunning SelectionTest's test methods here.
    def setUp(self):
        fixtures.SelectionTest.setUp(self)
        self.value=envelope()
        self.session=self.value['snapshot']['sessions'][0]
        self.sid=self.session['identity']['sessionId']
        self.key=self.s.identity_key(self.session['identity'])
        self.session.pop('label',None); self.session.pop('projectId',None)
        self.metadata_path=self.path/'metadata.json'
        self.index=self.path/'session_index.jsonl'
        (self.path/'config.json').write_text(json.dumps({'metadata_path':str(self.metadata_path),'title_index_path':str(self.index)}))
        self.write_metadata()

    def write_metadata(self,title='Real task title',assignment=True):
        self.index.write_text(json.dumps({'id':self.sid,'thread_name':title})+'\n')
        self.metadata_path.write_text(json.dumps({
            'local-projects':{'local':{'name':'Local project','rootPaths':['/repo']},
                              'nested':{'name':'Nested project','rootPaths':['/repo/nested']}},
            'thread-project-assignments':{self.sid:{'projectId':'local'}} if assignment else {},
            'thread-workspace-root-hints':{self.sid:'/repo/nested/src'}}))

    def detail(self):
        return self.rows('SELECT title,project,manual_project FROM task_info WHERE session="'+self.key+'"')[0]

    def test_local_title_and_project_enrich_shared_task(self):
        self.select(self.value)
        self.assertEqual(self.detail(),('Real task title','local','project'))
        self.assertEqual(self.rows("SELECT name FROM projects WHERE id='local'"),[('Local project',)])
        # Manual preference wins in the allocation layer.
        with contextlib.closing(b.connect_state(self.path)) as db:
            self.assertEqual(wall.task_projects(db)[self.key],'project')
        self.assertNotIn('Real task title',json.dumps(self.s.inspect(self.path)))

    def test_enriched_project_controls_line_allocation(self):
        self.session['activity']='active'
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute("UPDATE task_info SET manual_project=NULL WHERE session='legacy'")
        self.select(self.value)
        config={'line_groups':[[100,101],[102,103]]}
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            db.execute("DELETE FROM slots")
            db.execute("UPDATE map_settings SET style='project'")
            db.executemany("INSERT INTO line_prefs (line_id,project,signature) VALUES (?,?,0)",
                           [(wall.line_id([100,101]),'nested'),(wall.line_id([102,103]),'local')])
            assigned=wall.allocate(db,config,[(self.key,'working',1000)],set())
        self.assertEqual(assigned,{self.key:1})

    def test_hub_precedence_and_other_provider_isolation(self):
        other=copy.deepcopy(self.session); other['identity']['provider']='claude';other['identity']['client']='code';other['read']='unknown'
        self.config['qualifiedSources'].append({k:other['identity'][k] for k in self.s.SOURCE})
        self.s.configure(self.path,b,self.config)
        self.value['snapshot']['sessions'].append(other)
        self.session.update(label='Hub label',projectId='hub')
        self.select(self.value)
        self.assertEqual(self.detail(),('Hub label','shared-project-hub','project'))
        otherkey=self.s.identity_key(other['identity'])
        title,project=self.rows("SELECT title,project FROM task_info WHERE session='"+otherkey+"'")[0]
        self.assertTrue(title.startswith('Claude '));self.assertIsNone(project)

    def test_poll_refreshes_same_revision_without_lifecycle_or_effect_changes(self):
        self.select(self.value)
        before=self.rows('SELECT * FROM sessions'),self.rows('SELECT * FROM activity')
        poller=self.s.Poller(self.path,b)
        with patch.object(self.s,'fetch_snapshot',return_value=self.value):
            poller.tick(1001)
            with contextlib.closing(b.connect_state(self.path)) as db,db:
                db.execute("UPDATE meta SET value='0' WHERE key='dirty'")
            self.write_metadata('Updated title',assignment=False)
            poller.tick(1002)
        self.assertEqual(self.detail(),('Updated title','nested','project'))
        self.assertEqual(before,(self.rows('SELECT * FROM sessions'),self.rows('SELECT * FROM activity')))
        self.assertEqual(self.rows("SELECT value FROM meta WHERE key='dirty'"),[('1',)])
        # A fresh reader after restart preserves the same projection.
        self.s.accept(self.path,b,self.value)
        self.assertEqual(self.detail()[0],'Updated title')

    def test_retired_session_is_not_recreated_by_metadata(self):
        self.select(self.value)
        self.value['snapshot']['sessions']=[];self.value['snapshot']['revision']+=1
        self.s.accept(self.path,b,self.value)
        self.s.accept(self.path,b,self.value)
        self.assertEqual(self.rows('SELECT * FROM sessions'),[])
        self.assertEqual(self.rows('SELECT * FROM task_info'),[])
        self.assertEqual(self.rows('SELECT * FROM slots'),[])

    def test_missing_metadata_fallback_and_legacy_parity(self):
        self.index.unlink();self.metadata_path.unlink()
        ids=['019a1234-0000-7000-8000-00005b1e07c2','019a1234-0000-7000-8000-00004227761b']
        self.config['bindings']=[]
        self.s.configure(self.path,b,self.config)
        self.session['identity']['sessionId']=ids[0]
        other=copy.deepcopy(self.session);other['identity']['sessionId']=ids[1]
        self.value['snapshot']['sessions'].append(other)
        self.select(self.value)
        self.assertEqual(sorted(title for title, in self.rows('SELECT title FROM task_info')),
                         ['Codex 4227761b','Codex 5b1e07c2'])
        self.assertEqual(wall.fallback_title('codex',ids[0]),'Codex 5b1e07c2')

    def test_source_switch_preserves_manual_preference(self):
        self.select(self.value)
        self.s.select_source(self.path,b,'legacy')
        self.assertEqual(self.rows("SELECT manual_project FROM task_info WHERE session='legacy'"),[('project',)])
        self.select(self.value)
        self.assertEqual(self.detail(),('Real task title','local','project'))

