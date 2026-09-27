"""Serve a wall map with synthetic tasks. Never contacts lights or Codex state.

Without a command, serve the reference scenario from a temporary directory. The verification
adapter (#193) uses the commands: `seed` writes a named scenario into a run's empty state
directory, `serve` runs the actual wall server over it, and `drive` applies a named task
transition through the actual hook handler. Every entry point first installs a process guard
that refuses and records any socket connection, new process or light request.
"""
import argparse
import contextlib
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import signal
import sqlite3
import sys
import tempfile
import threading
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

BOUNDARY_LOG = 'device-boundary.jsonl'
PROJECTS = [{'id': 'a', 'name': 'Notification Service', 'color': '#ad8dff'},
            {'id': 'b', 'name': 'Daily Trader', 'color': '#39d8bb'},
            {'id': 'c', 'name': 'NBA GM', 'color': '#f4ad68'}]
TASKS = [('Verify subscriber delivery', 'a', 'working'), ('Review callback <b>safe</b>', 'a', 'blocked'),
         ('Confirm trade parameters', 'b', 'question'), ('Summarize market session', 'b', 'unread'),
         ('Build player profiles', 'c', 'working')]
# The hook waits behind the reference alerts: task-1 waits on a shell approval, task-2 on an asynchronous question.
WAITS = [('task-1', '1', 'permission:shell', 'permission', 'shell'),
         ('task-2', '1', 'input:call-1', 'async', 'request_user_input_async')]

SCENARIOS = {
    'reference': {'description': 'Lines and Light Panels in Work with five tasks in all four statuses across three projects',
                  'tasks': True, 'geometry': True},
    'empty': {'description': 'Lines and Light Panels in Work with no tasks, so the wall rests on its remembered scene',
              'tasks': False, 'geometry': True},
    'layout-unavailable': {'description': 'The reference tasks on Lines saved without drawing geometry, so the map asks '
                                          'the device for its layout and the boundary refuses the request',
                           'tasks': True, 'geometry': False},
}


def event(name, session, turn='1', tool=None):
    return {'hook_event_name': name, 'session_id': session, 'turn_id': turn, **({'tool_name': tool} if tool else {})}


# Hook events for the reference tasks. A defect is a known-wrong result that the scenario assertions must reject.
TRANSITIONS = {
    'complete': {'description': 'task-0 finishes its turn: working to unread, with a completion comet queued per device',
                 'defect': False, 'events': [event('Stop', 'task-0')]},
    'approve': {'description': 'task-1 receives its shell approval: blocked to working, clearing the red alert',
                'defect': False, 'events': [event('PostToolUse', 'task-1', tool='shell')]},
    'request-approval': {'description': 'task-4 asks for a shell approval: working to blocked',
                         'defect': False, 'events': [event('PermissionRequest', 'task-4', tool='shell')]},
    'resume': {'description': 'task-3 starts a new turn: unread to working',
               'defect': False, 'events': [event('UserPromptSubmit', 'task-3', turn='2')]},
    'defect-approve-other-tool': {'description': 'Known-wrong approval: a result for another tool leaves task-1 waiting, so its red stays',
                                  'defect': True, 'events': [event('PostToolUse', 'task-1', tool='apply_patch')]},
    'defect-complete-stale-turn': {'description': 'Known-wrong completion: a Stop for an earlier turn is ignored, so task-0 stays working',
                                   'defect': True, 'events': [event('Stop', 'task-0', turn='0')]},
}


class DeviceBoundaryError(ConnectionRefusedError):
    """A synthetic run refused to reach a light, a service or a new process."""


# Audit events that would leave the process. The wall server only accepts connections.
REFUSED_EVENTS = frozenset({'socket.connect', 'socket.sendto', 'socket.sendmsg', 'subprocess.Popen', 'os.system',
                            'os.exec', 'os.posix_spawn', 'os.spawn', 'os.fork', 'os.forkpty', 'pty.spawn'})


def refused(error):
    """True when error, or an error it wraps, is a boundary refusal."""
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        if isinstance(current, DeviceBoundaryError):
            return True
        seen.add(id(current))
        reason = getattr(current, 'reason', None)
        pending += [reason if isinstance(reason, BaseException) else None, current.__cause__, current.__context__]
    return False


def refuse_light_request(config, method, endpoint='', payload=None):
    """A transport.light_request stand-in that never sends."""
    raise DeviceBoundaryError('The synthetic wall cannot contact a light controller.')


