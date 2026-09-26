import contextlib
import json
import unittest
from unittest.mock import patch
from test_bridge import b, decode
import database
import modes
import test_scene_restore as scene_tests


class ModeTest(unittest.TestCase):
    setUp = scene_tests.SceneTest.setUp
    manager = scene_tests.SceneTest.manager
    saved = scene_tests.SceneTest.saved
    event = scene_tests.SceneTest.event
    query = scene_tests.SceneTest.query
    run_worker = scene_tests.SceneTest.run_worker

    def mode(self, name):
        modes.set_mode(self.directory, name, launch=lambda _: None, now=self.clock.now)

    def test_default_duplicate_and_persistence(self):
        self.event('UserPromptSubmit')
        self.assertEqual(modes.get_status(self.directory)['mode'], 'work')
        self.mode('free')
        first = self.query("SELECT value FROM meta WHERE key='mode_revision'")
        self.mode('free')
        self.assertEqual(self.query("SELECT value FROM meta WHERE key='mode_revision'"), first)
        self.assertTrue(modes.get_status(self.directory)['pending'])
        self.run_worker()
        self.assertEqual(modes.get_status(self.directory), {'mode': 'free', 'pending': False, 'error': None})

    def test_free_releases_once_and_never_requests_lights_on_events(self):
        manager = self.manager()
        manager.observe()
        manager.send(self.config, self.active, 1000, True)
        self.event('UserPromptSubmit')
        self.mode('free')
        self.run_worker()
        self.assertEqual((self.device.selected, self.device.brightness), ('Beach Waves', 43))
        self.device.calls.clear()
        self.event('PermissionRequest', tool_name='exec_command')
        self.run_worker()
        self.event('Stop')
        self.run_worker()
        self.assertEqual(self.device.calls, [])

    def test_read_receipts_clear_in_free_without_light_requests(self):
        self.event('UserPromptSubmit')
        self.mode('free')
        self.run_worker()
        self.device.calls.clear()
        self.unread = {'a'}
        self.event('Stop')
        self.run_worker([(1002, lambda: self.unread.clear())])
        self.assertEqual(self.query('SELECT * FROM receipts'), [])
        self.assertEqual(self.device.calls, [])

    def test_quiet_frames_are_steady_paired_colors(self):
        config = dict(self.config, _mode='quiet')
        snap = [('working', 1000), ('question', 1000), ('blocked', 1000), ('unread', 1000)] + [None]*11
        data = b.effect_payload(config, snap, 1000, True)
        self.assertEqual(data['write']['animType'], 'static')
        self.assertFalse(data['write']['loop'])
        panels = decode(data)
        for i, pair in enumerate(config['line_groups']):
            self.assertEqual(panels[pair[0]], panels[pair[1]])
            self.assertEqual(len(panels[pair[0]]), 1)
            expected = b.COLORS[snap[i][0]] if snap[i] else b.BASELINE
            self.assertEqual(tuple(panels[pair[0]][0][:3]), expected)

    def test_quiet_idle_preserves_original_brightness_across_restart(self):
        m = self.manager()
        m.observe()
        quiet = dict(self.config, _mode='quiet')
        m.send(quiet, self.idle, 1000, True)
        self.assertEqual(self.device.brightness, 10)
        m = self.manager()
        m.observe()
        self.assertEqual(self.saved()['scene']['brightness'], 43)
        self.device.calls.clear()
        m.send(dict(self.config, _mode='free'), self.idle, 1001, True)
        self.assertEqual(self.device.brightness, 43)
        self.assertFalse(any(call[2] == '/effects' for call in self.device.calls))

    def test_quiet_to_work_active_does_not_capture_dim_brightness(self):
        m = self.manager()
        m.observe()
        m.send(dict(self.config, _mode='quiet'), self.idle, 1000, True)
        m.observe()
        m.send(self.config, self.active, 1001, True)
        m.observe()
        m.send(self.config, self.idle, 1003, True)
        self.assertEqual(self.device.brightness, 43)

    def test_failed_quiet_takeover_preserves_original_brightness(self):
        m = self.manager()
        m.observe()
        m.send(dict(self.config, _mode='quiet'), self.idle, 1000, True)
        self.device.fail = lambda method, ep, payload: method == 'PUT' and ep == '/effects'
        with self.assertRaises(OSError):
            m.send(self.config, self.active, 1001, True)
        m = self.manager()
        m.observe()
        self.assertEqual(self.saved()['scene']['brightness'], 43)

    def test_return_to_work_skips_old_waves_preserves_slots(self):
        self.event('UserPromptSubmit')
        self.mode('free')
        self.run_worker()
        slots = self.query('SELECT * FROM slots')
        self.clock.sleep(0.2)
        self.mode('work')
        self.run_worker([(1002, lambda: self.event('Interrupt'))])
        self.assertEqual(self.query('SELECT * FROM slots'), slots)
        effects = [c[3] for c in self.device.calls if c[1] == 'PUT' and c[2] == '/effects' and 'write' in c[3]]
        for payload in effects:
            panels = decode(payload)
            for pair in self.config['line_groups'][1:]:
                self.assertTrue(all(tuple(f[:3]) == b.BASELINE for f in panels[pair[0]]))

    def test_rapid_mode_changes_apply_latest_only(self):
        self.event('UserPromptSubmit')
        self.mode('quiet')
        self.mode('work')
        self.mode('free')
        self.run_worker()
        self.assertEqual(modes.get_status(self.directory)['mode'], 'free')
        self.assertFalse(any(c[1] == 'PUT' for c in self.device.calls))

    def test_failed_handoff_remains_pending_and_retry_obeys_new_mode(self):
        m = self.manager()
        m.observe()
        m.send(self.config, self.active, 1000, True)
        self.event('UserPromptSubmit')
        self.mode('free')
        self.device.fail = lambda method, ep, payload: method == 'PUT'
        with self.assertRaises(OSError):
            self.run_worker()
        self.assertTrue(modes.get_status(self.directory)['pending'])
        self.mode('quiet')
        self.run_worker([(1002, lambda: self.mode('free'))])
        self.assertEqual(self.device.brightness, 43)
        self.assertFalse(modes.get_status(self.directory)['pending'])

    def test_mode_change_interrupts_preview(self):
        self.event('UserPromptSubmit')
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('preview','all')")
        self.run_worker([(1000.5, lambda: self.mode('free'))])
        self.assertLess(self.clock.now(), 1002)
        self.assertEqual(self.device.selected, 'Beach Waves')

    def test_free_leaves_external_stream_alone(self):
        m = self.manager()
        m.observe()
        m.send(self.config, self.active, 1000, True)
        self.device.selected = '*ExtControl*'
        self.event('UserPromptSubmit')
        self.mode('free')
        self.device.calls.clear()
        self.run_worker()
        self.assertFalse(any(c[1] == 'PUT' for c in self.device.calls))

    def test_quiet_new_scene_and_manual_brightness_become_preference(self):
        m = self.manager()
        m.observe()
        quiet = dict(self.config, _mode='quiet')
        m.send(quiet, self.idle, 1000, True)
        self.device.selected, self.device.brightness = 'Cotton Candy', 61
        m.observe()
        m.send(quiet, self.idle, 1001, True)
        self.assertEqual(self.device.brightness, 10)
        m.observe()
        m.send(dict(self.config, _mode='free'), self.idle, 1002, True)
        self.assertEqual((self.device.selected, self.device.brightness), ('Cotton Candy', 61))

    def test_quiet_idle_worker_does_not_repeat_writes(self):
        self.event('UserPromptSubmit')
        self.event('Interrupt')
        self.mode('quiet')
        calls = []
        self.run_worker([(1001, lambda: calls.append(len([c for c in self.device.calls if c[1] == 'PUT']))),
                         (1004, lambda: calls.append(len([c for c in self.device.calls if c[1] == 'PUT']))),
                         (1005, lambda: self.mode('free'))])
        self.assertEqual(calls[0], calls[1])

    def test_missing_scene_quiet_and_free_fallback(self):
        m = self.manager()
        self.device.selected = '*Dynamic*'
        m.observe()
        m.send(dict(self.config, _mode='quiet'), self.idle, 1000, True)
        self.assertEqual(self.device.brightness, 10)
        m.observe()
        m.send(dict(self.config, _mode='free'), self.idle, 1001, True)
        self.assertEqual(self.device.brightness, 30)
