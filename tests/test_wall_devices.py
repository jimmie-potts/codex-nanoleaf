"""Device-scoped wall map for issue #44: selector data, per-request registry, targeted actions and triangles."""
import contextlib
from http.server import ThreadingHTTPServer
import json
import math
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_bridge import b
import database
import jsonfile
import modes
from test_panels import layout as panels_layout
import devices
import panels
import project_map as wall
import wall_server

LINES_TOKEN = 'PRIVATE_LINES_TOKEN'
PANELS_TOKEN = 'PRIVATE_PANELS_TOKEN'
GROUPS = [[100 + i * 2, 101 + i * 2] for i in range(15)]
POSITIONS = [[i * 10, 0] for i in range(15)]


def refuse(*args, **kwargs):
    raise AssertionError('The device must not be contacted.')


class WallDeviceTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.write_registry(with_panels=False)
        self.panels_entry = panels.read_layout(panels_layout())

    def write_registry(self, with_panels, save_panels_layout=True):
        config = {'ip': '192.0.2.1', 'token': LINES_TOKEN,
                  'devices': {'wall': {'kind': 'lines', 'ip': '192.0.2.1', 'token_ref': 'token'}}}
        zones = [{'panelId': zone, 'x': i * 10 + (5 if zone % 2 else -5), 'y': 0, 'o': 0, 'shapeType': 18}
                 for i, pair in enumerate(GROUPS) for zone in pair]
        saved = {'wall': devices.lines_entry(GROUPS, POSITIONS, {'zone_geometry': {'positionData': zones, 'orientation': 0}})}
        if with_panels:
            config['panelsToken'] = PANELS_TOKEN
            config['devices']['panels'] = {'kind': 'panels', 'ip': '192.0.2.2', 'token_ref': 'panelsToken'}
            if save_panels_layout:
                saved['panels'] = panels.read_layout(panels_layout())
        jsonfile.write_json(self.directory / 'config.json', config)
        devices.save_layout(self.directory / 'layout.json', saved)

    def app(self):
        return wall_server.App(self.directory, launch=lambda *_: None, request=refuse)

    def db(self):
        return contextlib.closing(database.connect_state(self.directory))

    def serve(self, app):
        server = ThreadingHTTPServer(('127.0.0.1', 0), wall_server.handler(app, 'test-secret'))
        server.app = app
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}'

    def http(self, url, path, payload=None, headers=None):
        body = None if payload is None else json.dumps(payload).encode()
        base = {'Content-Type': 'application/json', 'Origin': url, 'X-Wall-Token': 'test-secret'} if body else {}
        request = Request(url + path, data=body, headers={**base, **(headers or {})})
        try:
            with urlopen(request) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    # AC1 and AC2: untargeted reads address Lines and list the registry read on each request.
    def test_untargeted_state_addresses_lines_and_lists_registered_devices(self):
        app = self.app()
        state = app.state()
        self.assertEqual((state['device'], state['kind'], len(state['lines'])), ('wall', 'lines', 15))
        self.assertEqual(state['devices'], [{'id': 'wall', 'kind': 'lines', 'name': 'Lines', 'default': True}])
        self.write_registry(with_panels=True)
        state = app.state()
        self.assertEqual([d['id'] for d in state['devices']], ['wall', 'panels'])
        self.assertEqual(state['devices'][1], {'id': 'panels', 'kind': 'panels', 'name': 'Light Panels', 'default': False})
        self.assertEqual(state['device'], 'wall')
        self.assertEqual(app.state('wall')['device'], 'wall')
        self.assertEqual(app.state('panels')['device'], 'panels')

    # AC4 and AC6: the Panels view comes from cached geometry, numbered in the reader's order.
    def test_targeted_panels_state_uses_cached_triangle_geometry(self):
        self.write_registry(with_panels=True)
        state = self.app().state('panels')
        elements = self.panels_entry['elements']
        self.assertEqual(state['kind'], 'panels')
        self.assertEqual([(line['id'], line['number']) for line in state['lines']],
                         [(e['id'], e['number']) for e in elements])
        self.assertEqual([line['number'] for line in state['lines']], list(range(1, 19)))
        radius = panels.SIDE / math.sqrt(3)
        by_id = {t['id']: t for t in self.panels_entry['panel_geometry']['triangles']}
        for line in state['lines']:
            triangle = by_id[line['id']]
            expected = [[triangle['x'] + radius * math.cos(math.radians(90 + triangle['o'] + 120 * k)),
                         -(triangle['y'] + radius * math.sin(math.radians(90 + triangle['o'] + 120 * k)))] for k in range(3)]
            for vertex, want in zip(line['points'], expected):
                self.assertAlmostEqual(vertex[0], want[0], places=6)
                self.assertAlmostEqual(vertex[1], want[1], places=6)
            self.assertEqual((line['project'], line['signature'], line['task']), (None, 0, None))
        self.assertIsNone(state['geometry_error'])
        self.assertIsNone(state['connector_layout'])
        self.assertIsNone(state['connector_error'])

    def test_registered_device_without_saved_layout_reports_an_error_without_contact(self):
        self.write_registry(with_panels=True, save_panels_layout=False)
        state = self.app().state('panels')
        self.assertEqual((state['device'], state['kind'], state['lines']), ('panels', 'panels', []))
        self.assertTrue(state['geometry_error'])

    # AC2: unknown devices are rejected, never mapped to Lines, and change nothing.
    def test_unknown_device_is_rejected_without_fallback_or_change(self):
        self.write_registry(with_panels=True)
        app = self.app()
        for target in ('missing', '', 'WALL', 'panels ', 5):
            with self.subTest(target=target):
                with self.assertRaises(wall_server.UnknownDevice):
                    app.state(target)
                with self.assertRaises(wall_server.UnknownDevice):
                    app.update('/api/settings', {'rotation': 90, 'device': target})
                with self.assertRaises(wall_server.UnknownDevice):
                    app.update('/api/locate', {'line': self.panels_entry['elements'][0]['id'], 'device': target})
        with self.db() as db:
            self.assertEqual(wall.settings(db)['rotation'], 0)
            self.assertEqual(wall.settings(db, 'panels')['rotation'], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM locate').fetchone(), (0,))
        self.assertTrue(issubclass(wall_server.UnknownDevice, ValueError))

    # AC2, AC3 and AC5: targeted actions change only the named device.
    def test_actions_address_the_named_device(self):
        self.write_registry(with_panels=True)
        app = self.app()
        triangle = self.panels_entry['elements'][3]['id']
        with self.db() as db, db:
            db.execute("INSERT INTO projects VALUES ('p','P','#00ff00','[]')")
        app.update('/api/settings', {'rotation': 90, 'flip_x': 1, 'device': 'panels'})
        app.update('/api/settings', {'style': 'project', 'device': 'panels'})
        app.update('/api/assign', {'lines': {triangle: {'project': 'p'}}, 'device': 'panels'})
        app.update('/api/locate', {'line': triangle, 'device': 'panels'})
        app.update('/api/project', {'id': 'p', 'color': '#123456', 'device': 'panels'})
        with self.assertRaises(ValueError):
            app.update('/api/assign', {'lines': {'100:101': {'project': 'p'}}, 'device': 'panels'})
        with self.assertRaises(ValueError):
            app.update('/api/locate', {'line': '100:101', 'device': 'panels'})
        with self.assertRaises(ValueError):
            app.update('/api/locate', {'line': triangle})
        with self.db() as db:
            self.assertEqual(wall.settings(db, 'panels'), {'style': 'project', 'coverage': 'whole', 'rotation': 90, 'flip_x': 1, 'flip_y': 0})
            self.assertEqual(wall.settings(db), {'style': 'classic', 'coverage': 'whole', 'rotation': 0, 'flip_x': 0, 'flip_y': 0})
            self.assertEqual(db.execute('SELECT line_id,project,device FROM line_prefs').fetchall(), [(triangle, 'p', 'panels')])
            self.assertEqual(db.execute('SELECT line_id,device FROM locate').fetchall(), [(triangle, 'panels')])
        lines, panel_view = app.state(), app.state('panels')
        self.assertEqual(lines['settings']['rotation'], 0)
        self.assertEqual(panel_view['settings']['rotation'], 90)
        self.assertEqual(next(l for l in panel_view['lines'] if l['id'] == triangle)['project'], 'p')
        self.assertTrue(all(l['project'] is None for l in lines['lines']))
        for view in (lines, panel_view):
            self.assertEqual(view['projects'][0]['color'], '#123456')

    def test_mode_changes_address_the_named_device_and_leave_the_other_scene_alone(self):
        self.write_registry(with_panels=True)
        scene = self.directory / 'scene-state.json'
        scene.write_text(json.dumps({'version': 1, 'scene': {'name': 'Beach', 'brightness': 40}, 'owned': False}))
        app = self.app()
        url = self.serve(app)
        code, body = self.http(url, '/api/mode', {'mode': 'quiet', 'device': 'panels'})
        self.assertEqual((code, body), (200, {'ok': True}))
        self.assertEqual(modes.get_status(self.directory, 'panels')['mode'], 'quiet')
        self.assertEqual(modes.get_status(self.directory)['mode'], 'work')
        self.assertEqual(app.state('panels')['mode'], 'quiet')
        self.assertEqual(app.state()['mode'], 'work')
        self.assertEqual(json.loads(scene.read_text())['scene']['name'], 'Beach')
        code, body = self.http(url, '/api/mode', {'mode': 'free', 'device': 'missing'})
        self.assertEqual(code, 400)
        self.assertIn('device', body['error'].lower())
        self.assertEqual([d['id'] for d in body['devices']], ['wall', 'panels'])
        self.assertEqual(modes.get_status(self.directory, 'panels')['mode'], 'quiet')
        self.assertEqual(modes.get_status(self.directory)['mode'], 'work')
        code, body = self.http(url, '/api/mode', {'mode': 'free'})
        self.assertEqual(code, 200)
        self.assertEqual(modes.get_status(self.directory)['mode'], 'free')
        self.assertEqual(modes.get_status(self.directory, 'panels')['mode'], 'quiet')

    # AC4: split-half settings are Lines-only.
    def test_one_zone_elements_reject_coverage_and_half_swaps(self):
        self.write_registry(with_panels=True)
        app = self.app()
        triangle = self.panels_entry['elements'][0]['id']
        with self.db() as db, db:
            db.execute("INSERT INTO projects VALUES ('p','P','#00ff00','[]')")
        app.update('/api/settings', {'style': 'project', 'device': 'panels'})
        for route, payload in (('/api/settings', {'coverage': 'status'}),
                               ('/api/assign', {'lines': {triangle: {'signature': 1}}}),
                               ('/api/assign', {'lines': {triangle: {'project': 'p', 'signature': 1}}})):
            with self.subTest(route=route), self.assertRaises(ValueError):
                app.update(route, {**payload, 'device': 'panels'})
        with self.db() as db:
            self.assertEqual(wall.settings(db, 'panels')['coverage'], 'whole')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM line_prefs').fetchone(), (0,))
        app.update('/api/settings', {'coverage': 'status'})
        app.update('/api/assign', {'lines': {'100:101': {'signature': 1}}})
        with self.db() as db:
            self.assertEqual(wall.settings(db)['coverage'], 'status')
            self.assertEqual(db.execute('SELECT line_id,signature,device FROM line_prefs').fetchall(), [('100:101', 1, 'wall')])

    # AC2: eviction addresses the named device; the shared-input suite covers the eviction itself.
    def test_eviction_is_routed_to_the_named_device(self):
        self.write_registry(with_panels=True)
        app = self.app()
        calls = []
        def evict(db, device, payload):
            calls.append((device, payload))
        with patch.object(b.shared_input, 'evict', evict):
            app.update('/api/evict', {'id': 'task', 'evictionToken': 'x' * 64, 'device': 'panels'})
            app.update('/api/evict', {'id': 'task', 'evictionToken': 'x' * 64})
            with self.assertRaises(wall_server.UnknownDevice):
                app.update('/api/evict', {'id': 'task', 'evictionToken': 'x' * 64, 'device': 'missing'})
        self.assertEqual(calls, [('panels', {'id': 'task', 'evictionToken': 'x' * 64}),
                                 ('wall', {'id': 'task', 'evictionToken': 'x' * 64})])

    # AC6: the HTTP surface keeps its checks, reads cached geometry only and never leaks a credential.
    def test_http_state_query_rejections_and_privacy(self):
        self.write_registry(with_panels=True)
        app = self.app()
        url = self.serve(app)
        with urlopen(url + '/api/state?device=panels') as response:
            state = json.load(response)
        self.assertEqual((state['device'], state['kind'], len(state['lines'])), ('panels', 'panels', 18))
        with urlopen(url + '/api/state') as response:
            self.assertEqual(json.load(response)['device'], 'wall')
        for view in (state, app.state()):
            text = json.dumps(view)
            self.assertNotIn(LINES_TOKEN, text)
            self.assertNotIn(PANELS_TOKEN, text)
            self.assertNotIn('192.0.2.', text)
        code, body = self.http(url, '/api/state?device=nope')
        self.assertEqual(code, 400)
        self.assertIn('device', body['error'].lower())
        self.assertEqual([d['id'] for d in body['devices']], ['wall', 'panels'])
        self.assertNotIn(PANELS_TOKEN, json.dumps(body))
        code, body = self.http(url, '/api/settings', {'rotation': 90, 'device': 'nope'})
        self.assertEqual(code, 400)
        self.assertEqual([d['id'] for d in body['devices']], ['wall', 'panels'])
        self.assertNotIn(PANELS_TOKEN, json.dumps(body))
        request = Request(url + '/api/settings', data=json.dumps({'rotation': 90, 'device': 'panels'}).encode(),
                          headers={'Content-Type': 'application/json', 'Origin': url})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        error.exception.close()
        self.assertEqual(error.exception.code, 403)
        with self.db() as db:
            self.assertEqual(wall.settings(db, 'panels')['rotation'], 0)
        self.assertEqual(app.rendering()['deviceId'], 'wall')


if __name__ == '__main__':
    unittest.main()