def program(event_name, args):
    """The program name a process event would start, without its arguments or directory."""
    if event_name == 'subprocess.Popen':
        target = args[0] if args[0] is not None else args[1]
    elif event_name in ('os.exec', 'os.posix_spawn', 'os.system', 'pty.spawn'):
        target = args[0]
    elif event_name == 'os.spawn':
        target = args[1]
    else:
        return event_name
    if isinstance(target, (list, tuple)):
        target = target[0] if target else ''
    if isinstance(target, bytes):
        target = target.decode(errors='replace')
    words = str(target).split()
    return Path(words[0]).name if words else event_name


class Boundary:
    """Refuses every way out of the process and records each attempt, without its credential."""

    def __init__(self, log):
        self.log = Path(log)
        self.lock = threading.Lock()

    def record(self, kind, target, **detail):
        entry = {'at': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                 'kind': kind, 'target': target, **detail, 'outcome': 'refused'}
        with self.lock, open(self.log, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(entry) + '\n')

    def light_request(self, config, method, endpoint='', payload=None):
        """The wall server's device seam."""
        self.record('light-request', str(config.get('ip')), method=method, endpoint=endpoint)
        refuse_light_request(config, method, endpoint, payload)

    def audit(self, name, args):
        if name not in REFUSED_EVENTS:
            return
        if name.startswith('socket.'):
            address = args[1] if len(args) > 1 else None
            target = f'{address[0]}:{address[1]}' if isinstance(address, tuple) and len(address) >= 2 else str(address)
            kind = name
        else:
            kind, target = 'process', program(name, args)
        self.record(kind, target)
        raise DeviceBoundaryError(f'The synthetic wall refused {kind} to {target}.')


def install_boundary(log):
    """Refuse device, service and process access for the rest of this process. It cannot be removed."""
    boundary = Boundary(log)
    sys.addaudithook(boundary.audit)
    return boundary


def registered(directory):
    return configuration.registered_devices(directory)


