"""Read-only element geometry on the integration extension for the Lines and the Panels (#169)."""
import contextlib
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from test_bridge import b
import configuration
import launcher
import transport
from test_device_worker import ROOT, triangles
from test_panels_controller import PanelsControllerTest
import controller_server as server
import devices
import integration_api
import project_map as wall


def lines_entry():
    """The Lines entry that the Linux installer saves from the fixture layout, with both geometry caches."""
    raw = json.loads((ROOT / 'tests/fixtures/lines-layout.json').read_text())
    groups = configuration.pair_lines(raw)
    orientation = raw['globalOrientation']['value']
    zones = {p['panelId']: p for p in raw['layout']['positionData']}
    geometry = {'zone_geometry': {'orientation': orientation,
                                  'positionData': [p for p in zones.values() if p['shapeType'] == 18]},
                'connector_geometry': wall.validated_connector_geometry(
                    {'orientation': orientation, 'positionData': raw['layout']['positionData']}, groups)[0]}
    positions = [[sum(zones[p]['x'] for p in pair) / 2, sum(zones[p]['y'] for p in pair) / 2] for pair in groups]
    return devices.lines_entry(groups, positions, geometry)


class GeometryTest(PanelsControllerTest):
    def setUp(self):
        super().setUp()
        self.lines, self.panels = lines_entry(), triangles(18)
        devices.save_layout(self.directory / 'layout.json', {'wall': self.lines, 'panels': self.panels})

    def pure(self, device):
        """Read the route and require unchanged state and layout bytes, no configuration load and no device request."""
        before = [(self.directory / name).read_bytes() for name in ('status.sqlite', 'layout.json')]
        with patch.object(configuration, 'load_config', side_effect=AssertionError('not a pure read')), \
                patch.object(launcher, 'launch_worker', side_effect=AssertionError('read launched work')):
            view = self.app.integration_geometry(self.token, device)
        self.assertEqual(before, [(self.directory / name).read_bytes() for name in ('status.sqlite', 'layout.json')])
        self.assertEqual(self.fake.addresses, [])
        return view

    def expected_elements(self, entry, drawn):
        return [dict(id=e['id'], number=e['number'], zones=e['zones'], points=d['points'])
                for e, d in zip(entry['elements'], drawn, strict=True)]

    def test_lines_return_their_elements_points_and_connectors(self):
        view = self.pure('wall')
        config = devices.projection(self.lines)
        graph = wall.connector_layout(config)
        self.assertEqual(set(view), {'apiVersion', 'identity', 'kind', 'elements', 'connectors'})
        self.assertEqual(view['apiVersion'], 'nanoleaf.integration/1.0')
        self.assertEqual(view['identity'], self.app.integration_snapshot(self.token, 'wall')['identity'])
        self.assertEqual(view['kind'], 'lines')
        self.assertEqual(len(view['elements']), 15)
        self.assertEqual(view['elements'], self.expected_elements(self.lines, wall.geometry(config)))
        self.assertEqual([e['zones'] for e in view['elements']], [e['zones'] for e in self.lines['elements']])
        self.assertTrue(all(len(e['points']) == 3 for e in view['elements']))
        self.assertEqual(view['connectors'], dict(nodes=[dict(id=n['id'], x=n['x'], y=n['y']) for n in graph['nodes']],
                                                  lines=[dict(id=l['id'], a=l['a'], b=l['b']) for l in graph['lines']]))

    def test_panels_return_their_triangles_without_connectors(self):
        view = self.pure('panels')
        self.assertEqual(view['identity']['deviceId'], 'panels')
        self.assertEqual(view['kind'], 'panels')
        self.assertEqual(len(view['elements']), 18)
        self.assertEqual(view['elements'], self.expected_elements(self.panels, wall.triangle_geometry(devices.projection(self.panels))))
        self.assertEqual([e['zones'] for e in view['elements']], [[t['panelId']] for t in self.panels['panel_geometry']['triangles']])
        self.assertIsNone(view['connectors'])

    def test_a_device_without_a_saved_layout_returns_an_explicit_empty_result(self):
        devices.save_layout(self.directory / 'layout.json', {'wall': self.lines})
        view = self.pure('panels')
        self.assertEqual(view, dict(apiVersion='nanoleaf.integration/1.0', identity=view['identity'],
                                    kind=None, elements=[], connectors=None))
        self.assertEqual(view['identity']['deviceId'], 'panels')
        (self.directory / 'layout.json').unlink()
        with patch.object(transport, 'light_request', side_effect=AssertionError('discovered geometry')):
            self.assertEqual(self.app.integration_geometry(self.token, 'wall')['elements'], [])

    def test_a_layout_without_drawable_geometry_keeps_its_elements(self):
        groups = [e['zones'] for e in self.lines['elements']]
        devices.save_layout(self.directory / 'layout.json', {'wall': devices.lines_entry(groups), 'panels': self.panels})
        view = self.pure('wall')
        self.assertEqual([e['id'] for e in view['elements']], [e['id'] for e in self.lines['elements']])
        self.assertTrue(all(e['points'] is None for e in view['elements']))
        self.assertIsNone(view['connectors'])

    def test_unknown_device_fails_as_the_snapshot_does(self):
        for device in ('unknown', ''):
            with self.subTest(device=device):
                with self.assertRaises(integration_api.Failure) as snapshot:
                    self.app.integration_snapshot(self.token, device)
                with self.assertRaises(integration_api.Failure) as geometry:
                    self.app.integration_geometry(self.token, device)
                self.assertEqual(geometry.exception.code, snapshot.exception.code)

    def test_read_scope_and_no_private_values(self):
        reader = server.issue(self.directory, 'reader', ['read'])
        raw = json.dumps([self.app.integration_geometry(reader, device) for device in ('wall', 'panels')])
        for private in ('192.0.2', 'fakeLines', 'fakePanels', 'token', 'ip', str(self.directory), reader, self.token):
            self.assertNotIn(private, raw)
        with self.assertRaises(integration_api.Failure) as failure:
            self.app.integration_geometry('not-a-credential', 'wall')
        self.assertEqual(failure.exception.code, 'unauthenticated')

    def test_invalid_or_oversized_layout_fails_without_a_partial_result(self):
        (self.directory / 'layout.json').write_text('{"version": 2, "devices": {"wall": {"kind": "lines", "elements": []}}}')
        with self.assertRaises(integration_api.Failure) as failure:
            self.app.integration_geometry(self.token, 'wall')
        self.assertEqual(failure.exception.code, 'unsupported-capability')
        (self.directory / 'layout.json').write_bytes(b' ' * (integration_api.MAX_LAYOUT_BYTES + 1))
        with self.assertRaises(integration_api.Failure) as failure:
            self.app.integration_geometry(self.token, 'wall')
        self.assertEqual(failure.exception.code, 'capacity')

    def test_every_extension_route_reads_a_layout_over_64_kib(self):
        # A larger saved layout stays readable by the snapshot and animation routes, not only geometry.
        path = self.directory / 'layout.json'
        path.write_bytes(path.read_bytes() + b' ' * (integration_api.MAX_BODY + 1))
        self.assertEqual(len(self.app.integration_snapshot(self.token, 'wall')['elements']), 15)
        self.assertIn('patterns', self.app.integration_animations(self.token, 'wall'))
        self.assertEqual(len(self.pure('wall')['elements']), 15)

    def test_typescript_consumer_accepts_the_actual_route_outputs(self):
        views = [self.app.integration_geometry(self.token, device) for device in ('wall', 'panels')]
        devices.save_layout(self.directory / 'layout.json', {'wall': self.lines})
        views.append(self.app.integration_geometry(self.token, 'panels'))
        with tempfile.NamedTemporaryFile('w', suffix='.json') as outputs:
            json.dump(views, outputs)
            outputs.flush()
            result = subprocess.run(['node', '--experimental-strip-types', str(ROOT / 'contracts/integration-v1/check.ts'), outputs.name],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['geometryOutputs'], 3)

    def test_http_route_guards_and_unchanged_snapshot(self):
        import test_controller_api
        self.server = server.make_server(self.app)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join()))
        http = lambda *a, **kw: test_controller_api.ControllerHTTPTest.http(self, *a, **kw)
        path = '/controller/integration/v1/geometry?deviceId=panels'
        self.assertEqual(http('GET', path, token=False)[0], 401)
        self.assertEqual(http('GET', path, headers={'Origin': 'https://bad.example'})[0], 403)
        code, view = http('GET', path)
        self.assertEqual((code, view), (200, self.app.integration_geometry(self.token, 'panels')))
        self.assertEqual(http('GET', '/controller/integration/v1/geometry?deviceId=unknown')[0],
                         http('GET', '/controller/integration/v1/snapshot?deviceId=unknown')[0])
        self.assertEqual(http('GET', path + '&extra=1')[0], 404)
        self.assertEqual(http('GET', '/controller/integration/v1/geometry')[0], 400)
        snapshot = http('GET', '/controller/integration/v1/snapshot?deviceId=wall')[1]
        self.assertNotIn('geometry', snapshot)
        self.assertNotIn('connectors', snapshot)
