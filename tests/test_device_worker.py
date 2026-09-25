"""Lines and NL22 Panels as independent devices under the existing worker (#43)."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_bridge import b, Clock, decode
from test_scene_restore import Device
import controller_server as server
import controller_state
import devices
import panels
import project_map as wall
import shared_input

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / 'tests/fixtures/nl22-panels-fixture.json').read_text())['panelLayout']
LINES_IP, PANELS_IP = '192.0.2.1', '192.0.2.2'


def triangles(count):
    reported = copy.deepcopy(FIXTURE)
    points = reported['layout']['positionData']
    points[:] = sorted(points, key=lambda p: (p['x'], p['y']))[:count]
    return panels.read_layout(reported)


class Devices:
    """Separate fake transports, addressed only by each device's configured address."""
    def __init__(self, clock):
        self.lines, self.panels = Device(clock), Device(clock)
        self.panels.names = ['Forest', 'Sunset']
        self.panels.selected, self.panels.brightness = 'Forest', 64

    def request(self, config, method, endpoint='', payload=None):
        target = {LINES_IP: self.lines, PANELS_IP: self.panels}[config['ip']]
        return target.request(config, method, endpoint, payload)


class DeviceWorkerTest(unittest.TestCase):
    def setUp(self, panel_count=18, order=('wall', 'panels')):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.clock = Clock()
        self.fake = Devices(self.clock)
        entries = {'wall': {'kind': 'lines', 'ip': LINES_IP, 'token_ref': 'token'},
                   'panels': {'kind': 'panels', 'ip': PANELS_IP, 'token_ref': 'panelsToken'}}
        b.write_json(self.directory / 'config.json', {
            'ip': LINES_IP, 'token': 'fakeLines', 'panelsToken': 'fakePanels',
            'devices': {name: entries[name] for name in order}})
        lines = devices.lines_entry([[100 + i * 2, 101 + i * 2] for i in range(15)], [[i * 10, 0] for i in range(15)])
        devices.save_layout(self.directory / 'layout.json', {'wall': lines, 'panels': triangles(panel_count)})
        self.unread = set()
        patcher = patch.object(b, 'light_request', self.fake.request)
        patcher.start()
        self.addCleanup(patcher.stop)

    def event(self, name, session='a', turn='1', **extra):
        b.handle_event(self.directory, {'hook_event_name': name, 'session_id': session, 'turn_id': turn, **extra},
                       launch=lambda _: None, now=self.clock.now)

    def mode(self, name, device='wall'):
        b.set_mode(self.directory, name, launch=lambda _: None, now=self.clock.now, device=device)

    def query(self, sql, *params):
        with contextlib.closing(b.connect_state(self.directory)) as db:
            return db.execute(sql, params).fetchall()

    def run_worker(self, device='wall', scheduled=(), read_unread=None):
        pending = list(scheduled)
        deadline = self.clock.now() + 25
        def advance(seconds):
            self.clock.sleep(seconds)
            self.assertLess(self.clock.now(), deadline, 'Worker did not release control')
            while pending and self.clock.now() >= pending[0][0]:
                pending.pop(0)[1]()
        reads = [0]
        def now():
            # A pass that loops without sleeping would otherwise hang the suite instead of failing.
            reads[0] += 1
            self.assertLess(reads[0], 3000, 'Worker looped without sleeping')
            return self.clock.now()
        result = b.run_worker(self.directory, sleep=advance, now=now,
                              read_unread=read_unread or (lambda: self.unread), device=device)
        self.assertEqual(pending, [])
        return result

    def effects(self, fake):
        return [payload for _, method, endpoint, payload in fake.calls
                if method == 'PUT' and endpoint == '/effects' and 'write' in payload]

    def slots(self, device):
        return dict(self.query('SELECT session, slot FROM slots WHERE device=?', device))

    def free_after(self, seconds, device):
        return [(self.clock.now() + seconds, lambda: self.mode('free', device))]


