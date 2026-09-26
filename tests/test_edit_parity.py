"""Equivalent configuration edits through the wall map and the integration extension (#118)."""
import contextlib
import json
import unittest

import test_controller_state as baseline
from test_bridge import b
import database
import jsonfile
import project_map as wall


class EditParityTest(unittest.TestCase):
    """The browser and machine adapters share one edit implementation and its notifications."""

    def setUp(self):
        baseline.ControllerStateTest.setUp(self)
        self.config = {'line_groups': [[101, 102], [103, 104]]}
        jsonfile.write_json(self.directory / 'config.json', self.config)
        jsonfile.write_json(self.directory / 'layout.json', {'line_groups': self.config['line_groups']})
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO projects VALUES ('/work/alpha', 'Alpha', '#112233', '[]')")
            db.execute("INSERT INTO projects VALUES ('/work/beta', 'Beta', '#445566', '[]')")
            db.execute("INSERT INTO task_info VALUES ('task-a','Task A','/work/alpha','/work/alpha',NULL,'turn',42)")
            db.execute("INSERT INTO sessions VALUES ('task-a','turn','working',42)")
            db.execute("INSERT INTO line_prefs (line_id, project, signature, device) VALUES ('103:104', '/work/beta', 1, 'wall')")
            # Another device's reservation and preference, which no Lines edit may touch.
            db.execute("INSERT INTO comets (session, turn, queued, source, started, device) VALUES ('task-a','turn',1,0,2,'panels')")
            db.execute("INSERT INTO line_prefs (line_id, project, signature, device) VALUES ('7', '/work/alpha', 0, 'panels')")
        self.browser = self.wall_app()

    def wall_app(self):
        import wall_server
        return wall_server.App(self.directory, config=self.config, launch=lambda _: None)

    def process(self):
        import integration_api
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            integration_api.process(db, self.config)

    def request(self, command):
        view = self.app.integration_snapshot(self.token, 'device')
        return dict(apiVersion=view['apiVersion'], controllerId='controller', deviceId='device',
                    requestId=view['nextRequestId'], expectedRevision=view['revision'], command=command)

    def machine(self, command):
        request = self.request(command)
        code, _ = self.app.integration_admit(self.token, request)
        self.assertEqual(code, 202)
        self.process()
        return self.app.integration_admit(self.token, request)[1]

    def opaque(self):
        # The extension lists projects and tasks in local-ID order under opaque IDs.
        view = self.app.integration_snapshot(self.token, 'device')
        projects = dict(zip(('/work/alpha', '/work/beta'), (p['id'] for p in view['projects'])))
        return projects, view['tasks'][0]['id']

    def saved(self):
        with contextlib.closing(self.state.readonly(self.directory)) as db:
            return dict(
                settings=wall.settings(db),
                palette=wall.palette(db),
                prefs=db.execute('SELECT line_id,project,signature,device FROM line_prefs ORDER BY device,line_id').fetchall(),
                tasks=db.execute('SELECT session,project,manual_project FROM task_info ORDER BY session').fetchall(),
                colors=db.execute('SELECT id,color FROM projects ORDER BY id').fetchall(),
                pending=db.execute('SELECT payload,device FROM map_pending ORDER BY device').fetchall(),
                epochs=db.execute('SELECT session,turn,status,started FROM activity ORDER BY session').fetchall(),
                comets=db.execute('SELECT session,turn,queued,source,started,device FROM comets ORDER BY device').fetchall(),
                source=db.execute('SELECT source FROM shared_input').fetchone(),
                mode=db.execute("SELECT value FROM meta WHERE key='mode'").fetchone())

    def counters(self):
        with contextlib.closing(self.state.readonly(self.directory)) as db:
            event = db.execute("SELECT value FROM meta WHERE key='event_revision'").fetchone()
            return int(event[0]) if event else 0, self.state.read(db)['revision']

    def assert_once(self, before):
        after = self.counters()
        self.assertEqual(after[0] - before[0], 1, 'one display wake-up per edit')
        self.assertEqual(after[1] - before[1], 1, 'one Lines ledger revision per edit')

    def edits(self):
        projects, task = self.opaque()
        alpha, beta = projects['/work/alpha'], projects['/work/beta']
        return [
            (('/api/settings', {'style': 'project', 'coverage': 'status'}),
             dict(kind='settings.set', style='project', coverage='status')),
            (('/api/assign', {'lines': {'101:102': {'project': '/work/beta', 'signature': 1}}}),
             dict(kind='elements.assign', elements=[dict(id='101:102', projectId=beta, signature=1)])),
            (('/api/assign', {'lines': {'103:104': {'project': None}}}),
             dict(kind='elements.assign', elements=[dict(id='103:104', projectId=None)])),
            (('/api/task', {'id': 'task-a', 'project': '/work/beta'}),
             dict(kind='task.assign', taskId=task, projectId=beta)),
            (('/api/project', {'id': '/work/alpha', 'color': '#AABBCC'}),
             dict(kind='project.color', projectId=alpha, color='#AABBCC')),
        ]

    def test_equivalent_edits_save_equivalent_state(self):
        initial = self.saved()
        for index, (browser, machine) in enumerate(self.edits()):
            with self.subTest(edit=machine['kind'], index=index):
                # Run the browser edit, record the result, then restore and run the machine edit.
                snapshot = (self.directory / 'status.sqlite').read_bytes()
                before = self.counters()
                self.assertEqual(self.browser.update(*browser), {'ok': True})
                self.assert_once(before)
                through_browser = self.saved()
                (self.directory / 'status.sqlite').write_bytes(snapshot)
                before = self.counters()
                receipt = self.machine(machine)
                self.assertEqual(receipt['outcome'], 'applied')
                self.assert_once(before)
                through_machine = self.saved()
                self.assertEqual(through_browser, through_machine)
                # Neither adapter resets epochs, reservations, source or mode.
                for key in ('epochs', 'comets', 'source', 'mode'):
                    self.assertEqual(through_machine[key], initial[key], key)
                self.assertIn(('7', '/work/alpha', 0, 'panels'), through_machine['prefs'])
                (self.directory / 'status.sqlite').write_bytes(snapshot)

    def test_active_comet_defers_browser_edit_and_holds_machine_edit(self):
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO comets (session, turn, queued, source, started, device) VALUES ('task-a','turn',1,0,2,'wall')")
        # Browser: an edit that moves the comet's source Line is saved as a pending wall edit.
        self.browser.update('/api/settings', {'style': 'project'})
        self.assertEqual(json.loads(self.saved()['pending'][0][0])['settings'], {'style': 'project'})
        self.assertEqual(self.saved()['settings']['style'], 'classic')
        # An edit away from the comet applies at once.
        self.browser.update('/api/project', {'id': '/work/beta', 'color': '#010203'})
        self.assertIn(('/work/beta', '#010203'), self.saved()['colors'])
        # Machine: admission refuses while a pending wall edit exists.
        request = self.request(dict(kind='settings.set', coverage='status'))
        self.assertEqual(self.app.integration_admit(self.token, request)[1]['failure']['code'], 'revision-conflict')
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute('DELETE FROM map_pending')
        # A queued edit waits while the Lines comet plays, then applies once it ends.
        request = self.request(dict(kind='settings.set', coverage='status'))
        self.assertEqual(self.app.integration_admit(self.token, request)[0], 202)
        self.process()
        self.assertEqual(self.app.integration_admit(self.token, request)[1]['outcome'], 'queued')
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("DELETE FROM comets WHERE device='wall'")
        self.process()
        self.assertEqual(self.app.integration_admit(self.token, request)[1]['outcome'], 'applied')
        self.assertEqual(self.saved()['settings']['coverage'], 'status')
        # A wall edit deferred after admission changes the revision the request expected.
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO comets (session, turn, queued, source, started, device) VALUES ('task-a','turn',1,0,2,'wall')")
        request = self.request(dict(kind='settings.set', coverage='whole'))
        self.assertEqual(self.app.integration_admit(self.token, request)[0], 202)
        self.browser.update('/api/settings', {'style': 'project'})
        self.process()
        receipt = self.app.integration_admit(self.token, request)[1]
        self.assertEqual((receipt['outcome'], receipt['failure']['code']), ('failed', 'revision-conflict'))
        self.assertEqual(self.saved()['settings']['coverage'], 'status')

    def test_browser_edit_after_admission_is_a_machine_revision_conflict(self):
        request = self.request(dict(kind='settings.set', style='project'))
        self.assertEqual(self.app.integration_admit(self.token, request)[0], 202)
        self.browser.update('/api/settings', {'coverage': 'status'})
        before = self.counters()
        self.process()
        receipt = self.app.integration_admit(self.token, request)[1]
        self.assertEqual((receipt['outcome'], receipt['failure']['code']), ('failed', 'revision-conflict'))
        self.assertEqual(self.counters(), before, 'a failed request notifies nothing')
        self.assertEqual(self.saved()['settings']['style'], 'classic')
        self.assertEqual(self.saved()['settings']['coverage'], 'status')

    def test_browser_only_edits_keep_their_ledger_scope(self):
        # Palette-only settings, eviction and Locate are browser edits; each still notifies once.
        before = self.counters()
        self.browser.update('/api/settings', {'palette': {'working': '#00e5ff'}})
        self.assert_once(before)
        before = self.counters()
        self.browser.update('/api/locate', {'line': '101:102'})
        self.assert_once(before)


if __name__ == '__main__':
    unittest.main()
