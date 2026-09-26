"""Serve a wall map with synthetic tasks. Never contacts lights or Codex state."""
import argparse
import contextlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import signal
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))
import bridge
import configuration
import database
import devices
import jsonfile
import panels
import store
import wall_server
import project_map as wall


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    raw = json.loads((ROOT / 'tests/fixtures/lines-layout.json').read_text())
    groups = configuration.pair_lines(raw)
    zones = {p['panelId']: p for p in raw['layout']['positionData']}
    config = {'ip': '192.0.2.1', 'token': 'FAKE_DEMO_TOKEN', 'line_groups': groups,
              'line_positions': [[sum(zones[p][axis] for p in pair)/2 for axis in ('x','y')] for pair in groups],
              'zone_geometry': {'positionData': raw['layout']['positionData'], 'orientation': raw['globalOrientation']['value']}}
    # The synthetic NL22 Light Panels sit beside the Lines so the Device selector can be exercised.
    panels_entry = panels.read_layout(json.loads((ROOT / 'tests/fixtures/nl22-panels-fixture.json').read_text())['panelLayout'])
    panels_config = dict(devices.projection(panels_entry), device='panels')

    def no_device(*args, **kwargs):
        raise RuntimeError('The demo cannot contact a light controller.')

    def update(directory):
        # Stands in for the light workers: apply edits and allocation without any device.
        with contextlib.closing(database.connect_state(directory)) as db, db:
            for target in (config, panels_config):
                device = devices.device_of(target)
                bridge.prune_comets(db, time.time(), store.control_state(db, device)['mode'], device)
                wall.apply_pending(db, device)
                bridge.dashboard(db, target, time.time())
                db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',
                           (devices.meta_key('mode_applied', device), str(store.control_state(db, device)['revision'])))

    with tempfile.TemporaryDirectory(prefix='codex-nanoleaf-demo-') as temporary:
        directory = Path(temporary)
        # The map reads the registry and the saved layout on every request, as the installation's map does.
        jsonfile.write_json(directory / 'config.json', {
            'ip': '192.0.2.1', 'token': 'FAKE_DEMO_TOKEN', 'panelsToken': 'FAKE_DEMO_PANELS',
            'devices': {'wall': {'kind': 'lines', 'ip': '192.0.2.1', 'token_ref': 'token'},
                        'panels': {'kind': 'panels', 'ip': '192.0.2.2', 'token_ref': 'panelsToken'}}})
        devices.save_layout(directory / 'layout.json', {
            'wall': devices.lines_entry(groups, config['line_positions'], {'zone_geometry': config['zone_geometry']}),
            'panels': panels_entry})
        with contextlib.closing(database.connect_state(directory)) as db, db:
            db.executemany('INSERT INTO projects VALUES (?,?,?,?)', [
                ('a','Notification Service','#ad8dff','[]'), ('b','Daily Trader','#39d8bb','[]'), ('c','NBA GM','#f4ad68','[]')])
            titles = ['Verify subscriber delivery','Review callback <b>safe</b>','Confirm trade parameters','Summarize market session','Build player profiles']
            states = [('a','working'),('a','blocked'),('b','question'),('b','unread'),('c','working')]
            for i, (project, status) in enumerate(states):
                sid = f'task-{i}'
                stamp = time.time()-90-i*61
                db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (sid,'1',status,stamp))
                db.execute('INSERT INTO activity VALUES (?,?,?,?)', (sid,'1',status,stamp))
                db.execute('INSERT INTO task_info VALUES (?,?,?,?,?,?,?)', (sid,titles[i],'',project,None,'1',stamp))
        update(directory)
        app = wall_server.App(directory, config, launch=update, request=no_device)
        server = ThreadingHTTPServer(('127.0.0.1', args.port), wall_server.handler(app, secrets.token_hex(32)))
        server.app = app
        def stop(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
        print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