class LaunchAndTargetTest(DeviceWorkerTest):
    # AC9 and the linux-runtime writer requirement: one locked instance per device.
    def test_launch_starts_one_instance_per_registered_device(self):
        commands = []
        with patch.object(b.subprocess, 'Popen', lambda command, **options: commands.append(command)):
            b.launch_worker(self.directory)
        self.assertEqual([c[c.index('--device') + 1] for c in commands], ['wall', 'panels'])
        self.assertTrue(all(c[2] == 'worker' for c in commands))

    def test_unreadable_registry_launches_the_original_device(self):
        (self.directory / 'config.json').write_text('{')
        commands = []
        with patch.object(b.subprocess, 'Popen', lambda command, **options: commands.append(command)):
            b.launch_worker(self.directory)
        self.assertEqual([c[c.index('--device') + 1] for c in commands], ['wall'])

    def test_second_instance_for_a_device_exits_without_sending(self):
        self.event('UserPromptSubmit')
        with contextlib.closing(sqlite3.connect(self.directory / 'notification-lock.panels.sqlite')) as lock:
            lock.execute('BEGIN EXCLUSIVE')
            self.assertIs(self.run_worker('panels'), False)
            self.assertEqual(self.fake.panels.calls, [])
            self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertTrue(self.effects(self.fake.lines))
        self.assertFalse((self.directory / 'notification-lock.wall.sqlite').exists())

    # AC6: explicit CLI targets, Lines by default, unknown targets rejected.
    def cli(self, *arguments):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['bridge.py', *arguments, '--state-dir', str(self.directory)]), \
                patch.object(b, 'launch_worker', lambda directory: None), contextlib.redirect_stdout(output):
            b.main()
        return output.getvalue()

    def test_cli_mode_and_status_accept_a_device_target(self):
        self.cli('mode', 'quiet', '--device', 'panels')
        self.assertEqual(b.get_status(self.directory, 'panels')['mode'], 'quiet')
        self.assertEqual(b.get_status(self.directory)['mode'], 'work')
        self.assertEqual(json.loads(self.cli('status', '--device', 'panels'))['mode'], 'quiet')
        self.assertEqual(json.loads(self.cli('status'))['mode'], 'work')
        self.cli('mode', 'free')
        self.assertEqual(b.get_status(self.directory)['mode'], 'free')
        self.assertEqual(b.get_status(self.directory, 'panels')['mode'], 'quiet')

    def test_unknown_target_is_rejected_without_state_change(self):
        before = self.query('SELECT key, value FROM meta ORDER BY key')
        for arguments in (('mode', 'free', '--device', 'missing'), ('status', '--device', 'missing'),
                          ('mode', 'free', '--device', '../x')):
            with self.subTest(arguments), self.assertRaises(SystemExit) as raised, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.cli(*arguments)
            self.assertNotEqual(raised.exception.code, 0)
        self.assertEqual(self.query('SELECT key, value FROM meta ORDER BY key'), before)


class UninstallTest(DeviceWorkerTest):
    def test_uninstall_frees_every_device_and_rejects_a_target(self):
        codex = self.directory / 'codex'
        codex.mkdir()
        self.event('UserPromptSubmit')
        with patch.dict('os.environ', {'CODEX_HOME': str(codex)}), \
                patch.object(b, 'launch_worker', lambda directory: None), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with patch.object(sys, 'argv', ['bridge.py', 'setup', '--uninstall', '--device', 'panels',
                                            '--state-dir', str(self.directory)]), self.assertRaises(SystemExit):
                b.main()
            self.assertFalse((codex / 'hooks.json').exists())
            self.assertEqual(b.get_status(self.directory, 'panels')['mode'], 'work')
            with patch.object(sys, 'argv', ['bridge.py', 'setup', '--uninstall', '--state-dir', str(self.directory)]):
                b.main()
        self.assertEqual((b.get_status(self.directory)['mode'], b.get_status(self.directory, 'panels')['mode']),
                         ('free', 'free'))


class UntargetedOrderTest(DeviceWorkerTest):
    def setUp(self):
        super().setUp(order=('panels', 'wall'))

    def test_untargeted_calls_address_lines_whatever_the_registry_order(self):
        self.assertEqual(b.load_config(self.directory)['device'], 'wall')
        with patch.object(sys, 'argv', ['bridge.py', 'mode', 'quiet', '--state-dir', str(self.directory)]), \
                patch.object(b, 'launch_worker', lambda directory: None), contextlib.redirect_stdout(io.StringIO()):
            b.main()
        self.assertEqual((b.get_status(self.directory)['mode'], b.get_status(self.directory, 'panels')['mode']), ('quiet', 'work'))


