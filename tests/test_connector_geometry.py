import copy
import contextlib
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_bridge import b
import project_map as wall
import wall_server


class ConnectorGeometryTest(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((Path(__file__).parent / 'fixtures/lines-layout.json').read_text())
        self.groups = b.pair_lines(self.raw)
        self.config = {'line_groups': self.groups, 'zone_geometry': {
            'positionData': self.raw['layout']['positionData'],
            'orientation': self.raw['globalOrientation']['value']}}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config.update(ip='192.0.2.1',token='SECRET_CANARY',line_positions=[[i,0] for i in range(15)])
        (self.directory/'layout.json').write_text(json.dumps(self.config))

    def test_actual_layout_preserves_identity_and_reported_housings(self):
        graph = wall.connector_layout(self.config)
        self.assertEqual(graph['version'], 1)
        self.assertEqual(len(graph['lines']), 15)
        self.assertEqual([line['id'] for line in graph['lines']], [wall.line_id(pair) for pair in self.groups])
        self.assertEqual([line['number'] for line in graph['lines']], list(range(1, 16)))
        self.assertEqual([line['zoneIds'] for line in graph['lines']], self.groups)
        shared = next(node for node in graph['nodes'] if 1036 in node['sourceIds'])
        self.assertEqual(shared['sourceIds'], [1028, 1036])
        self.assertAlmostEqual(shared['x'], 423)
        self.assertAlmostEqual(shared['y'], 402)
        self.assertEqual(len({node['id'] for node in graph['nodes']}), 12)
        self.assertTrue(all(line['a'] != line['b'] for line in graph['lines']))
        self.assertEqual(wall.geometry(self.config), wall.geometry(copy.deepcopy(self.config)))

    def legacy(self):
        self.config['zone_geometry']['positionData'] = [p for p in self.config['zone_geometry']['positionData'] if p['shapeType']==18]
        (self.directory/'layout.json').write_text(json.dumps(self.config))

    def test_legacy_cache_is_enriched_without_replacing_saved_state(self):
        self.legacy()
        old = copy.deepcopy(self.config)
        with contextlib.closing(b.connect_state(self.directory)) as db,db:
            db.execute("INSERT INTO line_prefs VALUES (?, 'project-canary', 1)", (wall.line_id(self.groups[0]),))
            before = list(db.iterdump())
        with patch.object(b,'light_request',return_value={'panelLayout': self.raw}) as read:
            wall_server.ensure_geometry(self.directory,b,self.config)
            self.assertIsNotNone(self.config.get('connector_geometry'))
            wall_server.ensure_geometry(self.directory,b,self.config)
            read.assert_called_once_with(self.config,'GET')
        saved = json.loads((self.directory/'layout.json').read_text())
        self.assertEqual({key:saved[key] for key in old}, old)
        self.assertEqual(self.config['zone_geometry'], old['zone_geometry'])
        self.assertEqual(saved['connector_geometry'], self.config['connector_geometry'])
        self.assertNotIn('SECRET_CANARY',json.dumps(saved['connector_geometry']))
        with contextlib.closing(b.connect_state(self.directory)) as db:
            self.assertEqual(list(db.iterdump()),before)

    def test_graph_is_allowlisted_and_rejects_invalid_geometry(self):
        self.config['zone_geometry']['private'] = 'SOURCE_SECRET'
        self.config['zone_geometry']['positionData'][0]['token'] = 'SOURCE_SECRET'
        self.assertNotIn('SECRET',json.dumps(wall.connector_layout(self.config)))
        for mutate in (
            lambda p: p['positionData'][1].update(x=float('nan')),
            lambda p: p['positionData'][0].update(shapeType=17),
            lambda p: p['positionData'].append(dict(p['positionData'][1])),
            lambda p: p['positionData'].__delitem__(0),
            lambda p: p['positionData'][0].update(x=900000),
        ):
            broken=copy.deepcopy(self.config)
            mutate(broken['zone_geometry'])
            self.assertIsNone(wall.connector_layout(broken))
        for groups in ([[True,1001]], [self.groups[0],self.groups[0]], [], None):
            self.assertIsNone(wall.connector_layout(dict(self.config,line_groups=groups)))

    def test_synthetic_topologies_and_orientation_preserve_zone_ownership(self):
        shapes = {
            'chain': ([(0,0),(180,0),(360,0)],[(0,1),(1,2)]),
            'branch': ([(0,0),(180,0),(-90,90*math.sqrt(3)),(-90,-90*math.sqrt(3))],[(0,1),(0,2),(0,3)]),
            'cycle': ([(0,0),(180,0),(90,90*math.sqrt(3))],[(0,1),(1,2),(2,0)]),
            'disconnected': ([(0,0),(180,0),(0,400),(180,400)],[(0,1),(2,3)]),
        }
        for name,(nodes,edges) in shapes.items():
            points=[{'panelId':i+1,'shapeType':16,'x':x,'y':y,'o':0} for i,(x,y) in enumerate(nodes)]
            groups=[]
            for i,(a,z) in enumerate(edges):
                pair=[100+i*2,101+i*2];groups.append(pair)
                for pid,t in zip(pair,(.25,.75)):
                    points.append({'panelId':pid,'shapeType':18,'x':nodes[a][0]*(1-t)+nodes[z][0]*t,'y':nodes[a][1]*(1-t)+nodes[z][1]*t,'o':0})
            for orientation in (0,90,180,270):
                with self.subTest(name=name,orientation=orientation):
                    config={'line_groups':groups,'zone_geometry':{'positionData':points,'orientation':orientation}}
                    graph=wall.connector_layout(config)
                    self.assertIsNotNone(graph)
                    self.assertEqual([(line['a'],line['b']) for line in graph['lines']],[(str(a+1),str(z+1)) for a,z in edges])
                    self.assertEqual([line['zoneIds'] for line in graph['lines']],groups)
                    for node,(x,y) in zip(graph['nodes'],nodes):
                        angle=math.radians(orientation)
                        self.assertAlmostEqual(node['x'],x*math.cos(angle)-y*math.sin(angle))
                        self.assertAlmostEqual(node['y'],-(x*math.sin(angle)+y*math.cos(angle)))

    def test_fresh_cache_and_failed_persistence_are_atomic(self):
        del self.config['zone_geometry']
        original=copy.deepcopy(self.config)
        disk=(self.directory/'layout.json').read_bytes()
        with patch.object(b,'light_request',return_value={'panelLayout':self.raw}), patch.object(b,'write_json',side_effect=OSError('PRIVATE_FAILURE')):
            self.assertFalse(wall_server.ensure_geometry(self.directory,b,self.config))
        self.assertEqual(self.config,original)
        self.assertEqual((self.directory/'layout.json').read_bytes(),disk)
        with patch.object(b,'light_request',return_value={'panelLayout':self.raw}):
            self.assertTrue(wall_server.ensure_geometry(self.directory,b,self.config))
        self.assertEqual(len(wall.geometry(self.config)),15)
        self.assertEqual(len(wall.connector_layout(self.config)['lines']),15)
        with patch.object(b,'light_request',side_effect=AssertionError('Valid cache must not read device')):
            self.assertTrue(wall_server.ensure_geometry(self.directory,b,self.config))

    def test_state_exposes_graph_and_preserves_legacy_fields(self):
        app=wall_server.App(self.directory,b,self.config,launch=lambda _: self.fail('No worker launch'))
        state=app.state()
        self.assertEqual(state['connector_layout'],wall.connector_layout(self.config))
        self.assertIsNone(state['connector_error'])
        for line,expected in zip(state['lines'],wall.geometry(self.config)):
            self.assertEqual({key:line[key] for key in expected},expected)
        self.assertNotIn('SECRET_CANARY',json.dumps(state))

    def test_failed_acquisition_is_bounded_in_free_and_can_recover(self):
        self.legacy()
        moment=[0]
        b.set_mode(self.directory,'free',launch=lambda _:None)
        with patch.object(wall_server.time,'monotonic',side_effect=lambda:moment[0]):
            app=wall_server.App(self.directory,b,self.config,launch=lambda _: self.fail('No worker launch'))
            with patch.object(b,'light_request',side_effect=OSError('PRIVATE_FAILURE')) as read:
                for instant in range(10,100,10):
                    moment[0]=instant
                    state=app.state()
                    self.assertEqual(len(state['lines']),15)
                    self.assertIsNone(state['connector_layout'])
                    self.assertNotIn('PRIVATE_FAILURE',json.dumps(state))
                self.assertEqual(read.call_count,3)
            moment[0]=100
            resumed=wall_server.App(self.directory,b,self.config,launch=lambda _:None)
            with patch.object(b,'light_request',side_effect=[OSError('unavailable'),{'panelLayout':self.raw}]) as read:
                moment[0]=110; self.assertIsNone(resumed.state()['connector_layout'])
                moment[0]=120; self.assertIsNotNone(resumed.state()['connector_layout'])
                moment[0]=150; resumed.state()
                self.assertEqual(read.call_count,2)

    def test_concurrent_state_reads_share_one_complete_enrichment(self):
        self.legacy()
        app=wall_server.App(self.directory,b,self.config,launch=lambda _: self.fail('No worker launch'))
        app.geometry_retry=0
        with patch.object(b,'light_request',return_value={'panelLayout':self.raw}) as read:
            with ThreadPoolExecutor(max_workers=8) as pool:
                states=list(pool.map(lambda _:app.state(),range(24)))
            self.assertEqual(read.call_count,1)
        self.assertTrue(all(s['connector_layout']==states[0]['connector_layout'] for s in states))
        self.assertEqual(json.loads((self.directory/'layout.json').read_text())['connector_geometry'],self.config['connector_geometry'])
