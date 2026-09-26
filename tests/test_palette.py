"""Task-light palette: storage, the settings write and worker frame colors (issue #139)."""
import contextlib
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_bridge import b, decode
import database
import modes
import test_project_map
import project_map as w
import wall_server

DEFAULTS = {'base': '#0a1866', 'working': '#00ff00', 'question': '#ffff00',
            'blocked': '#ff0000', 'unread': '#9b30ff'}


def rgb(value):
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))


class PaletteCase(unittest.TestCase):
    # Borrow the project-map fixtures without rerunning their tests here.
    setUp = test_project_map.ProjectTest.setUp
    event = test_project_map.ProjectTest.event
    query = test_project_map.ProjectTest.query
    run_worker = test_project_map.ProjectTest.run_worker
    projects = test_project_map.ProjectTest.projects
    task = test_project_map.ProjectTest.task
    prepare = test_project_map.ProjectTest.prepare
    assign = test_project_map.ProjectTest.assign


class PaletteStateTest(PaletteCase):
    def palette(self, app):
        return app.state()['palette']

    # AC1 and AC11: defaults, partial updates, reset and persistence.
    def test_defaults_partial_update_reset_and_restart(self):
        app = self.projects()
        self.assertEqual(self.palette(app), DEFAULTS)
        app.update('/api/settings', {'palette': {'unread': '#FF00C0', 'base': '#000000'}})
        app.update('/api/project', {'id': 'a', 'color': '#113355'})
        reopened = wall_server.App(self.directory, self.config, launch=lambda _: None)
        self.assertEqual(self.palette(reopened), dict(DEFAULTS, unread='#ff00c0', base='#000000'))
        reopened.update('/api/settings', {'palette': 'default'})
        state = reopened.state()
        self.assertEqual(state['palette'], DEFAULTS)
        self.assertEqual(next(p for p in state['projects'] if p['id'] == 'a')['color'], '#113355')

    # AC10: invalid requests change nothing.
    def test_invalid_palette_requests_apply_nothing(self):
        app = self.projects()
        app.update('/api/settings', {'palette': {'working': '#00e5ff'}})
        before = self.palette(app)
        for payload in ({'palette': {'unread': '#ff00c0', 'base': '#12345'}},
                        {'palette': {'unread': '#ff00c0', 'comet': '#ffffff'}},
                        {'palette': {'unread': 'red'}}, {'palette': {'unread': None}},
                        {'palette': {}}, {'palette': 'reset'}, {'palette': ['#ff00c0']},
                        {'palette': {'unread': '#ff00c0'}, 'style': 'bad'},
                        {'rotation': 90, 'palette': {'unread': '#12345'}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                app.update('/api/settings', payload)
            self.assertEqual(self.palette(app), before)
            self.assertEqual(app.state()['settings']['rotation'], 0)

    def test_palette_write_requires_origin_and_token(self):
        app = self.projects()
        server = ThreadingHTTPServer(('127.0.0.1', 0), wall_server.handler(app, 'test-secret'))
        server.app = app
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f'http://127.0.0.1:{server.server_port}'
        body = json.dumps({'palette': {'unread': '#ff00c0'}}).encode()
        for headers in ({'Origin': url}, {'Origin': 'https://example.com', 'X-Wall-Token': 'test-secret'}):
            request = Request(url + '/api/settings', data=body, headers={'Content-Type': 'application/json', **headers})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        self.assertEqual(self.palette(app), DEFAULTS)
        request = Request(url + '/api/settings', data=body, headers={
            'Content-Type': 'application/json', 'Origin': url, 'X-Wall-Token': 'test-secret'})
        with urlopen(request) as response:
            self.assertEqual(response.status, 200)
        with urlopen(url + '/api/state') as response:
            state = json.load(response)
        self.assertEqual(state['palette']['unread'], '#ff00c0')
        self.assertNotIn('PRIVATE_TEST_TOKEN', json.dumps(state))

    # AC11: an upgraded database keeps its preferences and starts with the new defaults.
    def test_upgrade_keeps_preferences_and_adopts_defaults(self):
        app = self.projects()
        self.assign(app, [2], 'a')
        app.update('/api/project', {'id': 'a', 'color': '#113355'})
        app.update('/api/settings', {'style': 'project', 'coverage': 'status', 'rotation': 90})
        modes.set_mode(self.directory, 'quiet', launch=lambda *_: None, now=self.clock.now)
        scene = self.directory / 'scene-state.json'
        scene.write_text(json.dumps({'version': 1, 'scene': {'name': 'Beach Waves', 'brightness': 43}, 'owned': False}))
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute('DROP TABLE palette')  # The state an earlier version left behind.
        before = (self.query('SELECT * FROM projects'), self.query('SELECT * FROM line_prefs'),
                  self.query('SELECT * FROM map_settings'), scene.read_text())
        state = wall_server.App(self.directory, self.config, launch=lambda _: None).state()
        self.assertEqual(state['palette'], DEFAULTS)
        self.assertEqual(state['mode'], 'quiet')
        self.assertEqual(before, (self.query('SELECT * FROM projects'), self.query('SELECT * FROM line_prefs'),
                                  self.query('SELECT * FROM map_settings'), scene.read_text()))

    def test_damaged_rows_fall_back_to_defaults(self):
        self.projects()
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.executemany('INSERT OR REPLACE INTO palette VALUES (?,?)',
                           [('unread', 'violet'), ('comet', '#ffffff'), ('base', '#000000')])
            self.assertEqual(w.palette(db), dict(DEFAULTS, base='#000000'))

    def test_integration_settings_api_offers_no_palette(self):
        import integration_api
        request = {'apiVersion': integration_api.VERSION, 'controllerId': 'c', 'deviceId': 'lines',
                   'requestId': {'epoch': 'a' * 32, 'sequence': 1}, 'expectedRevision': 'f' * 64,
                   'command': {'kind': 'settings.set', 'palette': {'unread': '#ff00c0'}}}
        with self.assertRaises(integration_api.Failure):
            integration_api.validate(request)


class PaletteFrameTest(PaletteCase):
    def configure(self, **roles):
        app = self.projects()
        if roles:
            app.update('/api/settings', {'palette': roles})
        return app

    def delays(self, cfg):
        return [b.travel_delays(cfg, i) for i in range(len(cfg['line_groups']))]

    # AC2: base for unused and read Lines, the Unread pulse and the comet tail.
    def test_work_default_palette(self):
        self.configure()
        cfg, _ = self.prepare()
        # A retained shared task that was read shows as idle.
        snap = [('unread', 990), ('idle', 990)] + [None] * 13
        delays = self.delays(cfg)
        base, unread = rgb(DEFAULTS['base']), rgb(DEFAULTS['unread'])
        self.assertEqual(b.zone_color(cfg, snap, 0, 0, 1000.5, delays), unread)
        self.assertEqual(b.zone_color(cfg, snap, 1, 0, 1000.5, delays), base)
        self.assertEqual(b.zone_color(cfg, snap, 2, 1, 1000.5, delays), base)
        cfg['_comet'] = {'source': 0, 'started': 1000}
        self.assertEqual(b.zone_color(cfg, snap, 0, 0, 1000.05, delays), (255, 255, 255))
        # Late in the tail, the comet has blended fully into the Unread color over the base.
        tail = b.zone_color(cfg, snap, 5, 0, 1000 + 1.4 * 5 / 14 + 0.3, delays)
        alpha = (0.6 - 0.3) / 0.4
        self.assertEqual(tail, tuple(round(bg * (1 - alpha) + fg * alpha) for bg, fg in zip(base, unread)))

    def test_chosen_working_color_for_wave_and_pulse(self):
        self.configure(working='#00e5ff')
        self.task('a', None)
        cfg, snap = self.prepare()
        delays = self.delays(cfg)
        cyan = rgb('#00e5ff')
        self.assertEqual(b.zone_color(cfg, snap, 0, 0, 1000.5, delays), cyan)
        wave = [b.zone_color(cfg, snap, 3, 0, 1000 + t / 100, delays) for t in range(0, 200)]
        self.assertIn(cyan, wave)
        self.assertEqual(b.zone_color(cfg, snap, 3, 0, 1003, delays), rgb(DEFAULTS['base']))
        self.assertEqual(b.zone_color(cfg, snap, 0, 0, 1001.5, delays), tuple(round(c * 0.2) for c in cyan))

    # AC3: Quiet steady at 10%.
    def test_quiet_steady_chosen_colors(self):
        self.configure(working='#00e5ff')
        self.task('a', None)
        cfg, snap = self.prepare()
        cfg['_mode'] = 'quiet'
        payload = b.effect_payload(cfg, snap, 1000, True)
        frames = decode(payload)
        self.assertEqual(payload['write']['animType'], 'static')
        self.assertEqual([f[:3] for f in frames[100]], [list(rgb('#00e5ff'))])
        self.assertEqual([f[:3] for f in frames[102]], [list(rgb(DEFAULTS['base']))])
        self.assertEqual(b.indicator_brightness(cfg), 10)

    # AC4: Project layout base halves and both coverage settings.
    def test_project_halves_use_base(self):
        app = self.configure(base='#4d3f2a')
        self.assign(app, [1], 'a')
        self.task('b', 'b')
        app.update('/api/settings', {'style': 'project', 'coverage': 'whole'})
        cfg, snap = self.prepare()
        delays = self.delays(cfg)
        base = rgb('#4d3f2a')
        self.assertEqual(b.zone_color(cfg, snap, 1, 0, 1003, delays), (170, 85, 255))
        self.assertEqual(b.zone_color(cfg, snap, 1, 1, 1003, delays), base)
        self.assertEqual({b.zone_color(cfg, snap, 4, half, 1003, delays) for half in (0, 1)}, {base})
        wave = [b.zone_color(cfg, snap, 1, 0, 1000 + t / 100, delays) for t in range(0, 200)]
        self.assertIn((0, 255, 0), wave)
        cfg['_coverage'] = 'status'
        wave = [b.zone_color(cfg, snap, 1, 0, 1000 + t / 100, delays) for t in range(0, 200)]
        self.assertEqual(set(wave), {(170, 85, 255)})

    # AC5: priority follows status, not hue.
    def test_swapped_hues_keep_status_priority(self):
        self.configure(blocked='#9b30ff', unread='#ff0000')
        violet = rgb('#9b30ff')
        snapshot = [('working', 1000), ('blocked', 1000), ('unread', 900), ('question', 1000)] + [None] * 11
        cfg = dict(self.config, _palette=b.wall.palette_rgb(self.palette()))
        delays = self.delays(cfg)
        self.assertEqual(b.pixel_color(snapshot, 2, 1000.55, delays, palette=cfg['_palette']), violet)
        self.assertEqual(b.pixel_color(snapshot, 1, 1000.5, delays, palette=cfg['_palette']), violet)
        cfg['_comet'] = {'source': 2, 'started': 1003}
        colors = {b.zone_color(cfg, snapshot, 1, 0, 1003 + t / 100, delays) for t in range(0, 200)}
        # The blocked Line only ever shows its own violet pulse, from 20% to full brightness.
        for color in colors:
            level = color[2] / 255
            self.assertGreaterEqual(level, b.MIN_BRIGHTNESS - 0.01)
            self.assertTrue(all(abs(a - c * level) <= 1 for a, c in zip(color, violet)), color)

    def palette(self):
        with contextlib.closing(database.connect_state(self.directory)) as db:
            return w.palette(db)

    # AC12: the Panels use the same palette.
    def test_panels_use_the_shared_palette(self):
        import devices
        import panels
        import test_panels
        self.configure(working='#00e5ff', base='#000000')
        entry = panels.read_layout(test_panels.layout())
        cfg = dict(devices.projection(entry), device='panels', ip='192.0.2.2', token='fake')
        count = len(cfg['line_groups'])
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            w.render_config(db, cfg, [None] * count)
        snapshot = [('working', 900)] + [None] * (count - 1)
        frames = decode(b.effect_payload(cfg, snapshot, 1000, True))
        first, other = cfg['line_groups'][0][0], cfg['line_groups'][1][0]
        self.assertIn(list(rgb('#00e5ff')), [f[:3] for f in frames[first]])
        self.assertEqual({tuple(f[:3]) for f in frames[other]}, {(0, 0, 0)})


class PaletteWorkerTest(PaletteCase):
    def effects(self, since=0):
        return [(at, decode(payload)) for at, method, endpoint, payload in self.device.calls
                if at >= since and method == 'PUT' and endpoint == '/effects' and 'write' in payload]

    # AC6: a change mid-pulse and mid-comet restarts nothing.
    def test_change_and_reset_mid_pulse_and_mid_comet(self):
        app = self.projects()
        self.task('w', None)
        self.task('u', None)
        seen = {}
        def finish():
            self.unread.add('u')
            self.event('Stop', 'u')
        def change():
            seen['before'] = (self.query('SELECT * FROM activity ORDER BY session'),
                              self.query('SELECT session,source,started FROM comets'), self.query('SELECT * FROM slots'))
            app.update('/api/settings', {'palette': {'unread': '#ff00c0', 'working': '#00e5ff'}})
        def check():
            seen['after'] = (self.query('SELECT * FROM activity ORDER BY session'),
                             self.query('SELECT session,source,started FROM comets'), self.query('SELECT * FROM slots'))
        def done():
            self.unread.clear()
            self.event('Interrupt', 'w')
        self.run_worker([(1001, finish), (1002, change), (1002.6, check),
                         (1005, lambda: app.update('/api/settings', {'palette': 'default'})), (1007, done)])
        self.assertEqual(seen['before'], seen['after'])
        self.assertEqual(len(seen['before'][1]), 1)
        source = seen['before'][1][0][1]
        panel = self.config['line_groups'][source][0]
        slots = {session: slot for session, slot, *_ in seen['before'][2]}
        working = self.config['line_groups'][slots['w']][0]
        changed = self.effects(1002)
        self.assertTrue(any([255, 0, 192] in [f[:3] for f in frames[panel]] for at, frames in changed if at < 1005))
        self.assertTrue(any([0, 229, 255] in [f[:3] for f in frames[working]] for at, frames in changed if at < 1005))
        comet_end = seen['before'][1][0][2] + b.COMET_SECONDS
        self.assertFalse(any([255, 255, 255] in [f[:3] for f in panels] for at, frames in self.effects(comet_end)
                             for panels in frames.values()))
        reset = self.effects(1005)
        self.assertTrue(reset and any(list(rgb(DEFAULTS['unread'])) in [f[:3] for f in frames[panel]] for at, frames in reset))
        self.assertIn(('w', '1', 'working', 1000), seen['after'][0])

    # AC7: an Off base leaves unused Lines dark, and the scene still returns.
    def test_off_base_keeps_unused_lines_dark_and_restores_scene(self):
        app = self.projects()
        app.update('/api/settings', {'palette': {'base': '#000000'}})
        self.task('a', None)
        self.event('PermissionRequest', 'a', tool_name='Bash')
        self.run_worker([(1003, lambda: self.event('Interrupt', 'a'))])
        # The first red wave crosses every Line; afterward only the blocked Line is lit.
        shown = self.effects(1000 + 0.5 * b.PULSE_SECONDS + b.TRAVEL_SECONDS)
        self.assertTrue(shown)
        for at, frames in shown:
            self.assertTrue(any(f[:3] == [255, 0, 0] for f in frames[100]))
            self.assertEqual({tuple(f[:3]) for zone in range(102, 130) for f in frames[zone]}, {(0, 0, 0)})
        self.assertEqual(self.device.selected, 'Beach Waves')

    # AC3: Free hands the lights back once and sends no palette colors.
    def test_free_after_palette_change_restores_scene_once(self):
        app = self.projects()
        app.update('/api/settings', {'palette': {'base': '#000000', 'working': '#00e5ff'}})
        self.task('a', None)
        self.run_worker([(1003, lambda: modes.set_mode(self.directory, 'free', launch=lambda *_: None, now=self.clock.now))])
        self.assertTrue(self.effects(0), 'Work showed the task before Free')
        self.assertEqual(self.effects(1003), [], 'Free sends no task frames')
        restored = [at for at, method, _, payload in self.device.calls
                    if at >= 1003 and method == 'PUT' and payload.get('select') == 'Beach Waves']
        self.assertEqual(len(restored), 1)
        self.assertEqual(self.device.selected, 'Beach Waves')

    def test_no_scene_fallback_stays_blue(self):
        app = self.projects()
        app.update('/api/settings', {'palette': {'base': '#000000'}})
        self.device.selected = '*Dynamic*'
        manager = b.SceneRestorer(self.directory, self.config, request=self.device.request)
        manager.observe()
        with contextlib.closing(database.connect_state(self.directory)) as db:
            cfg = dict(self.config)
            w.render_config(db, cfg, [None] * 15)
        manager.send(cfg, self.active, 1000, True)
        manager.send(cfg, [None] * 15, 1004, True)
        self.assertEqual(self.device.selected, '*Static*')
        _, frames = self.effects()[-1]
        self.assertEqual({tuple(f[:3]) for panels in frames.values() for f in panels}, {b.FALLBACK})


if __name__ == '__main__':
    unittest.main()