class MirroredTest(DeviceWorkerTest):
    # AC1: one element per device, independent capacity and waiting lists.
    def test_one_task_occupies_one_element_on_each_device(self):
        self.event('UserPromptSubmit')
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertEqual(len(self.slots('wall')), 1)
        self.assertEqual(len(self.slots('panels')), 1)
        lines_frames, panel_frames = decode(self.effects(self.fake.lines)[0]), decode(self.effects(self.fake.panels)[0])
        self.assertEqual(len(lines_frames), 30)
        self.assertEqual(len(panel_frames), 18)
        green = lambda frames: {zone for zone, steps in frames.items() if any(s[0] == s[2] == 0 < s[1] for s in steps)}
        self.assertEqual(len(green(panel_frames)), 18)  # The first wave crosses every triangle.
        # Lines runs later on the same shared epoch: its Line stays green, and the obsolete wave is not replayed.
        self.assertEqual(len(green(lines_frames)), 2)
        self.assertEqual(self.query("SELECT COUNT(*) FROM activity")[0][0], 1)

    def test_layout_save_keeps_the_other_devices_entry(self):
        path = self.directory / 'layout.json'
        stale = devices.layout_devices(json.loads(path.read_text()))
        del stale['panels']
        devices.save_device_layout(path, 'wall', stale['wall'])
        saved = devices.layout_devices(json.loads(path.read_text()))
        self.assertEqual(sorted(saved), ['panels', 'wall'])
        self.assertEqual(len(saved['panels']['elements']), 18)

    def test_scene_restoration_is_per_device(self):
        self.event('UserPromptSubmit')
        self.run_worker('panels', self.free_after(3, 'panels'))
        saved = json.loads((self.directory / 'scene-state.panels.json').read_text())
        self.assertEqual(saved['scene'], {'name': 'Forest', 'brightness': 64})
        self.assertFalse((self.directory / 'scene-state.json').exists())
        self.assertEqual((self.fake.panels.selected, self.fake.panels.brightness), ('Forest', 64))
        self.assertEqual(self.fake.lines.calls, [])


class SmallPanelsTest(DeviceWorkerTest):
    def setUp(self):
        super().setUp(panel_count=6)

    def test_full_panels_device_waits_without_moving_tasks(self):
        for n in range(9):
            self.event('UserPromptSubmit', f's{n}')
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertEqual(len(self.slots('panels')), 6)
        self.assertEqual(len(self.slots('wall')), 9)
        panel_slots = self.slots('panels')
        # A failing Panels device never gives its tasks to Lines or takes Lines' tasks.
        self.mode('work', 'panels')
        self.fake.panels.fail = lambda method, endpoint, payload: True
        with self.assertRaises(OSError):
            self.run_worker('panels')
        self.assertEqual(self.slots('panels'), panel_slots)
        self.assertEqual(len(self.slots('wall')), 9)


class EvidenceTest(DeviceWorkerTest):
    # AC2: shared completion and read evidence, device-scoped comet queues.
    def complete(self, session='a'):
        self.event('UserPromptSubmit', session)
        self.event('Stop', session)
        self.unread.add(session)

    def test_completion_queues_one_comet_per_work_device(self):
        self.mode('quiet', 'panels')
        self.complete()
        self.assertEqual(self.query('SELECT device FROM comets'), [('wall',)])
        self.mode('work', 'panels')
        self.complete('b')
        self.assertEqual(sorted(self.query("SELECT device FROM comets WHERE session='b'")), [('panels',), ('wall',)])

    def read_after(self, seconds):
        return [(self.clock.now() + seconds, self.unread.clear)]

    def test_reading_clears_both_devices_and_drops_queued_comets(self):
        self.complete()
        self.run_worker('wall', self.read_after(2.5))
        self.assertEqual(self.query("SELECT status FROM sessions"), [('ended',)])
        self.assertEqual(self.query('SELECT device FROM comets'), [('panels',)])
        self.run_worker('panels')
        self.assertEqual(self.query('SELECT device FROM comets'), [])
        self.assertTrue(all((255, 255, 255) not in {tuple(f[:3]) for f in frames}
                            for payload in self.effects(self.fake.panels) for frames in decode(payload).values()))

    def test_panels_plays_its_own_comet_from_its_own_triangle(self):
        self.complete()
        self.run_worker('panels', self.read_after(2.5))
        self.assertEqual(self.query("SELECT device FROM comets"), [('wall',)])
        white = [payload for payload in self.effects(self.fake.panels)
                 if any((255, 255, 255) in {tuple(f[:3]) for f in frames} for frames in decode(payload).values())]
        self.assertEqual(len(white), 1)
        self.assertEqual(self.fake.lines.calls, [])


