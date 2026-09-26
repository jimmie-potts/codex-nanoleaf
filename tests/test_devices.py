"""Device registry, per-device layout shape, device-scoped state and the Linux migration."""
import contextlib
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_bridge import b
import configuration
import database
import jsonfile
import modes
import store
import transport
import project_map as wall
import devices

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/linux-state-v4'
NO_DEVICE = AssertionError('The device must not be contacted.')


def refuse(*args, **kwargs):
    raise NO_DEVICE


class DeviceTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        # Nothing here may reach a device: refuse at the transport boundary.
        patcher = patch.object(transport, 'light_request', refuse)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_two_devices(self):
        jsonfile.write_json(self.directory / 'config.json', {
            'ip': '192.0.2.1', 'token': 'fakeLines', 'panelsToken': 'fakePanels',
            'devices': {'wall': {'kind': 'lines', 'ip': '192.0.2.1', 'token_ref': 'token'},
                        'panels': {'kind': 'panels', 'ip': '192.0.2.2', 'token_ref': 'panelsToken'}}})
        jsonfile.write_json(self.directory / 'layout.json', {'version': 2, 'devices': {
            'wall': {'kind': 'lines', 'elements': [
                {'id': '5:6', 'number': 1, 'zones': [5, 6], 'position': [0, 0]},
                {'id': '7:8', 'number': 2, 'zones': [7, 8], 'position': [10, 0]}]},
            'panels': {'kind': 'panels', 'elements': [
                {'id': '5', 'number': 1, 'zones': [5], 'position': [0, 0]},
                {'id': '6', 'number': 2, 'zones': [6], 'position': [10, 0]},
                {'id': '7', 'number': 3, 'zones': [7], 'position': [20, 0]}]}}})

    def query(self, sql, *params):
        with contextlib.closing(database.connect_state(self.directory)) as db:
            return db.execute(sql, params).fetchall()

    # AC4 and AC6: layout shapes
    def test_legacy_layout_loads_as_default_device_without_request(self):
        jsonfile.write_json(self.directory / 'config.json', {'ip': '192.0.2.1', 'token': 'fake'})
        groups = [[100 + i * 2, 101 + i * 2] for i in range(15)]
        positions = [[i * 10, 0] for i in range(15)]
        jsonfile.write_json(self.directory / 'layout.json', {'line_groups': groups, 'line_positions': positions})
        disk = (self.directory / 'layout.json').read_bytes()
        config = configuration.load_config(self.directory)
        self.assertEqual((config['device'], config['kind']), ('wall', 'lines'))
        self.assertEqual(config['line_groups'], groups)
        self.assertEqual(config['line_positions'], positions)
        self.assertEqual([e['number'] for e in config['elements']], list(range(1, 16)))
        self.assertEqual(config['elements'][0], {'id': '100:101', 'number': 1, 'zones': [100, 101], 'position': [0, 0]})
        self.assertEqual((self.directory / 'layout.json').read_bytes(), disk)
        self.assertEqual(configuration.load_config(self.directory, 'wall')['elements'], config['elements'])
        self.assertNotIn('devices', json.dumps(config.get('elements')))

    def test_version_two_layout_with_lines_and_triangles(self):
        self.write_two_devices()
        lines = configuration.load_config(self.directory)
        panels = configuration.load_config(self.directory, 'panels')
        self.assertEqual((lines['device'], lines['ip'], lines['token']), ('wall', '192.0.2.1', 'fakeLines'))
        self.assertEqual((panels['device'], panels['kind'], panels['ip'], panels['token']), ('panels', 'panels', '192.0.2.2', 'fakePanels'))
        self.assertEqual(lines['line_groups'], [[5, 6], [7, 8]])
        self.assertEqual(panels['line_groups'], [[5], [6], [7]])
        self.assertEqual([e['id'] for e in panels['elements']], ['5', '6', '7'])
        self.assertEqual(sorted(devices.registry(json.loads((self.directory / 'config.json').read_text()))), ['panels', 'wall'])
        with self.assertRaises(ValueError):
            configuration.load_config(self.directory, 'unknown')

    def test_malformed_layout_is_rejected_and_last_valid_file_kept(self):
        self.write_two_devices()
        valid = json.loads((self.directory / 'layout.json').read_text())
        for mutate in (lambda d: d['wall']['elements'][0].update(zones=[5]),
                       lambda d: d['panels']['elements'][0].update(zones=[5, 6]),
                       lambda d: d['wall']['elements'][1].update(zones=[5, 6]),
                       lambda d: d['wall']['elements'][0].update(zones=['5', 6]),
                       lambda d: d['wall']['elements'][0].update(number=2),
                       lambda d: d['wall'].update(kind='unknown'),
                       lambda d: d['wall'].update(elements=[])):
            broken = copy.deepcopy(valid)
            mutate(broken['devices'])
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    devices.layout_devices(broken)
                with self.assertRaises(ValueError):
                    devices.save_layout(self.directory / 'layout.json', broken['devices'])
                self.assertEqual(json.loads((self.directory / 'layout.json').read_text()), valid)
        (self.directory / 'layout.json').write_text(json.dumps({'version': 2, 'devices': {'wall': {'kind': 'lines', 'elements': [{'id': '5:6', 'number': 1, 'zones': [5, 5], 'position': [0, 0]}]}}}))
        with self.assertRaises(ValueError):
            configuration.load_config(self.directory)

    @unittest.skipUnless(sys.platform == 'linux', 'Native Linux installation')
    def test_installer_writes_per_device_layout_and_registry(self):
        import install_linux
        layout = json.loads((ROOT / 'tests/fixtures/lines-layout.json').read_text())
        install_linux.prepare_state(self.directory / 'state', '192.0.2.12', 'fixtureToken',
                                    request=lambda *_: {'panelLayout': layout})
        saved = json.loads((self.directory / 'state/layout.json').read_text())
        self.assertEqual(saved['version'], 2)
        self.assertEqual(list(saved['devices']), ['wall'])
        elements = saved['devices']['wall']['elements']
        self.assertEqual(len(elements), 15)
        self.assertTrue(all(len(e['zones']) == 2 and e['id'] == devices.element_id(e['zones']) for e in elements))
        self.assertEqual([e['number'] for e in elements], list(range(1, 16)))
        config = json.loads((self.directory / 'state/config.json').read_text())
        self.assertEqual(config['devices'], {'wall': {'kind': 'lines', 'ip': '192.0.2.12', 'token_ref': 'token'}})
        self.assertEqual(json.dumps(config).count('fixtureToken'), 1)
        loaded = configuration.load_config(self.directory / 'state')
        self.assertEqual(len(loaded['line_groups']), 15)
        self.assertIsNotNone(wall.connector_layout(loaded))

    # AC2: identity
    def test_registry_address_change_keeps_identity_and_preferences(self):
        self.write_two_devices()
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            wall.apply_patch(db, {'lines': {'5:6': {'project': 'kept'}}})
        config = json.loads((self.directory / 'config.json').read_text())
        config['ip'] = '192.0.2.99'
        config['devices']['wall']['ip'] = '192.0.2.99'
        jsonfile.write_json(self.directory / 'config.json', config)
        moved = configuration.load_config(self.directory)
        self.assertEqual((moved['device'], moved['ip']), ('wall', '192.0.2.99'))
        with contextlib.closing(database.connect_state(self.directory)) as db:
            self.assertEqual(wall.owners(db, moved)[0], ('kept', 0))

    def test_equal_element_ids_on_two_devices_do_not_collide(self):
        self.write_two_devices()
        lines = configuration.load_config(self.directory)
        panels = configuration.load_config(self.directory, 'panels')
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.executemany('INSERT INTO projects VALUES (?,?,?,?)', [('a', 'A', '#111111', '[]'), ('b', 'B', '#222222', '[]')])
            wall.request_patch(db, {'lines': {'5:6': {'project': 'a', 'signature': 1}}}, lines)
            wall.request_patch(db, {'lines': {'5': {'project': 'b'}}, 'settings': {'style': 'project'}}, panels)
            self.assertEqual(wall.owners(db, lines)[0], ('a', 1))
            self.assertEqual(wall.owners(db, panels)[0], ('b', 0))
            self.assertEqual(wall.settings(db)['style'], 'classic')
            self.assertEqual(wall.settings(db, 'panels')['style'], 'project')
            db.execute("INSERT INTO comets (session, turn, queued, source, started, device) VALUES ('t','1',1,0,1,'panels')")
            self.assertTrue(wall.request_patch(db, {'lines': {'5': {'project': None}}}, panels))
            self.assertFalse(wall.request_patch(db, {'lines': {'5:6': {'project': None}}}, lines))
            self.assertIsNone(wall.pending(db))
            self.assertEqual(wall.pending(db, 'panels')['lines'], {'5': {'project': None}})
            self.assertEqual(wall.owners(db, lines)[0], (None, 1))
            self.assertEqual(wall.owners(db, panels)[0], ('b', 0))

    def test_literally_equal_element_ids_on_two_devices_keep_separate_state(self):
        jsonfile.write_json(self.directory / 'config.json', {
            'ip': '192.0.2.1', 'token': 'fakeLines', 'secondToken': 'fakeSecond',
            'devices': {'wall': {'kind': 'lines', 'ip': '192.0.2.1', 'token_ref': 'token'},
                        'second': {'kind': 'lines', 'ip': '192.0.2.3', 'token_ref': 'secondToken'}}})
        element = {'id': '5:6', 'number': 1, 'zones': [5, 6], 'position': [0, 0]}
        jsonfile.write_json(self.directory / 'layout.json', {'version': 2, 'devices': {
            'wall': {'kind': 'lines', 'elements': [element]}, 'second': {'kind': 'lines', 'elements': [element]}}})
        first = configuration.load_config(self.directory)
        second = configuration.load_config(self.directory, 'second')
        self.assertEqual([e['id'] for e in first['elements']], [e['id'] for e in second['elements']])
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.executemany('INSERT INTO projects VALUES (?,?,?,?)', [('a', 'A', '#111111', '[]'), ('b', 'B', '#222222', '[]')])
            wall.apply_patch(db, {'lines': {'5:6': {'project': 'a', 'signature': 1}}}, 'wall')
            wall.apply_patch(db, {'lines': {'5:6': {'project': 'b'}}}, 'second')
            self.assertEqual(wall.owners(db, first), [('a', 1)])
            self.assertEqual(wall.owners(db, second), [('b', 0)])
            self.assertEqual(db.execute("SELECT device, project FROM line_prefs WHERE line_id='5:6' ORDER BY device").fetchall(),
                             [('second', 'b'), ('wall', 'a')])
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO line_prefs (line_id, project, signature, device) VALUES ('5:6', 'c', 0, 'wall')")
            db.execute("INSERT OR REPLACE INTO locate (line_id, started, device) VALUES ('5:6', NULL, 'second')")
            self.assertIsNone(wall.locate_state(db, first, 1000.0, 'work'))
            self.assertEqual(wall.locate_state(db, second, 1000.0, 'work'), {'source': 0, 'started': 1000.0})

    # AC3: device-scoped placements, modes and scenes
    def test_one_task_one_placement_per_device_and_unique_slot_per_device(self):
        self.write_two_devices()
        lines = configuration.load_config(self.directory)
        panels = configuration.load_config(self.directory, 'panels')
        b.handle_event(self.directory, {'hook_event_name': 'UserPromptSubmit', 'session_id': 'a', 'turn_id': '1'}, launch=lambda _: None, now=lambda: 1000.0)
        b.handle_event(self.directory, {'hook_event_name': 'UserPromptSubmit', 'session_id': 'b', 'turn_id': '1'}, launch=lambda _: None, now=lambda: 1001.0)
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            first = b.dashboard(db, lines, 1002.0)
            second = b.dashboard(db, panels, 1002.0)
            self.assertEqual([s and s[0] for s in first], ['working', 'working'])
            self.assertEqual([s and s[0] for s in second], ['working', 'working', None])
            self.assertEqual(db.execute("SELECT device, slot FROM slots WHERE session='a' ORDER BY device").fetchall(), [('panels', 0), ('wall', 0)])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM activity').fetchone(), (2,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO slots (session, slot, device) VALUES ('c', 0, 'wall')")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO slots (session, slot, device) VALUES ('a', 1, 'wall')")
            db.execute("INSERT INTO slots (session, slot, device) VALUES ('c', 2, 'panels')")
        self.assertEqual(self.query("SELECT slot FROM slots WHERE session='c'"), [(2,)])

    def test_modes_and_scene_files_are_independent_per_device(self):
        self.write_two_devices()
        lines = configuration.load_config(self.directory)
        panels = configuration.load_config(self.directory, 'panels')
        modes.set_mode(self.directory, 'quiet', launch=lambda _: None, now=lambda: 1000.0, device='panels')
        self.assertEqual(modes.get_status(self.directory)['mode'], 'work')
        self.assertEqual(modes.get_status(self.directory, device='panels')['mode'], 'quiet')
        with contextlib.closing(database.connect_state(self.directory)) as db:
            self.assertEqual(store.control_state(db), store.control_state(db, 'wall'))
            self.assertEqual(store.control_state(db, 'panels')['mode'], 'quiet')
            self.assertEqual(store.control_state(db)['revision'], 0)
        jsonfile.write_json(self.directory / 'scene-state.json', {'version': 1, 'scene': {'name': 'Lines Scene', 'brightness': 40}, 'owned': False, 'quiet_scene': None})
        self.assertEqual(b.SceneRestorer(self.directory, lines).state['scene']['name'], 'Lines Scene')
        other = b.SceneRestorer(self.directory, panels)
        self.assertEqual(other.path.name, 'scene-state.panels.json')
        self.assertIsNone(other.state['scene'])
        other.save(scene={'name': 'Panels Scene', 'brightness': 20})
        self.assertEqual(json.loads((self.directory / 'scene-state.json').read_text())['scene']['name'], 'Lines Scene')
        self.assertEqual(json.loads((self.directory / 'scene-state.panels.json').read_text())['scene']['name'], 'Panels Scene')

    # AC5: migration of a pre-change Linux database
    def rows(self, db):
        tables = {
            'sessions': 'id, turn, status, updated', 'activity': 'session, turn, status, started',
            'receipts': 'session, turn, completed, observed', 'waits': 'session, turn, key, kind, tool',
            'task_info': 'session, title, cwd, project, manual_project, turn, started', 'projects': 'id, name, color, roots',
            'slots': 'session, slot', 'comets': 'session, turn, queued, source, started',
            'line_prefs': 'line_id, project, signature', 'map_settings': 'style, coverage, rotation, flip_x, flip_y',
            'map_pending': 'payload', 'locate': 'line_id, started', 'display_v3': 'snapshot, looping, rendered',
            'meta': 'key, value', 'controller_meta': 'id, payload', 'controller_credentials': 'principal, digest, scopes, active',
            'controller_requests': 'sequence, request, receipt, principal, phase, created, mode_revision',
            'controller_events': 'sequence, payload', 'integration_meta': 'id, sequence',
            'integration_requests': 'sequence, principal, request, receipt, phase, created, revision',
            'shared_input': 'id, source, generation, config, envelope, received, connection, error, backup'}
        return {table: sorted(db.execute(f'SELECT {columns} FROM {table}').fetchall(), key=repr) for table, columns in tables.items()}

    def test_pre_change_linux_database_migrates_and_repeats_without_change(self):
        for name in ('config.json', 'layout.json', 'scene-state.json'):
            # The fixture copies carry a suffix so the private-state ignore rules do not hide them.
            shutil.copyfile(FIXTURE / name.replace('.json', '-fixture.json'), self.directory / name)
        with contextlib.closing(sqlite3.connect(self.directory / 'status.sqlite')) as db:
            db.executescript((FIXTURE / 'status.sql').read_text())
            before = self.rows(db)
            self.assertNotIn('device', [row[1] for row in db.execute('PRAGMA table_info(slots)')])
        expectations = json.loads((FIXTURE / 'fixture.json').read_text())
        scene_before = (self.directory / 'scene-state.json').read_bytes()
        with contextlib.closing(database.connect_state(self.directory)) as db:
            first = self.rows(db)
            for table in ('slots', 'comets', 'line_prefs', 'map_settings', 'map_pending', 'locate', 'display_v3'):
                with self.subTest(table=table):
                    self.assertEqual(db.execute(f'SELECT DISTINCT device FROM {table}').fetchall(), [('wall',)])
            dump_one = list(db.iterdump())
        with contextlib.closing(database.connect_state(self.directory)) as db:
            dump_two = list(db.iterdump())
            second = self.rows(db)
        self.assertEqual(first, before)
        self.assertEqual(second, before)
        self.assertEqual(dump_one, dump_two)
        self.assertEqual((self.directory / 'scene-state.json').read_bytes(), scene_before)
        self.assertEqual(before['activity'], [('task-blocked', 't1', 'blocked', 1002.0), ('task-question', 't1', 'question', 1002.7),
                                              ('task-unread', 't1', 'unread', 1004.0), ('task-unread-2', 't1', 'unread', 1006.0),
                                              ('task-working', 't1', 'working', 1000.0)])
        self.assertEqual(before['line_prefs'], [('100:101', 'project-a', 1), ('102:103', 'project-a', 0), ('104:105', 'project-b', 1)])
        self.assertEqual(before['map_settings'], [('project', 'status', 90, 1, 0)])
        self.assertEqual(before['task_info'][4][3:5], ('project-a', 'project-a'))
        config = configuration.load_config(self.directory)
        self.assertEqual((config['device'], len(config['line_groups'])), ('wall', 15))
        restorer = b.SceneRestorer(self.directory, config)
        self.assertEqual(restorer.state['scene'], {'name': 'Fixture Scene', 'brightness': 43})
        import controller_state
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            self.assertEqual(controller_state.credential(db, expectations['controllerToken']), ('codex', ['read', 'control']))
            self.assertEqual(store.control_state(db), {'mode': 'work', 'revision': 2, 'applied': 2, 'wave_cutoff': 995.0, 'error': None})
            self.assertEqual(b.current_comet(db, 1011.0), expectations['comet'])
            self.assertEqual(wall.pending(db)['lines'], {expectations['cometSourceLine']: {'project': 'project-b'}})
            self.assertEqual(wall.owners(db, config)[:3], [('project-a', 1), ('project-a', 0), ('project-b', 1)])
            self.assertEqual(wall.locate_state(db, config, 1011.0, 'work'), None)  # an active comet defers Locate
            self.assertEqual(db.execute('SELECT session, slot FROM slots ORDER BY slot').fetchall(),
                             [('task-working', 0), ('task-blocked', 2), ('task-question', 3), ('task-unread', 4), ('task-unread-2', 5)])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM controller_requests WHERE phase='done'").fetchone(), (1,))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM integration_requests WHERE phase='done'").fetchone(), (1,))

    def test_pre_change_shared_input_backup_restores_after_migration(self):
        import shared_input
        for name in ('config.json', 'layout.json', 'scene-state.json'):
            shutil.copyfile(FIXTURE / name.replace('.json', '-fixture.json'), self.directory / name)
        backup = {'sessions': [['legacy', 'turn', 'working', 900.0]], 'slots': [['legacy', 7]], 'waits': [],
                  'activity': [['legacy', 'turn', 'working', 900.0]], 'receipts': [], 'comets': [['legacy', 'turn', 901.0, 7, 902.0]],
                  'task_info': [['legacy', 'Old title', '', None, None, 'turn', 900.0]]}
        with contextlib.closing(sqlite3.connect(self.directory / 'status.sqlite')) as db:
            db.executescript((FIXTURE / 'status.sql').read_text())
            db.execute("UPDATE shared_input SET source='shared', backup=? WHERE id=1", (json.dumps(backup),))
            db.commit()
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            shared_input.restore_tables(db, backup)
            self.assertEqual(db.execute('SELECT session, slot, device FROM slots').fetchall(), [('legacy', 7, 'wall')])
            self.assertEqual(db.execute('SELECT session, source, started, device FROM comets').fetchall(), [('legacy', 7, 902.0, 'wall')])
            restored = shared_input.dump_tables(db)
            shared_input.restore_tables(db, restored)
            self.assertEqual(shared_input.dump_tables(db), restored)

    def test_backup_names_every_column_in_table_order(self):
        # Older sources restore a backup positionally, so its named columns keep each table's order.
        import shared_input
        for name in ('config.json', 'layout.json', 'scene-state.json'):
            shutil.copyfile(FIXTURE / name.replace('.json', '-fixture.json'), self.directory / name)
        migrated = self.directory / 'migrated'
        migrated.mkdir()
        with contextlib.closing(sqlite3.connect(migrated / 'status.sqlite')) as db:
            db.executescript((FIXTURE / 'status.sql').read_text())
        for directory in (self.directory, migrated):
            with contextlib.closing(database.connect_state(directory)) as db:
                for table, names in shared_input.BACKUP.items():
                    with self.subTest(directory=directory.name, table=table):
                        self.assertEqual(names, tuple(devices.columns(db, table)))

    def test_rows_saved_before_the_device_key_belong_to_the_original_device(self):
        self.assertEqual(devices.legacy_row('slots', ['a', 7]), {'session': 'a', 'slot': 7, 'device': 'wall'})
        self.assertEqual(devices.legacy_row('comets', ['a', 't', 1.0, 2, None]),
                         {'session': 'a', 'turn': 't', 'queued': 1.0, 'source': 2, 'started': None, 'device': 'wall'})
        self.assertIsNone(devices.legacy_row('slots', ['a', 7, 'panels']))
        self.assertIsNone(devices.legacy_row('sessions', ['a', 't', 'working', 1.0]))

    def test_device_aware_backup_restores_each_devices_rows(self):
        import shared_input
        self.write_two_devices()
        backup = {'sessions': [['a', 't', 'working', 900.0], ['b', 't', 'unread', 901.0]],
                  'slots': [['a', 0, 'wall'], ['a', 2, 'panels'], ['b', 1, 'panels']],
                  'waits': [['a', 't', 'permission:shell', 'permission', 'shell']],
                  'activity': [['a', 't', 'working', 900.0], ['b', 't', 'unread', 901.0]],
                  'receipts': [['b', 't', 901.0, 0]],
                  'comets': [['b', 't', 902.0, 1, 903.0, 'panels'], ['b', 't', 902.0, None, None, 'wall']],
                  'task_info': [['a', 'Title', '/synthetic', 'p', 'q', 't', 900.0]]}
        for _ in range(2):  # Repeated initialization keeps the restored rows.
            with contextlib.closing(database.connect_state(self.directory)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                shared_input.restore_tables(db, backup)
                self.assertEqual(shared_input.dump_tables(db), backup)
        self.assertEqual(self.query('SELECT device, session, source, started FROM comets ORDER BY device'),
                         [('panels', 'b', 1, 903.0), ('wall', 'b', None, None)])
        self.assertEqual(self.query('SELECT device, session, slot FROM slots ORDER BY device, slot'),
                         [('panels', 'b', 1), ('panels', 'a', 2), ('wall', 'a', 0)])

    # AC6: untargeted callers
    def test_untargeted_callers_address_default_device(self):
        self.write_two_devices()
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            self.assertEqual(wall.settings(db), wall.settings(db, devices.DEFAULT))
            self.assertEqual(devices.DEFAULT, 'wall')
            wall.apply_patch(db, {'settings': {'style': 'project'}})
            self.assertEqual(wall.settings(db, 'wall')['style'], 'project')
            self.assertEqual(wall.settings(db, 'panels')['style'], 'classic')
            db.execute("INSERT OR REPLACE INTO locate (line_id, started, device) VALUES ('5:6', NULL, 'wall')")
            self.assertEqual(wall.locate_state(db, configuration.load_config(self.directory), 1000.0, 'work'), {'source': 0, 'started': 1000.0})
            self.assertIsNone(wall.locate_state(db, configuration.load_config(self.directory, 'panels'), 1000.0, 'work'))
        self.assertEqual(modes.get_status(self.directory), modes.get_status(self.directory, device='wall'))


if __name__ == '__main__':
    unittest.main()
