"""#120 AC2: the synthetic map fixture that scripts/demo.py serves to the browser suite."""
import contextlib
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_bridge import b  # noqa: F401  (puts bridge/ on the import path)
import database
import store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('demo', ROOT / 'scripts/demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
NOW = 50000.0


class DemoFixtureTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def query(self, sql):
        with contextlib.closing(database.connect_state(self.directory)) as db:
            return db.execute(sql).fetchall()

    def test_demo_seeds_tasks_projects_and_applied_modes_without_a_device(self):
        demo.prepare(self.directory, now=lambda: NOW)
        stamps = [NOW - 90 - index * 61 for index in range(5)]
        statuses = ['working', 'blocked', 'question', 'unread', 'working']
        self.assertEqual(self.query('SELECT id, turn, status, updated FROM sessions ORDER BY id'),
                         [(f'task-{i}', '1', statuses[i], stamps[i]) for i in range(5)])
        # Each task's wave epoch is its status time, so the map shows settled local pulses.
        self.assertEqual(self.query('SELECT session, turn, status, started FROM activity ORDER BY session'),
                         [(f'task-{i}', '1', statuses[i], stamps[i]) for i in range(5)])
        self.assertEqual(self.query('SELECT id, name, color, roots FROM projects ORDER BY id'),
                         [('a', 'Notification Service', '#ad8dff', '[]'), ('b', 'Daily Trader', '#39d8bb', '[]'),
                          ('c', 'NBA GM', '#f4ad68', '[]')])
        self.assertEqual(self.query('SELECT session, title, cwd, project, manual_project, turn, started FROM task_info ORDER BY session'),
                         [(f'task-{i}', title, '', project, None, '1', stamps[i]) for i, (title, project) in enumerate(
                             [('Verify subscriber delivery', 'a'), ('Review callback <b>safe</b>', 'a'),
                              ('Confirm trade parameters', 'b'), ('Summarize market session', 'b'), ('Build player profiles', 'c')])])
        with contextlib.closing(database.connect_state(self.directory)) as db:
            for device in ('wall', 'panels'):
                with self.subTest(device=device):
                    state = store.control_state(db, device)
                    self.assertEqual((state['mode'], state['applied']), ('work', state['revision']))
                    placed = db.execute('SELECT COUNT(*) FROM slots WHERE device=?', (device,)).fetchone()[0]
                    self.assertGreaterEqual(placed, 4, 'the browser suite needs placed tasks on each device')

    def test_seeding_stays_inside_the_callers_transaction(self):
        project = {'id': 'p', 'name': 'Project', 'color': '#123456'}
        tasks = [{'id': 'kept', 'title': 'Kept', 'project': 'p', 'status': 'working', 'since': NOW},
                 {'id': 'bad', 'title': 'Bad', 'project': 'p', 'status': 'idle', 'since': NOW}]
        with contextlib.closing(database.connect_state(self.directory)) as db:
            db.execute('BEGIN IMMEDIATE')
            with patch.object(sqlite3, 'connect', side_effect=AssertionError('seeding opens no connection')):
                database.seed_synthetic(db, [project], tasks[:1])
                self.assertTrue(db.in_transaction, 'no hidden commit')
                with self.assertRaises(ValueError):
                    database.seed_synthetic(db, [], tasks[1:])
            db.rollback()
        for table in ('projects', 'sessions', 'activity', 'task_info'):
            with self.subTest(table=table):
                self.assertEqual(self.query('SELECT * FROM ' + table), [])


if __name__ == '__main__':
    unittest.main()