class ModesTest(DeviceWorkerTest):
    # AC3: independent modes, Free handoff and scoped clears.
    def test_panels_free_handoff_leaves_lines_rendering(self):
        self.event('UserPromptSubmit')
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.assertEqual((self.fake.panels.selected, self.fake.panels.brightness), ('Forest', 64))
        self.fake.panels.calls.clear()
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            wall.request_patch(db, {'settings': {'coverage': 'status'}}, b.load_config(self.directory))
        self.event('PermissionRequest', tool_name='exec_command')
        self.run_worker('panels')
        self.assertEqual(self.fake.panels.calls, [])
        self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertTrue(self.effects(self.fake.lines))
        self.assertEqual(self.fake.panels.calls, [])
        self.assertEqual(b.get_status(self.directory, 'panels'), {'mode': 'free', 'pending': False, 'error': None})

    def test_panels_free_keeps_the_lines_comet_and_pending_edit(self):
        self.event('UserPromptSubmit')
        self.event('Stop')
        self.unread.add('a')
        lines = b.load_config(self.directory)
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("UPDATE comets SET source=0, started=? WHERE device='wall'", (self.clock.now(),))
            db.execute("INSERT INTO slots (session, slot, device) VALUES ('a', 0, 'wall')")
            self.assertTrue(wall.request_patch(db, {'settings': {'style': 'project'}}, lines))
        self.mode('free', 'panels')
        self.run_worker('panels', [(self.clock.now() + 1, self.unread.clear)])
        self.assertEqual(self.query("SELECT device, started IS NOT NULL FROM comets"), [('wall', 1)])
        self.assertEqual(self.query("SELECT device FROM map_pending"), [('wall',)])
        self.assertEqual(b.get_status(self.directory)['mode'], 'work')

    def test_unread_completion_shows_unread_color_on_both_devices(self):
        self.mode('quiet', 'wall')
        self.mode('quiet', 'panels')
        self.event('UserPromptSubmit')
        self.event('Stop')
        self.unread.add('a')
        class Stop(Exception):
            pass
        def stop_after_a_pass(seconds):
            raise Stop()
        for device in ('wall', 'panels'):
            with self.assertRaises(Stop):  # The unread task keeps each worker watching; stop after one pass.
                b.run_worker(self.directory, sleep=stop_after_a_pass, now=self.clock.now,
                             read_unread=lambda: self.unread, device=device)
        for fake, device in ((self.fake.lines, 'wall'), (self.fake.panels, 'panels')):
            slot = self.slots(device)['a']
            zones = b.load_config(self.directory, device)['elements'][slot]['zones']
            first = decode(self.effects(fake)[0])
            self.assertEqual({tuple(first[z][0][:3]) for z in zones}, {b.COLORS['unread']})

    def test_panels_scene_returns_after_a_recoverable_failure(self):
        self.event('UserPromptSubmit')
        self.fake.panels.fail = lambda method, endpoint, payload: method == 'PUT'
        with self.assertRaises(OSError):
            self.run_worker('panels')
        self.event('Stop')
        self.run_worker('panels', [(self.clock.now() + 3, self.unread.clear)])
        self.assertEqual((self.fake.panels.selected, self.fake.panels.brightness), ('Forest', 64))
        self.assertEqual(self.fake.lines.calls, [])

    def test_quiet_on_one_device_keeps_the_other_in_work(self):
        self.event('UserPromptSubmit')
        self.mode('quiet', 'panels')
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.run_worker('wall', self.free_after(3, 'wall'))
        brightness = lambda fake: [p['brightness']['value'] for _, m, e, p in fake.calls if m == 'PUT' and e == '/state' and 'on' in p]
        self.assertEqual(brightness(self.fake.panels)[0], 10)
        self.assertEqual(brightness(self.fake.lines)[0], 30)
        self.assertEqual(self.effects(self.fake.panels)[0]['write']['animType'], 'static')
        self.assertEqual(self.effects(self.fake.lines)[0]['write']['animType'], 'custom')

    def test_refresh_clears_only_its_target_display_cache(self):
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            for device in ('wall', 'panels'):
                db.execute('INSERT INTO display_v3 (snapshot, looping, rendered, device) VALUES (?,1,0,?)', ('x', device))
        args = ['bridge.py', 'setup', '--refresh', '--device', 'panels', '--state-dir', str(self.directory)]
        with patch.object(sys, 'argv', args), patch.object(b, 'launch_worker', lambda directory: None):
            b.main()
        self.assertEqual(self.query('SELECT device FROM display_v3'), [('wall',)])

    def test_reset_says_it_resets_every_device(self):
        self.event('UserPromptSubmit')
        output = io.StringIO()
        args = ['bridge.py', 'setup', '--reset', '--state-dir', str(self.directory)]
        with patch.object(sys, 'argv', args), patch.object(b, 'launch_worker', lambda directory: None), \
                contextlib.redirect_stdout(output):
            b.main()
        self.assertIn('every device', output.getvalue())
        self.assertEqual(self.query('SELECT COUNT(*) FROM slots'), [(0,)])

    def test_panels_preview_is_scoped_to_panels(self):
        self.mode('quiet', 'wall')
        args = ['bridge.py', 'setup', '--notify', '--device', 'panels', '--state-dir', str(self.directory)]
        with patch.object(sys, 'argv', args), patch.object(b, 'launch_worker', lambda directory: None), \
                contextlib.redirect_stdout(io.StringIO()):
            b.main()
        self.assertEqual(self.query("SELECT key FROM meta WHERE key LIKE 'preview%'"), [('preview@panels',)])
        self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertEqual(self.query("SELECT key FROM meta WHERE key LIKE 'preview%'"), [('preview@panels',)])
        self.run_worker('panels')
        self.assertEqual(self.query("SELECT key FROM meta WHERE key LIKE 'preview%'"), [])
        self.assertTrue(self.effects(self.fake.panels))


