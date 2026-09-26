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


PROJECTS = [{'id': 'a', 'name': 'Notification Service', 'color': '#ad8dff'},
            {'id': 'b', 'name': 'Daily Trader', 'color': '#39d8bb'},
            {'id': 'c', 'name': 'NBA GM', 'color': '#f4ad68'}]
TASKS = [('Verify subscriber delivery', 'a', 'working'), ('Review callback <b>safe</b>', 'a', 'blocked'),
         ('Confirm trade parameters', 'b', 'question'), ('Summarize market session', 'b', 'unread'),
         ('Build player profiles', 'c', 'working')]


def prepare(directory, now=time.time):
    """Write the synthetic installation into directory; return the Lines configuration and the worker stand-in."""
    raw = json.loads((ROOT / 'tests/fixtures/lines-layout.json').read_text())
    groups = configuration.pair_lines(raw)
    zones = {p['panelId']: p for p in raw['layout']['positionData']}
    config = {'ip': '192.0.2.1', 'token': 'FAKE_DEMO_TOKEN', 'line_groups': groups,
              'line_positions': [[sum(zones[p][axis] for p in pair)/2 for axis in ('x','y')] for pair in groups],
              'zone_geometry': {'positionData': raw['layout']['positionData'], 'orientation': raw['globalOrientation']['value']}}
    # The synthetic NL22 Light Panels sit beside the Lines so the Device selector can be exercised.
    panels_entry = panels.read_layout(json.loads((ROOT / 'tests/fixtures/nl22-panels-fixture.json').read_text())['panelLayout'])
    panels_config = dict(devices.projection(panels_entry), device='panels')

    def update(directory):
        # Stands in for the light workers: apply edits and allocation without any device.
        with contextlib.closing(database.connect_state(directory)) as db, db:
            for target in (config, panels_config):
                device = devices.device_of(target)
                bridge.prune_comets(db, now(), store.control_state(db, device)['mode'], device)
                wall.apply_pending(db, device)
                bridge.dashboard(db, target, now())
                store.mark_applied(db, store.control_state(db, device)['revision'], device)

    # The map reads the registry and the saved layout on every request, as the installation's map does.
    jsonfile.write_json(directory / 'config.json', {
        'ip': '192.0.2.1', 'token': 'FAKE_DEMO_TOKEN', 'panelsToken': 'FAKE_DEMO_PANELS',
        'devices': {'wall': {'kind': 'lines', 'ip': '192.0.2.1', 'token_ref': 'token'},
                    'panels': {'kind': 'panels', 'ip': '192.0.2.2', 'token_ref': 'panelsToken'}}})
    devices.save_layout(directory / 'layout.json', {
        'wall': devices.lines_entry(groups, config['line_positions'], {'zone_geometry': config['zone_geometry']}),
        'panels': panels_entry})
    with contextlib.closing(database.connect_state(directory)) as db, db:
        database.seed_synthetic(db, PROJECTS, [
            {'id': f'task-{i}', 'title': title, 'project': project, 'status': status, 'since': now()-90-i*61}
            for i, (title, project, status) in enumerate(TASKS)])
    update(directory)
    return config, update


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()

    def no_device(*args, **kwargs):
        raise RuntimeError('The demo cannot contact a light controller.')

    with tempfile.TemporaryDirectory(prefix='codex-nanoleaf-demo-') as temporary:
        directory = Path(temporary)
        config, update = prepare(directory)
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