def worker_stand_in(directory, now=time.time, request=refuse_light_request):
    """Stand in for the light workers: apply edits and allocation for every registered device, without any device."""
    targets = [configuration.load_config(directory, device, request=request) for device in registered(directory)]

    def update(directory):
        with contextlib.closing(database.connect_state(directory)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            for target in targets:
                device = devices.device_of(target)
                bridge.prune_comets(db, now(), store.control_state(db, device)['mode'], device)
                wall.apply_pending(db, device)
                bridge.dashboard(db, target, now())
                store.mark_applied(db, store.control_state(db, device)['revision'], device)
    return update


def seed(directory, scenario='reference', now=time.time):
    """Write a scenario's synthetic installation into an empty state directory and run the worker stand-in once."""
    directory = Path(directory)
    if scenario not in SCENARIOS:
        raise ValueError(f'Unknown scenario {scenario!r}. Choose one of: {", ".join(SCENARIOS)}.')
    if any(directory.iterdir()):
        raise ValueError('Seed an empty state directory. A run resets its state by emptying it first.')
    definition = SCENARIOS[scenario]
    raw = json.loads((ROOT / 'tests/fixtures/lines-layout.json').read_text())
    groups = configuration.pair_lines(raw)
    zones = {p['panelId']: p for p in raw['layout']['positionData']}
    positions = [[sum(zones[p][axis] for p in pair) / 2 for axis in ('x', 'y')] for pair in groups]
    drawing = {'zone_geometry': {'positionData': raw['layout']['positionData'],
                                 'orientation': raw['globalOrientation']['value']}} if definition['geometry'] else None
    # The synthetic NL22 Light Panels sit beside the Lines so the Device selector can be exercised.
    panels_entry = panels.read_layout(json.loads((ROOT / 'tests/fixtures/nl22-panels-fixture.json').read_text())['panelLayout'])
    # The map reads the registry and the saved layout on every request, as the installation's map does.
    # The synthetic credentials pass the transport's own checks, so only the boundary stops a request.
    jsonfile.write_json(directory / 'config.json', {
        'ip': '192.0.2.1', 'token': 'FakeDemoToken', 'panelsToken': 'FakeDemoPanels',
        'devices': {'wall': {'kind': 'lines', 'ip': '192.0.2.1', 'token_ref': 'token'},
                    'panels': {'kind': 'panels', 'ip': '192.0.2.2', 'token_ref': 'panelsToken'}}})
    devices.save_layout(directory / 'layout.json', {'wall': devices.lines_entry(groups, positions, drawing), 'panels': panels_entry})
    tasks = TASKS if definition['tasks'] else []
    with contextlib.closing(database.connect_state(directory)) as db, db:
        database.seed_synthetic(db, PROJECTS, [
            {'id': f'task-{i}', 'title': title, 'project': project, 'status': status, 'since': now()-90-i*61}
            for i, (title, project, status) in enumerate(tasks)])
        if tasks:
            db.executemany('INSERT INTO waits (session,turn,key,kind,tool) VALUES (?,?,?,?,?)', WAITS)
    worker_stand_in(directory, now)(directory)


def prepare(directory, now=time.time):
    """Seed the reference scenario; return the Lines configuration and the worker stand-in."""
    seed(directory, 'reference', now)
    return configuration.load_config(directory, request=refuse_light_request), worker_stand_in(directory, now)


def drive(directory, transition, now=time.time, request=refuse_light_request):
    """Apply a named transition's hook events through the actual hook handler, then the worker stand-in."""
    if transition not in TRANSITIONS:
        raise ValueError(f'Unknown transition {transition!r}. Choose one of: {", ".join(TRANSITIONS)}.')
    update = worker_stand_in(directory, now, request)
    events = TRANSITIONS[transition]['events']
    for item in events:
        bridge.handle_event(directory, dict(item), launch=update, now=now)
    sessions = sorted({item['session_id'] for item in events})
    with contextlib.closing(sqlite3.connect(directory / 'status.sqlite')) as db:
        statuses = dict(db.execute(f'SELECT id,status FROM sessions WHERE id IN ({",".join("?" * len(sessions))})', sessions))
    return {'transition': transition, 'tasks': statuses}


def serve(directory, boundary, port=0, now=time.time):
    """Serve a seeded state directory on 127.0.0.1 until SIGTERM, starting as the installed map does."""
    config = configuration.load_config(directory, request=boundary.light_request)
    wall_server.ensure_geometry(directory, config, request=boundary.light_request)
    app = wall_server.App(directory, config, launch=worker_stand_in(directory, now, boundary.light_request),
                          request=boundary.light_request)
    instance = secrets.token_hex(16)
    server = ThreadingHTTPServer(('127.0.0.1', port), wall_server.handler(app, secrets.token_hex(32), instance))
    server.app = app

    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    # The installed map's receipt: a probe matches this instance against /health.
    jsonfile.write_json(directory / 'map-server.json', {'port': server.server_port, 'instance': instance, 'boundary': 'refusing'})
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'instance': instance}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=8765, help='Port for the temporary demo; 0 picks a free one.')
    commands = parser.add_subparsers(dest='command')
    commands.add_parser('scenarios', help='Print the scenario names and descriptions as JSON.')
    seeding = commands.add_parser('seed', help='Write a scenario into an empty state directory.')
    serving = commands.add_parser('serve', help='Serve a seeded state directory on 127.0.0.1.')
    driving = commands.add_parser('drive', help='Apply a named task transition to a seeded state directory.')
    for command in (seeding, serving, driving):
        command.add_argument('--state-dir', type=Path, required=True)
    seeding.add_argument('--scenario', choices=list(SCENARIOS), default='reference')
    serving.add_argument('--port', type=int, default=0, help='Port on 127.0.0.1; 0 picks a free one.')
    driving.add_argument('transition', choices=list(TRANSITIONS))
    args = parser.parse_args(argv)

    if args.command == 'scenarios':
        print(json.dumps({name: scenario['description'] for name, scenario in SCENARIOS.items()}))
        return
    if args.command is None:
        with tempfile.TemporaryDirectory(prefix='codex-nanoleaf-demo-') as temporary:
            directory = Path(temporary)
            boundary = install_boundary(directory / BOUNDARY_LOG)
            seed(directory, 'reference')
            serve(directory, boundary, args.port)
        return
    directory = args.state_dir.resolve()
    boundary = install_boundary(directory / BOUNDARY_LOG)
    if args.command == 'seed':
        seed(directory, args.scenario)
        print(json.dumps({'scenario': args.scenario}))
    elif args.command == 'drive':
        print(json.dumps(drive(directory, args.transition, request=boundary.light_request)))
    else:
        serve(directory, boundary, args.port)


if __name__ == '__main__':
    main()