class LocateTest(DeviceWorkerTest):
    # AC12: an explicit Locate flashes one physical triangle and respects Panels' Free mode.
    def locate(self, element):
        import wall_server
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            wall_server.apply_operation(db, b, b.load_config(self.directory, 'panels'), '/api/locate', {'line': element})
            b.mark_dirty(db)

    def test_locate_flashes_one_triangle_on_panels_only(self):
        config = b.load_config(self.directory, 'panels')
        target = config['elements'][7]
        self.locate(target['id'])
        self.assertEqual(self.query('SELECT line_id, device FROM locate'), [(target['id'], 'panels')])
        self.run_worker('wall')
        self.assertEqual(self.effects(self.fake.lines), [])
        self.run_worker('panels')
        flashed = {zone for payload in self.effects(self.fake.panels)
                   for zone, frames in decode(payload).items() if any(f[:3] == [255, 255, 255] for f in frames)}
        self.assertEqual(flashed, set(target['zones']))
        self.assertEqual(self.query('SELECT * FROM locate'), [])
        self.assertEqual((self.fake.panels.selected, self.fake.panels.brightness), ('Forest', 64))

    def test_locate_is_rejected_in_panels_free_and_for_lines_ids(self):
        self.mode('free', 'panels')
        config = b.load_config(self.directory, 'panels')
        with self.assertRaises(ValueError):
            self.locate(config['elements'][0]['id'])
        self.mode('work', 'panels')
        with self.assertRaises(ValueError):
            self.locate(b.load_config(self.directory)['elements'][0]['id'])
        self.assertEqual(self.query('SELECT * FROM locate'), [])


