"""NL22 Light Panels geometry, triangle payloads and triangle presentation rules."""
import contextlib
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_bridge import b, Clock, decode
import configuration
import database
import jsonfile
import devices
import panels
import project_map as wall

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / 'tests/fixtures/nl22-panels-fixture.json').read_text())


def layout(mutate=None):
    value = copy.deepcopy(FIXTURE['panelLayout'])
    if mutate:
        mutate(value['layout']['positionData'])
    return value


class GeometryTest(unittest.TestCase):
    # AC8 and AC13: stable one-zone triangles from reported geometry.
    def test_fixture_reads_eighteen_connected_triangles(self):
        entry = panels.read_layout(layout())
        elements = entry['elements']
        self.assertEqual(entry['kind'], 'panels')
        self.assertEqual(len(elements), 18)
        self.assertEqual([e['number'] for e in elements], list(range(1, 19)))
        reported = {p['panelId']: p for p in FIXTURE['panelLayout']['layout']['positionData']}
        for element in elements:
            (zone,) = element['zones']
            self.assertEqual(element['id'], str(zone))
            self.assertEqual(element['position'], [reported[zone]['x'], reported[zone]['y']])
        geometry = entry['panel_geometry']
        self.assertEqual([t['id'] for t in geometry['triangles']], [e['id'] for e in elements])
        self.assertEqual({t['o'] for t in geometry['triangles']}, {0, 60})
        degree = {e['id']: 0 for e in elements}
        for first, second in geometry['neighbors']:
            degree[first] += 1
            degree[second] += 1
        # Three hexagons of six triangles; two shared edges join them.
        self.assertEqual(len(geometry['neighbors']), 3 * 6 + 2)
        self.assertLessEqual(max(degree.values()), 3)
        self.assertEqual(devices.validate_elements('panels', elements), elements)

    def test_order_is_stable_and_independent_of_report_order(self):
        first = panels.read_layout(layout())
        second = panels.read_layout(layout(lambda points: points.reverse()))
        self.assertEqual(first, second)

    def test_other_valid_counts_are_supported(self):
        def one_hexagon(points):
            keep = sorted(points, key=lambda p: p['x'])[:6]
            points[:] = keep
        self.assertEqual(len(panels.read_layout(layout(one_hexagon))['elements']), 6)
        self.assertEqual(len(panels.read_layout(layout(lambda p: p.__setitem__(slice(1, None), [])))['elements']), 1)

    def test_non_light_modules_are_excluded(self):
        def rhythm(points):
            points.append({'panelId': 999, 'x': 0, 'y': 0, 'o': 0, 'shapeType': 1})
            points.append({'panelId': 998, 'x': 5, 'y': 400, 'o': 0, 'shapeType': 12})
        entry = panels.read_layout(layout(rhythm))
        self.assertEqual(len(entry['elements']), 18)
        self.assertNotIn('999', [e['id'] for e in entry['elements']])

    def test_malformed_or_unsupported_geometry_is_rejected(self):
        first = lambda points: points[0]
        cases = {
            'lines zone': lambda p: first(p).update(shapeType=18),
            'shapes triangle': lambda p: first(p).update(shapeType=8),
            'canvas control square': lambda p: first(p).update(shapeType=3),
            'duplicate id': lambda p: first(p).update(panelId=p[1]['panelId']),
            'text id': lambda p: first(p).update(panelId='55'),
            'boolean id': lambda p: first(p).update(panelId=True),
            'out of range id': lambda p: first(p).update(panelId=70000),
            'missing x': lambda p: first(p).pop('x'),
            'infinite y': lambda p: first(p).update(y=float('inf')),
            'text orientation': lambda p: first(p).update(o='0'),
            'overlap': lambda p: p.append(dict(first(p), panelId=500, x=first(p)['x'] + 10)),
            'disconnected': lambda p: p.append({'panelId': 501, 'x': 5000, 'y': 5000, 'o': 0, 'shapeType': 0}),
            'no triangles': lambda p: p.__setitem__(slice(None), [{'panelId': 1, 'x': 0, 'y': 0, 'o': 0, 'shapeType': 1}]),
            'entry type': lambda p: p.append('panel'),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    panels.read_layout(layout(mutate))
        for broken in (None, [], {'layout': {}}, {'layout': {'positionData': {}}},
                       dict(layout(), globalOrientation={'value': 'north'})):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                panels.read_layout(broken)


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        jsonfile.write_json(self.directory / 'config.json', {
            'ip': '192.0.2.1', 'token': 'fakeLines', 'panelsToken': 'fakePanels',
            'devices': {'panels': {'kind': 'panels', 'ip': '192.0.2.2', 'token_ref': 'panelsToken'}}})
        jsonfile.write_json(self.directory / 'layout.json', {
            'line_groups': [[100 + i * 2, 101 + i * 2] for i in range(15)],
            'line_positions': [[i * 10, 0] for i in range(15)]})
        self.requests = []

    def request(self, config, method, endpoint='', payload=None):
        self.requests.append((config['ip'], config['token'], method, endpoint))
        return {'name': 'Synthetic panels', 'panelLayout': layout()}

    def test_panels_layout_is_discovered_once_and_saved_beside_lines(self):
        config = configuration.load_config(self.directory, 'panels', request=self.request)
        again = configuration.load_config(self.directory, 'panels', request=self.request)
        lines = configuration.load_config(self.directory, request=self.request)
        self.assertEqual(self.requests, [('192.0.2.2', 'fakePanels', 'GET', '')])
        self.assertEqual((config['kind'], len(config['line_groups'])), ('panels', 18))
        self.assertEqual(again['elements'], config['elements'])
        self.assertTrue(all(len(zones) == 1 for zones in config['line_groups']))
        saved = json.loads((self.directory / 'layout.json').read_text())
        self.assertEqual(sorted(saved['devices']), ['panels', 'wall'])
        self.assertIn('panel_geometry', saved['devices']['panels'])
        self.assertEqual(lines['line_groups'], [[100 + i * 2, 101 + i * 2] for i in range(15)])

    def test_rejected_geometry_saves_nothing(self):
        disk = (self.directory / 'layout.json').read_bytes()
        def broken(config, method, endpoint='', payload=None):
            return {'panelLayout': layout(lambda p: p[0].update(shapeType=17))}
        with self.assertRaises(ValueError):
            configuration.load_config(self.directory, 'panels', request=broken)
        self.assertEqual((self.directory / 'layout.json').read_bytes(), disk)


class PayloadTest(unittest.TestCase):
    def setUp(self):
        entry = panels.read_layout(layout())
        self.config = dict(devices.projection(entry), device='panels', ip='192.0.2.2', token='fake')
        self.count = len(self.config['line_groups'])

    def colors(self, payload, element):
        return [tuple(frame[:3]) for frame in decode(payload)[self.config['line_groups'][element][0]]]

    # AC9: one zone per triangle and no Lines-only logical-panel flag.
    def test_custom_payload_has_one_zone_per_triangle(self):
        snapshot = [None] * self.count
        snapshot[0] = ('working', 1000)
        payload = b.effect_payload(self.config, snapshot, 1000, False)
        write = payload['write']
        self.assertEqual(write['animType'], 'custom')
        self.assertNotIn('logicalPanelsEnabled', write)
        values = write['animData'].split()
        self.assertEqual(int(values[0]), self.count)
        frames = decode(payload)
        self.assertEqual(sorted(frames), sorted(z for (z,) in self.config['line_groups']))
        for zone_frames in frames.values():
            self.assertEqual(sum(frame[4] for frame in zone_frames), b.PULSE_TICKS)
            self.assertTrue(all(frame[3] == 0 for frame in zone_frames))
        idle = b.effect_payload(self.config, [None] * self.count, 1000, True)['write']
        self.assertEqual(idle['animType'], 'static')
        self.assertTrue(all(len(f) == 1 for f in decode({'write': idle}).values()))

    def test_lines_payload_keeps_logical_zones(self):
        lines = {'line_groups': [[100 + i * 2, 101 + i * 2] for i in range(15)],
                 'line_positions': [[i * 10, 0] for i in range(15)]}
        write = b.effect_payload(lines, [('working', 1000)] + [None] * 14, 1000, False)['write']
        self.assertIs(write['logicalPanelsEnabled'], True)
        self.assertEqual(int(write['animData'].split()[0]), 30)

    # AC10: whole triangles, travel within the arrangement and alert priority.
    def test_wave_reaches_neighbors_before_distant_triangles(self):
        positions = self.config['line_positions']
        source = 0
        delays = b.travel_delays(self.config, source)
        order = sorted(range(self.count), key=lambda i: delays[i])
        near, far = order[1], order[-1]
        self.assertLess(delays[near], delays[far])
        snapshot = [None] * self.count
        snapshot[source] = ('blocked', 0)
        table = [b.travel_delays(self.config, i) for i in range(self.count)]
        arrival = lambda target: next(t / 100 for t in range(0, 200) if b.pixel_color(snapshot, target, t / 100, table) != b.BASELINE)
        self.assertLess(arrival(near), arrival(far))
        self.assertEqual(b.pixel_color(snapshot, far, 5.3, table), b.BASELINE)
        self.assertEqual(b.pixel_color(snapshot, source, 2.5, table)[0] > 0, True)
        self.assertGreater(len({tuple(p) for p in positions}), 1)

    def test_comet_keeps_question_triangle_and_returns_others(self):
        snapshot = [None] * self.count
        snapshot[5] = ('question', 900)
        cfg = dict(self.config, _comet={'source': 0, 'started': 1000}, _mode='work')
        payload = b.effect_payload(cfg, snapshot, 1000, True)
        self.assertFalse(payload['write']['loop'])
        self.assertEqual(set(self.colors(payload, 5)) & {(255, 255, 255)}, set())
        self.assertTrue(all(c[0] > 0 and c[1] > 0 and c[2] == 0 for c in self.colors(payload, 5)))
        others = [i for i in range(self.count) if i != 5]
        self.assertTrue(any((255, 255, 255) in self.colors(payload, i) for i in others))
        self.assertTrue(all(self.colors(payload, i)[-1] == b.BASELINE for i in others))

    # AC11: triangles never show project halves.
    def test_project_layout_never_splits_a_triangle(self):
        cfg = dict(self.config, _style='project', _coverage='whole', _signatures=[((200, 0, 200), 0)] * self.count)
        snapshot = [None] * self.count
        snapshot[3] = ('working', 1000)
        payload = b.effect_payload(cfg, snapshot, 1000, True)
        for element in range(self.count):
            self.assertNotIn((200, 0, 200), self.colors(payload, element))

    # AC12: Locate flashes one triangle only.
    def test_locate_targets_one_triangle(self):
        cfg = dict(self.config, _locate={'source': 7, 'started': 1000})
        payload = b.effect_payload(cfg, [None] * self.count, 1000, False)
        for element in range(self.count):
            flashed = (255, 255, 255) in self.colors(payload, element)
            self.assertEqual(flashed, element == 7)


class ReservationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        entry = panels.read_layout(layout())
        self.config = dict(devices.projection(entry), device='panels')
        self.clock = Clock()

    def db(self):
        return contextlib.closing(database.connect_state(self.directory))

    # AC11: a six-triangle region reserved by one ordinary multi-element edit.
    def test_six_triangle_reservation_and_shared_overflow(self):
        ids = [e['id'] for e in self.config['elements']]
        region = ids[:6]
        with self.db() as db, db:
            db.execute("INSERT INTO projects VALUES ('p','P','#00ff00','[]'), ('q','Q','#ff00ff','[]')")
            deferred = wall.request_patch(db, {'settings': {'style': 'project'},
                                               'lines': {i: {'project': 'p'} for i in region}}, self.config)
            self.assertFalse(deferred)
            rows = []
            for n in range(20):
                session = f's{n:02d}'
                project = 'p' if n < 8 else 'q'
                db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (session, '1', 'working', n))
                db.execute('INSERT INTO task_info VALUES (?,?,?,?,?,?,?)', (session, '', '', project, None, '1', None))
                rows.append((session, '1', 'working'))
            assigned = wall.allocate(db, self.config, rows, set())
        region_slots = set(range(6))
        for session, slot in assigned.items():
            if session >= 's08':
                self.assertNotIn(slot, region_slots)
        self.assertEqual(len(assigned), 18)
        # Shared triangles hold the overflow of p; q never borrows p's region.
        self.assertEqual({assigned[f's{n:02d}'] for n in range(6)}, region_slots)
        with self.db() as db:
            self.assertEqual(wall.settings(db)['style'], 'classic')
            self.assertEqual(wall.settings(db, 'panels')['style'], 'project')

    def test_render_config_gives_triangles_no_signature(self):
        ids = [e['id'] for e in self.config['elements']]
        with self.db() as db, db:
            db.execute("INSERT INTO projects VALUES ('p','P','#00ff00','[]')")
            wall.request_patch(db, {'settings': {'style': 'project'}, 'lines': {ids[0]: {'project': 'p'}}}, self.config)
            wall.render_config(db, self.config, [None] * len(ids))
        self.assertEqual(self.config['_style'], 'project')
        self.assertEqual(self.config['_signatures'], [])


if __name__ == '__main__':
    unittest.main()
