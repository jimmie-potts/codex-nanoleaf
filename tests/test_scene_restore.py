import copy
import contextlib
import json
from pathlib import Path
import tempfile
import unittest

from test_bridge import b, Clock, decode
import database
import jsonfile


class Device:
    def __init__(self, clock):
        self.clock = clock
        self.names = ['Beach Waves', 'Cotton Candy']
        self.selected = 'Beach Waves'
        self.brightness = 43
        self.on = True
        self.calls = []
        self.fail = None
        self.lose_selection_reply = False

    def request(self, config, method, endpoint='', payload=None):
        self.calls.append((self.clock.now(), method, endpoint, copy.deepcopy(payload)))
        if self.fail and self.fail(method, endpoint, payload):
            self.fail = None
            raise OSError('Device unavailable')
        if method == 'GET' and endpoint == '/effects':
            return {'select': self.selected, 'effectsList': list(self.names)}
        if method == 'GET' and endpoint == '/state':
            return {'brightness': {'value': self.brightness}, 'on': {'value': self.on}}
        if method == 'PUT' and endpoint == '/state':
            if 'brightness' in payload:
                self.brightness = payload['brightness']['value']
            if 'on' in payload:
                self.on = payload['on']['value']
        elif method == 'PUT' and endpoint == '/effects':
            if 'select' in payload:
                assert payload['select'] in self.names
                self.selected = payload['select']
                if self.lose_selection_reply:
                    self.lose_selection_reply = False
                    raise OSError('Response lost after selection succeeded')
            else:
                self.selected = '*Dynamic*' if payload['write']['animType'] == 'custom' else '*Static*'
        else:
            raise AssertionError((method, endpoint))


class SceneTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.clock = Clock()
        self.device = Device(self.clock)
        self.config = {'ip': '192.168.1.207', 'token': 'PRIVATE_TEST_TOKEN',
                       'line_groups': [[100+i*2, 101+i*2] for i in range(15)],
                       'line_positions': [[i*10, 0] for i in range(15)]}
        (self.directory/'config.json').write_text(json.dumps(self.config))
        (self.directory/'layout.json').write_text(json.dumps({
            key: self.config[key] for key in ('line_groups', 'line_positions')}))
        self.active = [('working', 1000)] + [None]*14
        self.idle = [None]*15
        self.unread = set()

    def manager(self):
        return b.SceneRestorer(self.directory, self.config, request=self.device.request)

    def saved(self):
        return json.loads((self.directory/'scene-state.json').read_text())

    def event(self, name, session='a', **kwargs):
        b.handle_event(self.directory, {'hook_event_name': name, 'session_id': session,
                       'turn_id': '1', **kwargs}, launch=lambda _: None, now=self.clock.now)

    def query(self, sql):
        with contextlib.closing(database.connect_state(self.directory)) as db:
            return db.execute(sql).fetchall()

    def run_worker(self, scheduled=()):
        pending = list(scheduled)
        deadline = self.clock.now()+25
        def advance(seconds):
            self.clock.sleep(seconds)
            self.assertLess(self.clock.now(), deadline, 'Worker did not release control after idle')
            while pending and self.clock.now() >= pending[0][0]:
                _, action = pending.pop(0)
                action()
        b.run_worker(self.directory, sleep=advance, now=self.clock.now, request=self.device.request,
                     read_unread=lambda: self.unread)
        self.assertEqual(pending, [])

    def test_scene_and_brightness_survive_takeover_and_worker_restart(self):
        first = self.manager()
        self.assertTrue(first.observe())
        first.send(self.config, self.active, 1000, False)
        self.assertEqual(self.device.selected, '*Dynamic*')
        self.assertEqual(self.device.brightness, 30)
        self.assertEqual(self.saved()['scene'], {'name': 'Beach Waves', 'brightness': 43})
        restarted = self.manager()
        self.assertFalse(restarted.observe())
        restarted.send(self.config, self.idle, 1005, True)
        self.assertEqual((self.device.selected, self.device.brightness), ('Beach Waves', 43))
        self.assertFalse(self.saved()['owned'])

    def test_temporary_indicators_never_replace_saved_scene(self):
        manager = self.manager()
        manager.observe()
        for status in b.COLORS:
            manager.send(self.config, [(status, 1000)]+[None]*14, 1000, True)
            self.assertFalse(manager.observe())
            self.assertEqual(self.saved()['scene'], {'name': 'Beach Waves', 'brightness': 43})

    def test_first_viewed_task_goes_to_base_and_only_last_read_restores_scene(self):
        self.event('UserPromptSubmit', 'a')
        self.event('UserPromptSubmit', 'b')
        def finish_a():
            self.unread.add('a')
            self.event('Stop', 'a')
        def finish_b():
            self.unread.add('b')
            self.event('Stop', 'b')
        self.run_worker([(1003, finish_a), (1005, finish_b),
                         (1007, lambda: self.unread.remove('a')),
                         (1009, lambda: self.unread.clear())])
        frames = [(when, decode(payload)) for when, method, endpoint, payload in self.device.calls
                  if method == 'PUT' and endpoint == '/effects' and 'write' in payload]
        between_reads = [panels for when, panels in frames if 1007 <= when < 1009]
        self.assertTrue(between_reads)
        for panels in between_reads:
            self.assertEqual({tuple(f[:3]) for f in panels[100]}, {b.BASELINE})
            dim = tuple(round(c * b.MIN_BRIGHTNESS) for c in b.COLORS['unread'])
            self.assertIn(dim, {tuple(f[:3]) for f in panels[102]})
        restorations = [when for when, method, _, payload in self.device.calls
                        if method == 'PUT' and payload.get('select') == 'Beach Waves']
        self.assertEqual(len(restorations), 1)
        self.assertGreaterEqual(restorations[0], 1009)
        self.assertEqual((self.device.selected, self.device.brightness), ('Beach Waves', 43))
        self.assertEqual(dict(self.query('SELECT id,status FROM sessions')), {'a': 'ended', 'b': 'ended'})

    def test_scene_change_during_quiet_work_becomes_restore_target_without_new_hooks(self):
        self.event('UserPromptSubmit')
        def choose_scene():
            self.device.selected, self.device.brightness = 'Cotton Candy', 66
        def check_capture():
            self.assertEqual(self.saved()['scene'], {'name': 'Cotton Candy', 'brightness': 66})
            self.assertEqual(self.device.selected, '*Dynamic*')
            self.assertEqual(self.query('SELECT started FROM activity'), [(1000.0,)])
        self.run_worker([(1003, choose_scene), (1004.5, check_capture),
                         (1006, lambda: self.event('Interrupt'))])
        self.assertEqual((self.device.selected, self.device.brightness), ('Cotton Candy', 66))

    def test_idle_hooks_leave_scene_running_without_restarting_it(self):
        self.run_worker()
        self.device.selected, self.device.brightness = 'Cotton Candy', 57
        self.device.calls.clear()
        self.run_worker()
        self.assertFalse(any(method == 'PUT' for _, method, _, _ in self.device.calls))
        self.assertEqual(self.saved()['scene'], {'name': 'Cotton Candy', 'brightness': 57})

    def test_no_initial_scene_uses_blue_until_user_chooses_one(self):
        self.device.selected = '*Dynamic*'
        manager = self.manager()
        manager.observe()
        manager.send(self.config, self.active, 1000, True)
        self.assertIsNone(self.saved()['scene'])
        manager.send(self.config, self.idle, 1004, True)
        self.assertEqual(self.device.selected, '*Static*')
        self.device.selected, self.device.brightness = 'Cotton Candy', 64
        manager.observe()
        manager.send(self.config, self.active, 1005, True)
        manager.send(self.config, self.idle, 1010, True)
        self.assertEqual((self.device.selected, self.device.brightness), ('Cotton Candy', 64))

    def test_failed_restore_keeps_target_for_retry(self):
        manager = self.manager()
        manager.observe()
        manager.send(self.config, self.active, 1000, True)
        self.device.fail = lambda method, endpoint, payload: method == 'PUT' and endpoint == '/effects'
        with self.assertRaises(OSError):
            manager.send(self.config, self.idle, 1003, True)
        self.assertTrue(self.saved()['owned'])
        retried = self.manager()
        retried.observe()
        retried.send(self.config, self.idle, 1005, True)
        self.assertEqual((self.device.selected, self.device.brightness), ('Beach Waves', 43))
        self.assertFalse(self.saved()['owned'])

    def test_lost_restore_response_does_not_recapture_indicator_brightness(self):
        manager = self.manager()
        manager.observe()
        manager.send(self.config, self.active, 1000, True)
        self.device.lose_selection_reply = True
        with self.assertRaises(OSError):
            manager.send(self.config, self.idle, 1003, True)
        retried = self.manager()
        retried.observe()
        retried.send(self.config, self.idle, 1005, True)
        self.assertEqual(self.saved()['scene'], {'name': 'Beach Waves', 'brightness': 43})
        self.assertFalse(self.saved()['owned'])

    def test_capture_failure_leaves_original_scene_untouched(self):
        self.event('UserPromptSubmit')
        self.device.fail = lambda method, endpoint, payload: method == 'GET' and endpoint == '/state'
        with self.assertRaises(OSError):
            self.run_worker()
        self.assertFalse(any(method == 'PUT' for _, method, _, _ in self.device.calls))
        self.assertEqual(self.device.selected, 'Beach Waves')
        self.assertTrue(self.query("SELECT value FROM meta WHERE key='dirty'"))

    def test_deleted_scene_returns_to_blue_without_selecting_invalid_name(self):
        manager = self.manager()
        manager.observe()
        manager.send(self.config, self.active, 1000, True)
        self.device.names.remove('Beach Waves')
        manager.observe()
        manager.send(self.config, self.idle, 1003, True)
        self.assertEqual(self.device.selected, '*Static*')
        self.assertFalse(self.saved()['owned'])

    def test_scene_state_contains_no_credentials_or_task_contents(self):
        manager = self.manager()
        manager.observe()
        manager.send(self.config, self.active, 1000, True)
        saved = self.saved()
        self.assertEqual(set(saved), {'version', 'scene', 'owned', 'quiet_scene', 'quiet_brightness'})
        self.assertEqual(set(saved['scene']), {'name', 'brightness'})
        self.assertNotIn('PRIVATE_TEST_TOKEN', json.dumps(saved))

    def test_legacy_quiet_state_file_keeps_remembered_brightness_after_upgrade(self):
        # Files written before the recorded level existed only ever dimmed to 10.
        jsonfile.write_json(self.directory / 'scene-state.json',
                     {'version': 1, 'scene': {'name': 'Beach Waves', 'brightness': 43}, 'owned': True, 'quiet_scene': 'Beach Waves'})
        self.device.brightness = 10
        manager = self.manager()
        self.assertEqual(manager.state['quiet_brightness'], 10)
        manager.observe()
        self.assertEqual(self.saved()['scene'], {'name': 'Beach Waves', 'brightness': 43})
        manager.send(dict(self.config, _mode='free'), self.idle, 1000, True)
        self.assertEqual(self.device.brightness, 43)
        jsonfile.write_json(self.directory / 'scene-state.json', {'version': 1, 'scene': None, 'owned': False, 'quiet_scene': None, 'quiet_brightness': 101})
        with self.assertRaises(ValueError):
            self.manager()

    def test_upgrade_adopts_cached_indicators_before_restoring_idle_baseline(self):
        self.event('UserPromptSubmit')
        self.device.selected = '*Dynamic*'
        self.clock.value = 1004
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            snapshot = b.dashboard(db, self.config, 1004)
            db.execute('INSERT INTO display_v3 (snapshot, looping, rendered) VALUES (?, 1, 1004)', (json.dumps(snapshot),))
        self.run_worker([(1007, lambda: self.event('Interrupt'))])
        self.assertEqual(self.device.selected, '*Static*')
        self.assertFalse(self.saved()['owned'])


if __name__ == '__main__':
    unittest.main()