class ContinuityTest(DeviceWorkerTest):
    # AC4: no replay on registration; comet sources survive overrides.
    def test_registering_panels_later_replays_nothing(self):
        config = json.loads((self.directory / 'config.json').read_text())
        registered = copy.deepcopy(config)
        del config['devices']['panels']
        b.write_json(self.directory / 'config.json', config)
        self.event('UserPromptSubmit', 'a')
        self.event('UserPromptSubmit', 'b')
        self.event('Stop', 'b')
        self.unread.add('b')
        epochs = self.query('SELECT session, started FROM activity ORDER BY session')
        self.assertEqual(self.query('SELECT device FROM comets'), [('wall',)])
        self.clock.sleep(10)
        b.write_json(self.directory / 'config.json', registered)
        self.run_worker('panels', self.free_after(3, 'panels') + [(self.clock.now() + 3.5, self.unread.clear)])
        self.assertEqual(self.query("SELECT session, started FROM activity WHERE session='a'"), epochs[:1])
        self.assertEqual(self.query("SELECT COUNT(*) FROM comets WHERE device='panels'"), [(0,)])
        first = decode(self.effects(self.fake.panels)[0])
        occupied = {self.query("SELECT slot FROM slots WHERE device='panels' AND session=?", s)[0][0] for s in 'ab'}
        zones = [e['zones'][0] for e in b.load_config(self.directory, 'panels')['elements']]
        for index, zone in enumerate(zones):
            if index not in occupied:
                self.assertEqual({tuple(f[:3]) for f in first[zone]}, {b.BASELINE})

    def test_override_keeps_the_panels_comet_source_until_it_ends(self):
        self.event('UserPromptSubmit')
        self.event('Stop')
        self.unread.add('a')
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO projects VALUES ('p','P','#00ff00','[]'), ('q','Q','#ff00ff','[]')")
            db.execute("UPDATE task_info SET project='p'")
            config = b.load_config(self.directory, 'panels')
            ids = [e['id'] for e in config['elements']]
            wall.request_patch(db, {'settings': {'style': 'project'}, 'lines': {i: {'project': 'p'} for i in ids}}, config)
        observed = []
        def override():
            with contextlib.closing(b.connect_state(self.directory)) as db, db:
                started = db.execute("SELECT source FROM comets WHERE device='panels' AND started IS NOT NULL").fetchone()
                observed.append(started)
                self.assertFalse(wall.request_patch(db, {'tasks': {'a': 'q'}}, b.load_config(self.directory)))
                b.mark_dirty(db)
        def during():
            observed.append(self.query("SELECT slot FROM slots WHERE device='panels'"))
        def after():
            observed.append(self.query("SELECT slot FROM slots WHERE device='panels'"))
        start = self.clock.now()
        self.run_worker('panels', [(start + 0.5, override), (start + 1.5, during), (start + 2.6, after),
                                   (start + 4, lambda: self.mode('free', 'panels')), (start + 4.5, self.unread.clear)])
        self.assertIsNotNone(observed[0])
        self.assertEqual(observed[1], [(observed[0][0],)])
        self.assertEqual(observed[2], [])


class IsolationTest(DeviceWorkerTest):
    # AC5: a failing device records only its own error and retries.
    def test_panels_outage_leaves_lines_update_and_outcome(self):
        server.configure(self.directory, b, 'controller', 'wall', 'source')
        self.event('UserPromptSubmit')
        self.fake.panels.fail = lambda method, endpoint, payload: True
        attempts, feeds = [], []
        original = b.run_worker
        def run(directory, device='wall', feed=None):
            attempts.append(device)
            feeds.append(feed)
            return original(directory, device=device, feed=feed, sleep=self.clock.sleep, now=self.clock.now,
                            read_unread=lambda: self.unread)
        with patch.object(sys, 'argv', ['bridge.py', 'worker', '--device', 'panels', '--state-dir', str(self.directory)]), \
                patch.object(b, 'run_worker', side_effect=run), \
                patch.object(b.time, 'sleep', lambda seconds: self.assertEqual(seconds, 2) or self.mode('free', 'panels')):
            b.main()
        self.assertEqual(attempts, ['panels', 'panels'])
        # The retry loop hands every attempt the same feed state, so a failed pass cannot force a resync.
        self.assertIsInstance(feeds[0], dict)
        self.assertIs(feeds[0], feeds[1])
        self.assertIsNone(b.get_status(self.directory)['error'])
        with contextlib.closing(b.connect_state(self.directory)) as db:
            self.assertIsNone(db.execute("SELECT value FROM meta WHERE key='control_error'").fetchone())
            outcome = controller_state.read(db)['lastOutcome']
        self.assertEqual(outcome, {'status': 'unknown'})
        self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertTrue(self.effects(self.fake.lines))
        self.assertIsNone(b.get_status(self.directory)['error'])

    def test_failed_pass_records_panels_error_only(self):
        self.event('UserPromptSubmit')
        self.fake.panels.fail = lambda method, endpoint, payload: True
        with self.assertRaises(OSError):
            self.run_worker('panels')
        b.record_failure(self.directory, 'panels')
        self.assertEqual(b.get_status(self.directory, 'panels')['error'], 'Light update failed; retrying.')
        self.assertIsNone(b.get_status(self.directory)['error'])

    def test_waiting_panels_instance_wakes_even_after_lines_clears_dirty(self):
        self.event('UserPromptSubmit')
        def change():
            self.event('PermissionRequest', tool_name='exec_command')
            with contextlib.closing(b.connect_state(self.directory)) as db, db:
                db.execute("DELETE FROM meta WHERE key='dirty'")  # The Lines instance already applied it.
        start = self.clock.now()
        self.run_worker('panels', [(start + 4.1, change), (start + 4.6, lambda: self.mode('free', 'panels'))])
        red = [payload for payload in self.effects(self.fake.panels)
               if any(any(f[:3] == [255, 0, 0] for f in frames) for frames in decode(payload).values())]
        self.assertTrue(red)


