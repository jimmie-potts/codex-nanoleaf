import contextlib
import json
import unittest
from unittest.mock import patch

from test_bridge import b
import transport
import database
import shared_source
import test_scene_restore as scenes
import test_shared_input as shared
import wall_server


THREAD = '019a1234-5678-7123-8123-123456789abc'
CHILD = '019a1234-5678-7123-8123-123456789def'


class LegacyLinksTest(unittest.TestCase):
    setUp = scenes.SceneTest.setUp
    event = scenes.SceneTest.event
    query = scenes.SceneTest.query

    def app(self, ids):
        self.index = self.directory / 'session_index.jsonl'
        self.index.write_text(''.join(json.dumps({'id':sid,'thread_name':'Desktop task'})+'\n' for sid in ids))
        self.config['title_index_path'] = str(self.index)
        return wall_server.App(self.directory,self.config,launch=lambda _:None)

    def test_indexed_uuid_gets_wall_link(self):
        self.event('UserPromptSubmit',THREAD)
        app = self.app([THREAD])
        self.assertEqual(app.state()['tasks'][0].get('codexUrl'),'codex://threads/'+THREAD)

    def test_unknown_and_malformed_ids_have_no_link(self):
        for sid in (THREAD,'not-a-uuid',THREAD+'?hostId=remote','javascript:alert(1)',THREAD.replace('-','')):
            self.event('UserPromptSubmit',sid)
        app = self.app(['not-a-uuid',THREAD+'?hostId=remote','javascript:alert(1)',THREAD.replace('-','')])
        self.assertTrue(all('codexUrl' not in task for task in app.state()['tasks']))

    def test_index_removal_missing_file_and_recovery(self):
        self.event('UserPromptSubmit',THREAD)
        app = self.app([THREAD])
        self.assertIn('codexUrl',app.state()['tasks'][0])
        original = self.index.read_text()
        self.index.write_text('')
        self.assertNotIn('codexUrl',app.state()['tasks'][0])
        self.assertEqual(app.state()['tasks'][0]['title'],'Desktop task')
        self.index.write_text(original)
        self.assertIn('codexUrl',app.state()['tasks'][0])
        self.index.unlink()
        self.assertNotIn('codexUrl',app.state()['tasks'][0])
        self.index.write_text(original)
        self.assertIn('codexUrl',app.state()['tasks'][0])


class SharedLinksTest(unittest.TestCase):
    setUp = shared.SelectionTest.setUp
    select = shared.SelectionTest.select
    rows = shared.SelectionTest.rows

    def prepare(self, provider='codex', client='desktop', session_id=THREAD, child=False):
        value = shared.envelope()
        root = value['snapshot']['sessions'][0]
        root['identity'].update(provider=provider,client=client,sessionId=session_id)
        root['activity'] = 'active'
        if provider != 'codex': root['read'] = 'unknown'
        self.config['bindings'] = []
        self.config['qualifiedSources'] = [{k:root['identity'][k] for k in self.s.SOURCE}]
        if child:
            sub = shared.child_of(root,CHILD,activity='active')
            value['snapshot']['sessions'].append(sub)
            source = {k:sub['identity'][k] for k in self.s.SOURCE}
            if source not in self.config['qualifiedSources']: self.config['qualifiedSources'].append(source)
        shared.recount(value)
        shared_source.configure(self.path,self.config)
        self.select(value)
        app = wall_server.App(self.path,{'line_groups':[[100,101]],'line_positions':[[0,0]]},launch=lambda _:None)
        return app, value

    def test_shared_desktop_root_links_without_local_index(self):
        app, _ = self.prepare()
        self.assertEqual(app.state()['tasks'][0].get('codexUrl'),'codex://threads/'+THREAD)

    def test_folded_child_links_only_parent(self):
        app, _ = self.prepare(child=True)
        tasks = app.state()['tasks']
        self.assertEqual(len(tasks),1)
        self.assertEqual(tasks[0].get('codexUrl'),'codex://threads/'+THREAD)

    def assert_no_root_link(self,provider,client,sid):
        app, _ = self.prepare(provider,client,sid,child=True)
        app.metadata.titles[THREAD] = 'Cached Desktop title'
        tasks = app.state()['tasks']
        self.assertEqual(len(tasks),1)
        self.assertNotIn('codexUrl',tasks[0])

    def test_cli_has_no_link(self):
        self.assert_no_root_link('codex','cli',THREAD)

    def test_claude_has_no_link(self):
        self.assert_no_root_link('claude','code',THREAD)

    def test_malformed_root_does_not_borrow_desktop_child_uuid(self):
        self.assert_no_root_link('codex','desktop','bad')

    def test_unhyphenated_id_has_no_link(self):
        self.assert_no_root_link('codex','desktop',THREAD.replace('-',''))

    def test_link_projection_preserves_state_and_machine_api_privacy(self):
        import controller_state
        import integration_api
        app, value = self.prepare(child=True)
        with contextlib.closing(database.connect_state(self.path)) as db,db:
            controller_state.init(db,{'deviceId':'device'})
        tables = ('sessions','activity','receipts','comets','slots','meta','shared_input','controller_meta','controller_requests')
        before = {table:self.rows('SELECT * FROM '+table) for table in tables}
        with patch.object(transport,'light_request',side_effect=AssertionError('device request')), \
             patch.object(app,'launch',side_effect=AssertionError('worker launch')):
            for _ in range(2): self.assertIn('codexUrl',app.state()['tasks'][0])
        self.assertEqual(before,{table:self.rows('SELECT * FROM '+table) for table in tables})
        with contextlib.closing(database.connect_state(self.path)) as db:
            self.assertNotIn('codexUrl',json.dumps(controller_state.snapshot(db)))
            self.assertNotIn('codexUrl',json.dumps(integration_api.projection(db,app.config['line_groups'])[0]))
        self.assertNotIn('codexUrl',json.dumps(self.s.inspect(self.path)))
        self.assertNotIn('codexUrl',json.dumps(value))


if __name__ == '__main__':
    unittest.main()