class ProtectedApiTest(DeviceWorkerTest):
    # AC7: machine requests, overrides and the hold stay on Lines.
    def setUp(self):
        super().setUp()
        server.configure(self.directory, b, 'controller', 'wall', 'source')
        self.token = server.issue(self.directory, b, 'client', ['read', 'control'])
        self.app = server.App(self.directory, b, launch=lambda _: None)

    def command(self, command):
        snap = self.app.snapshot()
        return self.app.admit(self.token, dict(apiVersion='1.0', controllerId='controller', deviceId='wall',
                                               requestId=snap['nextRequestId'],
                                               expectedConfigurationRevision=snap['configurationRevision'],
                                               expectedGeneration=snap['generation'], command=command))

    def test_machine_requests_never_reach_panels(self):
        self.event('UserPromptSubmit')
        self.command({'kind': 'mode.set', 'mode': 'Quiet'})
        self.command({'kind': 'brightness.set', 'percent': 55})
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.assertEqual(b.get_status(self.directory, 'panels')['mode'], 'free')
        panel_levels = [p['brightness']['value'] for _, m, e, p in self.fake.panels.calls if m == 'PUT' and e == '/state' and 'on' in p]
        self.assertEqual(panel_levels[0], 30)
        self.assertNotIn(55, [p.get('brightness', {}).get('value') for _, m, e, p in self.fake.panels.calls if m == 'PUT'])
        pending = self.app.snapshot()['state']['pending']
        self.assertEqual([p['command']['kind'] for p in pending], ['mode.set', 'brightness.set'])
        self.run_worker('wall', [(self.clock.now() + 3, lambda: self.mode('free', 'wall'))])
        lines_levels = [p['brightness']['value'] for _, m, e, p in self.fake.lines.calls if m == 'PUT' and 'brightness' in (p or {})]
        self.assertIn(55, lines_levels)
        self.assertEqual(self.app.snapshot()['state']['pending'], [])

    def test_lines_hold_does_not_stop_panels(self):
        self.command({'kind': 'mode.set', 'mode': 'Quiet'})
        self.fake.lines.fail = lambda method, endpoint, payload: method == 'PUT'
        with self.assertRaises(OSError):
            self.run_worker('wall')
        self.assertEqual(self.app.snapshot()['state']['lastOutcome']['receipt']['outcome'], 'uncertain')
        held = self.query("SELECT value FROM meta WHERE key='controller_hold_revision'")[0][0]
        # Give Panels the same revision number, so a hold that ignored the device would match it.
        revision = lambda: self.query("SELECT value FROM meta WHERE key='mode_revision@panels'")
        while int((revision() or [('0',)])[0][0]) < int(held):
            self.mode('quiet' if b.get_status(self.directory, 'panels')['mode'] == 'work' else 'work', 'panels')
        self.assertEqual(revision(), [(held,)])
        self.event('UserPromptSubmit')
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.assertTrue(self.effects(self.fake.panels))
        self.assertEqual(self.app.snapshot()['state']['lastOutcome']['receipt']['outcome'], 'uncertain')

    def test_panels_never_runs_controller_integration_or_scene_discovery(self):
        import integration_api
        calls = []
        self.event('UserPromptSubmit')
        with patch.object(integration_api, 'process', lambda *a, **k: calls.append('integration')), \
                patch.object(controller_state, 'discovered', lambda *a, **k: calls.append('discovered')), \
                patch.object(controller_state, 'recover', lambda *a, **k: calls.append('recover')), \
                patch.object(controller_state, 'Execution', side_effect=AssertionError('Panels created a controller execution')):
            self.run_worker('panels', self.free_after(3, 'panels'))
        self.assertEqual(calls, [])
        self.assertTrue(self.effects(self.fake.panels))
        with patch.object(integration_api, 'process', lambda *a, **k: calls.append('integration')), \
                patch.object(controller_state, 'discovered', lambda *a, **k: calls.append('discovered')):
            self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertIn('integration', calls)
        self.assertIn('discovered', calls)
        with contextlib.closing(b.connect_state(self.directory)) as db:
            names = controller_state.read(db).get('scenes', [])
        self.assertNotIn('Forest', names)

    def test_panels_pass_keeps_the_lines_error(self):
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            db.execute("INSERT INTO meta VALUES ('control_error', 'Light update failed; retrying.')")
        self.event('UserPromptSubmit')
        self.run_worker('panels', self.free_after(3, 'panels'))
        self.assertEqual(b.get_status(self.directory)['error'], 'Light update failed; retrying.')
        self.assertIsNone(b.get_status(self.directory, 'panels')['error'])

    def test_lines_outage_keeps_panels_comets_in_shared_input(self):
        import test_shared_input as shared
        config = {'version': 1, 'ownerId': 'owner', 'consumerId': 'nanoleaf',
                  'endpoint': 'http://127.0.0.1:12345/api/monitor/v1', 'tokenFile': str(self.directory / 'token'),
                  'clearOnNewTurn': True,
                  'qualifiedSources': [{'provider': 'codex', 'client': 'desktop', 'hostId': 'host', 'sourceId': 'source'}],
                  'bindings': []}
        shared_input.configure(self.directory, b, config)
        active = shared.envelope(); first = active['snapshot']['sessions'][0]; notice = first['notices'].pop()
        first['activity'] = 'active'; active['snapshot']['revision'] = 1
        done = copy.deepcopy(active); done['snapshot']['revision'] = 2
        done['snapshot']['sessions'][0].update(activity='idle', notices=[notice])
        feed = [active]
        fetch = lambda config, minimum_revision=0: feed[0]
        with patch.object(shared_input, 'fetch_snapshot', fetch):
            shared_input.select_source(self.directory, b, 'shared', fetch=fetch, now=self.clock.now)
            self.fake.lines.fail = lambda method, endpoint, payload: True
            state = {}
            for attempt in range(3):
                self.fake.lines.fail = lambda method, endpoint, payload: True
                if attempt == 1:
                    feed[0] = done
                self.clock.sleep(2)
                with self.assertRaises(OSError):
                    b.run_worker(self.directory, sleep=self.clock.sleep, now=self.clock.now,
                                 read_unread=lambda: self.unread, device='wall', feed=state)
        self.assertEqual(sorted(self.query('SELECT device FROM comets')), [('panels',), ('wall',)])

    def test_panels_instance_never_polls_the_shared_feed(self):
        ticks = []
        with patch.object(shared_input.Poller, 'tick', lambda poller, instant: ticks.append(instant) or False):
            self.event('UserPromptSubmit')
            self.run_worker('panels', self.free_after(3, 'panels'))
            self.assertEqual(ticks, [])
            self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertTrue(ticks)


class UnregisteredDeviceTest(DeviceWorkerTest):
    # #45 removal: an instance for a device that is no longer registered stops.
    def unregister(self, device='panels'):
        config = json.loads((self.directory / 'config.json').read_text())
        del config['devices'][device]
        b.write_json(self.directory / 'config.json', config)
        with contextlib.closing(b.connect_state(self.directory)) as db, db:
            b.mark_dirty(db)

    def test_waiting_instance_exits_after_its_device_is_removed(self):
        self.event('UserPromptSubmit')
        removed = self.clock.now() + 3
        self.run_worker('panels', [(removed, self.unregister)])
        self.assertTrue(self.effects(self.fake.panels))
        self.assertFalse([call for call in self.fake.panels.calls if call[0] > removed])
        self.run_worker('wall', self.free_after(3, 'wall'))
        self.assertTrue(self.effects(self.fake.lines))

    def test_retry_loop_stops_for_an_unregistered_device(self):
        class Stop(BaseException):
            pass
        attempts = []
        def run(directory, device='wall', feed=None):
            attempts.append(device)
            if len(attempts) > 1:
                raise Stop()
            self.unregister()
            raise OSError('Device unavailable')
        with patch.object(sys, 'argv', ['bridge.py', 'worker', '--device', 'panels', '--state-dir', str(self.directory)]), \
                patch.object(b, 'run_worker', side_effect=run), patch.object(b.time, 'sleep', lambda seconds: None):
            try:
                b.main()
            except Stop:
                pass
        self.assertEqual(attempts, ['panels'])
        self.assertEqual(self.query("SELECT key FROM meta WHERE key LIKE '%@panels' AND key LIKE 'control_error%'"), [])

if __name__ == '__main__':
    unittest.main()
