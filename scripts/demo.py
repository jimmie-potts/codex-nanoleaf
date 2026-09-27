"""Serve a wall map with synthetic tasks. Never contacts lights or Codex state.

Without a command, serve the reference scenario from a temporary directory. The verification
adapter (#193) uses the commands: `seed` writes a named scenario into a run's empty state
directory and marks it with demo-run.json, `serve` runs the actual wall server over a marked
directory, and `drive` applies a named task transition to one through the actual hook handler.
Neither accepts an unmarked directory or the installation's own state directory. Before calling
any bridge function, every entry point installs a process boundary that refuses and records
outbound connections, new processes, foreign code loaded through ctypes, new subinterpreters and
light requests. Importing the bridge modules first has no side effects.

The hub-paired scenario (#194) makes a run a consumer of a paired Hub run: its boundary also allows,
and records, connections to that Hub's loopback feed port and nothing else; `serve` runs the real
controller API listener the Hub calls; and a stand-in writer polls the Hub's feed through the real
shared-input Poller and applies integration settings about once per second.
"""
import argparse
import contextlib
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import importlib
import json
import os
from pathlib import Path
import queue
import re
import secrets
import signal
import socket
import sqlite3
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))
import bridge
import configuration
import controller_server
import database
import devices
import integration_api
import jsonfile
import panels
import shared_input
import shared_source
import store
import wall_server
import project_map as wall

BOUNDARY_LOG = 'device-boundary.jsonl'
# Written by `seed`; `serve` and `drive` refuse a directory without it.
MARKER = 'demo-run.json'
PROJECTS = [{'id': 'a', 'name': 'Notification Service', 'color': '#ad8dff'},
            {'id': 'b', 'name': 'Daily Trader', 'color': '#39d8bb'},
            {'id': 'c', 'name': 'NBA GM', 'color': '#f4ad68'}]
TASKS = [('Verify subscriber delivery', 'a', 'working'), ('Review callback <b>safe</b>', 'a', 'blocked'),
         ('Confirm trade parameters', 'b', 'question'), ('Summarize market session', 'b', 'unread'),
         ('Build player profiles', 'c', 'working')]
# The hook waits behind the reference alerts: task-1 waits on a shell approval, task-2 on an asynchronous question.
WAITS = [('task-1', '1', 'permission:shell', 'permission', 'shell'),
         ('task-2', '1', 'input:call-1', 'async', 'request_user_input_async')]
# Ports of the installed services. A run never serves on one, and a paired Hub never names one.
INSTALLED_PORTS = frozenset({8788, 8765, 8787, 8791, 41230, 41231})

# The pairing convention of Hub #495's integrated preview. The orchestrator writes both credential
# files, mode 0600, into the run's runtime directory before it reseeds the run hub-paired; the Hub
# presents the controller token to this run's controller API, and this run presents the feed token
# to the Hub's monitor feed. Neither value is ever printed or recorded.
HUB_PAIRED = 'hub-paired'
FEED_TOKEN = 'hub-feed-token'
CONTROLLER_TOKEN = 'hub-controller-token'
PAIRED_OWNER = 'verify-owner'
PAIRED_CONSUMER = 'nanoleaf'
PAIRED_SOURCE = {'provider': 'codex', 'client': 'cli', 'hostId': 'verify-host', 'sourceId': 'verify-source'}
CONTROLLER = {'controllerId': 'wall-controller', 'deviceId': 'wall', 'sourceId': 'wall'}
HUB_PRINCIPAL = 'hub'

SCENARIOS = {
    'reference': {'description': 'Lines and Light Panels in Work with five tasks in all four statuses across three projects',
                  'tasks': True, 'geometry': True},
    'empty': {'description': 'Lines and Light Panels in Work with no tasks, so the wall rests on its remembered scene',
              'tasks': False, 'geometry': True},
    'layout-unavailable': {'description': 'The reference tasks on Lines saved without drawing geometry, so the map asks '
                                          'the device for its layout and the boundary refuses the request',
                           'tasks': True, 'geometry': False},
    HUB_PAIRED: {'description': "Lines and Light Panels with no local tasks, following a paired Hub run's session feed "
                                'and serving the controller API that Hub calls',
                 'tasks': False, 'geometry': True, 'paired': True},
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
    'defect-complete-contacts-device': {'description': 'Known-wrong completion: task-0 completes, but the worker stand-in also tries to send '
                                                       'the effect to each device, which the boundary refuses and records',
                                        'defect': True, 'events': [event('Stop', 'task-0')], 'contacts_device': True},
    # hub-paired takes no hook events: the Hub owns task state there. These defects are its known-wrong writers.
    'defect-poll-installed-hub': {'description': "Known-wrong feed: the paired stand-in polls the installed Hub's port 8788 instead of "
                                                 'the paired run, which the boundary refuses and records',
                                  'defect': True, 'paired': True, 'events': [], 'polls_installed_hub': True},
    'defect-paired-light-request': {'description': 'Known-wrong writer: the paired stand-in also tries to send the effect to each device, '
                                                   'which the boundary refuses and records',
                                    'defect': True, 'paired': True, 'events': [], 'contacts_device': True},
}


class DeviceBoundaryError(ConnectionRefusedError):
    """A synthetic run refused to reach a light, a service or a new process."""


class PairingError(ValueError):
    """A hub-paired seed without a usable paired Hub origin or credential file. The message never holds a path or value."""


# Audit events that would leave the process. The wall server only accepts connections, starts no
# process, loads no foreign code and creates no interpreter.
REFUSED_EVENTS = frozenset({'socket.connect', 'socket.sendto', 'socket.sendmsg', 'subprocess.Popen', 'os.system',
                            'os.exec', 'os.posix_spawn', 'os.spawn', 'os.fork', 'os.forkpty', 'pty.spawn',
                            'ctypes.dlopen', 'ctypes.dlsym', 'ctypes.call_function', 'cpython.PyInterpreterState_New'})
# Standard-library launchers that raise no audit event: multiprocessing's spawn and forkserver start
# children through fork_exec, and concurrent.interpreters through _interpreters.create. The boundary
# replaces each with a recording refusal. These are the only attributes the demo ever replaces.
UNAUDITED = (('_posixsubprocess', 'fork_exec', 'process'), ('_interpreters', 'create', 'subinterpreter'),
             ('_xxsubinterpreters', 'create', 'subinterpreter'))


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
    """Refuses every way out of the process and records each attempt, without its credential.

    A hub-paired run's boundary also allows TCP connections to its paired Hub's feed port on
    127.0.0.1, recording each as `allowed`. It never allows an installed service's port.
    """

    def __init__(self, log, paired_port=None):
        self.log = Path(log)
        self.lock = threading.Lock()
        self.paired = paired_port if type(paired_port) is int and paired_port not in INSTALLED_PORTS else None

    def record(self, kind, target, outcome='refused', **detail):
        entry = {'at': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                 'kind': kind, 'target': target, **detail, 'outcome': outcome}
        with self.lock, open(self.log, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(entry) + '\n')

    def allows(self, name, args):
        """True only for a TCP connect to 127.0.0.1 on the paired Hub's feed port."""
        if name != 'socket.connect' or self.paired is None or len(args) < 2:
            return False
        sock, address = args[0], args[1]
        return (getattr(sock, 'family', None) == socket.AF_INET and getattr(sock, 'type', None) == socket.SOCK_STREAM
                and address == ('127.0.0.1', self.paired))

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
            if self.allows(name, args):
                # The address the process asked for, not the policy's port, so the log can show a leak.
                self.record(name, target, outcome='allowed')
                return
            kind = name
        elif name == 'ctypes.dlopen':
            kind, target = name, Path(str(args[0])).name if args and args[0] else 'this process'
        elif name == 'ctypes.dlsym':
            kind, target = name, str(args[1]) if len(args) > 1 else 'symbol'
        elif name == 'ctypes.call_function':
            kind, target = name, 'foreign function'
        elif name == 'cpython.PyInterpreterState_New':
            kind, target = 'subinterpreter', name
        else:
            kind, target = 'process', program(name, args)
        self.record(kind, target)
        raise DeviceBoundaryError(f'The synthetic wall refused {kind} to {target}.')

    def refusal(self, kind, name):
        """A recording refusal that stands in for an unaudited launcher."""
        def refuse(*args, **kwargs):
            target = program('subprocess.Popen', (None, args[0])) if kind == 'process' and args else name
            self.record(kind, target)
            raise DeviceBoundaryError(f'The synthetic wall refused {kind} to {target}.')
        return refuse


def install_boundary(log, paired_port=None):
    """Refuse device, service and process access for the rest of this process. It cannot be removed.

    paired_port, from a hub-paired seed's marker, is the one loopback port the process may connect to.
    """
    boundary = Boundary(log, paired_port)
    sys.addaudithook(boundary.audit)
    for module_name, attribute, kind in UNAUDITED:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        setattr(module, attribute, boundary.refusal(kind, f'{module_name}.{attribute}'))
    return boundary


def outside_installation(directory):
    """The resolved directory, when it is neither the installation's state directory nor inside it."""
    directory = Path(directory).resolve()
    installed = configuration.data_dir().resolve()
    if directory == installed or installed in directory.parents:
        raise ValueError("Refusing the state directory: it is the installation's own state.")
    return directory


def owned_state(directory):
    """The resolved directory, when `seed` marked it and it is not the installation's own state."""
    directory = outside_installation(directory)
    if not (directory / MARKER).is_file():
        raise ValueError(f'Refusing the state directory: it has no {MARKER} from demo.py seed.')
    return directory


def marker(directory):
    """The seed's record in demo-run.json: its scenario and, for hub-paired, the paired Hub's port."""
    try:
        value = json.loads((Path(directory) / MARKER).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def registered(directory):
    return configuration.registered_devices(directory)


def paired_port(hub_feed):
    """The port of a paired Hub run's origin, exactly http://127.0.0.1:<port>/, never an installed service's port."""
    found = re.fullmatch(r'http://127\.0\.0\.1:([1-9][0-9]{0,4})/', hub_feed) if isinstance(hub_feed, str) else None
    if not found or int(found[1]) > 65535:
        raise PairingError("hub-feed must be the paired Hub run's origin, http://127.0.0.1:<port>/.")
    if int(found[1]) in INSTALLED_PORTS:
        raise PairingError("hub-feed names an installed service's port.")
    return int(found[1])


def paired_token(credentials, name):
    """One credential file the orchestrator wrote: private, and one token of the form the controller API mints."""
    try:
        token = shared_input.private_read(Path(credentials) / name, 128).decode('ascii').strip()
    except (shared_input.FeedError, UnicodeError):
        token = ''
    if not controller_server.TOKEN.fullmatch(token):
        raise PairingError(f'hub-paired needs a private {name} file in the run directory.')
    return token


def pair(directory, port, credentials, controller_token):
    """Make a seeded run a consumer of the paired Hub run.

    The controller API gets the Lines identity the orchestrator expects and accepts the Hub's
    credential, stored as the controller stores every credential, by its digest. Shared input
    follows the Hub's feed, whose token file stays in the run directory. A cutover's `shared-select`
    reads the feed before switching; this seed cannot, because its boundary allows no connection
    and the Hub may accept the feed credential only after this seed. The Poller checks every
    envelope as that preflight does, and a paired run has no legacy tasks to set aside.
    """
    controller_server.configure(directory, CONTROLLER['controllerId'], CONTROLLER['deviceId'], CONTROLLER['sourceId'])
    controller_server.register(directory, HUB_PRINCIPAL, ['read', 'control'], controller_token)
    shared_source.configure(directory, {
        'version': 1, 'ownerId': PAIRED_OWNER, 'consumerId': PAIRED_CONSUMER,
        'endpoint': f'http://127.0.0.1:{port}/api/monitor/v1', 'tokenFile': str(credentials / FEED_TOKEN),
        'clearOnNewTurn': True, 'qualifiedSources': [PAIRED_SOURCE], 'bindings': []})
    with contextlib.closing(database.connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        shared_input.save_legacy_tasks(db, [])
        db.execute("UPDATE shared_input SET source='shared',generation=generation+1,envelope=NULL,connection='unavailable',error=NULL WHERE id=1")
        store.mark_dirty(db)


def worker_stand_in(directory, now=time.time, request=refuse_light_request, contacts_device=False):
    """Stand in for the light workers: apply edits and allocation for every registered device, without any device.

    contacts_device makes a known-wrong stand-in that also tries to send an effect to each device,
    as a worker would; the request fails and the stand-in carries on.
    """
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
        for target in targets if contacts_device else ():
            try:
                request(target, 'PUT', '/effects', {'write': {'command': 'display'}})
            except OSError:
                pass
    return update


def seed(directory, scenario='reference', now=time.time, hub_feed=None, credentials=None):
    """Write a scenario's synthetic installation into an empty state directory and run the worker stand-in once.

    hub-paired also needs hub_feed, the paired Hub run's origin, and credentials, the run directory
    holding the two credential files. Every refusal happens before anything is written.
    """
    directory = Path(directory)
    if scenario not in SCENARIOS:
        raise ValueError(f'Unknown scenario {scenario!r}. Choose one of: {", ".join(SCENARIOS)}.')
    outside_installation(directory)
    if any(directory.iterdir()):
        raise ValueError('Seed an empty state directory. A run resets its state by emptying it first.')
    definition = SCENARIOS[scenario]
    paired = definition.get('paired', False)
    if paired:
        if credentials is None:
            raise PairingError('hub-paired needs the run directory that holds its credential files.')
        port = paired_port(hub_feed)
        credentials = Path(credentials).resolve()
        paired_token(credentials, FEED_TOKEN)  # Checked here; the Poller reads it again for every request.
        controller_token = paired_token(credentials, CONTROLLER_TOKEN)
    elif hub_feed is not None or credentials is not None:
        raise PairingError('Only hub-paired takes a Hub origin and credential files.')
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
        # A paired run's projects, like its tasks, come from the Hub.
        database.seed_synthetic(db, [] if paired else PROJECTS, [
            {'id': f'task-{i}', 'title': title, 'project': project, 'status': status, 'since': now()-90-i*61}
            for i, (title, project, status) in enumerate(tasks)])
        if tasks:
            db.executemany('INSERT INTO waits (session,turn,key,kind,tool) VALUES (?,?,?,?,?)', WAITS)
    worker_stand_in(directory, now)(directory)
    if paired:
        pair(directory, port, credentials, controller_token)
    jsonfile.write_json(directory / MARKER, {'scenario': scenario, 'seededBy': 'scripts/demo.py seed',
                                             **({'pairedPort': port, 'hubFeed': hub_feed} if paired else {})})


def prepare(directory, now=time.time):
    """Seed the reference scenario; return the Lines configuration and the worker stand-in."""
    seed(directory, 'reference', now)
    return configuration.load_config(directory, request=refuse_light_request), worker_stand_in(directory, now)


def poll_installed_hub(directory):
    """The known-wrong feed: one poll of the installed Hub's port through the real shared-input transport.

    The boundary refuses the connection before any byte is sent, so the poll fails as an unreachable feed.
    """
    config = dict(shared_source.source_config(directory)['config'], endpoint='http://127.0.0.1:8788/api/monitor/v1')
    try:
        shared_input.fetch_snapshot(config)
    except shared_input.FeedError:
        pass


def drive(directory, transition, now=time.time, request=refuse_light_request):
    """Apply a named transition's hook events through the actual hook handler, then the worker stand-in.

    A hub-paired run takes only its own defect transitions: the Hub owns its task state.
    """
    if transition not in TRANSITIONS:
        raise ValueError(f'Unknown transition {transition!r}. Choose one of: {", ".join(TRANSITIONS)}.')
    directory = owned_state(directory)
    definition = TRANSITIONS[transition]
    paired = marker(directory).get('scenario') == HUB_PAIRED
    if definition.get('paired', False) != paired:
        raise ValueError('The Hub owns task state in hub-paired; drive task events through the Hub.' if paired
                         else f'{transition} applies only to a hub-paired run.')
    update = worker_stand_in(directory, now, request, definition.get('contacts_device', False))
    if definition.get('polls_installed_hub'):
        poll_installed_hub(directory)
    events = definition['events']
    for item in events:
        bridge.handle_event(directory, dict(item), launch=update, now=now)
    if paired and definition.get('contacts_device'):
        update(directory)
    sessions = sorted({item['session_id'] for item in events})
    statuses = {}
    if sessions:
        with contextlib.closing(sqlite3.connect(directory / 'status.sqlite')) as db:
            statuses = dict(db.execute(f'SELECT id,status FROM sessions WHERE id IN ({",".join("?" * len(sessions))})', sessions))
    return {'transition': transition, 'tasks': statuses}


class PairedWriter:
    """The worker stand-in of a hub-paired run.

    About once per second, and whenever the map or the controller API wakes it, it runs one pass:
    the real shared-input Poller, at most one feed request a second, then for every device the
    worker's edits and allocation, with the Lines' integration settings queue first. It never
    renders or sends: every light request stays refused.
    """

    def __init__(self, directory, now=time.time, request=refuse_light_request):
        self.directory, self.now = directory, now
        self.targets = [configuration.load_config(directory, device, request=request) for device in registered(directory)]
        self.poller = shared_source.Poller(directory)
        self.woken = threading.Event()
        self.lock = threading.Lock()

    def wake(self, directory=None):
        """The launch seam: a pass runs promptly, never in the caller's thread."""
        self.woken.set()

    def run_pass(self):
        with self.lock:
            self.poller.tick(self.now())
            instant = self.now()
            with contextlib.closing(database.connect_state(self.directory)) as db, db:
                db.execute('BEGIN IMMEDIATE')
                for target in self.targets:
                    device = devices.device_of(target)
                    bridge.prune_comets(db, instant, store.control_state(db, device)['mode'], device)
                    if device == devices.DEFAULT:
                        integration_api.process(db, target, now=instant)
                    wall.apply_pending(db, device)
                    bridge.dashboard(db, target, instant)
                    store.mark_applied(db, store.control_state(db, device)['revision'], device)

    def start(self):
        def loop():
            while True:
                self.woken.wait(1)
                self.woken.clear()
                try:
                    self.run_pass()
                except Exception as error:
                    # A failed pass, such as one that met a busy database, is retried by the next.
                    print(f'paired writer: pass failed ({type(error).__name__})', file=sys.stderr, flush=True)
        threading.Thread(target=loop, name='paired-writer', daemon=True).start()


def free_port():
    """A loopback port the kernel reports free that no installed service uses.

    The kernel's ephemeral range includes installed ports such as 41230 and 41231. Another process
    can still take the port before the listener binds it; that start then fails as a port in use.
    """
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        if port not in INSTALLED_PORTS:
            return port


# Set when the controller listener stops after it was announced; the run then exits with status 1.
CONTROLLER_STOPPED = threading.Event()


def serve_controller(directory, port, launch):
    """Start the real controller API listener in a thread; return its origin once it is bound.

    Port 0 takes a free port that no installed service uses. A standalone scenario relaunched after
    pairing keeps the recorded endpoint, so the listener runs with the controller identity but no
    accepted credential: every Hub call is unauthenticated. If the listener stops after it was
    announced, the run prints one fixed line and ends, so the unit fails visibly.
    """
    controller_server.configure(directory, CONTROLLER['controllerId'], CONTROLLER['deviceId'], CONTROLLER['sourceId'])
    bound = queue.Queue()
    announced = threading.Event()

    def run():
        ended = None
        try:
            controller_server.serve(directory, port or free_port(), launch, ready=lambda value: (announced.set(), bound.put(value)))
        except BaseException as error:
            if not announced.is_set():
                bound.put(error)
                return
            ended = type(error).__name__
        print(f'controller listener stopped{f" ({ended})" if ended else ""}', file=sys.stderr, flush=True)
        CONTROLLER_STOPPED.set()
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=run, name='controller', daemon=True).start()
    result = bound.get(timeout=30)
    if isinstance(result, BaseException):
        raise result
    return f'http://127.0.0.1:{result}/'


def verification_state(directory):
    """The run's scripted read for Hub #495's orchestrator: feed freshness and the integration settings applied.

    `feed` is the local shared-input inspection: `connection` is current only while the last
    accepted envelope is at most 4 s old. `ownerId` is the owner of the last accepted envelope,
    null before the first, never the configured owner. `integration` counts the Lines'
    integration requests: `applied` by the stand-in writer, `queued` not yet applied, `failed`
    completed otherwise. The ledger keeps the last 256 completed requests. It never includes a
    token or a token path.
    """
    view = shared_input.inspect(directory)
    counts = {'applied': 0, 'queued': 0, 'failed': 0}
    with contextlib.closing(sqlite3.connect((directory / 'status.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        for phase, receipt in db.execute('SELECT phase,receipt FROM integration_requests'):
            key = 'queued' if phase != 'done' else 'applied' if json.loads(receipt).get('outcome') == 'applied' else 'failed'
            counts[key] += 1
        envelope = db.execute('SELECT envelope FROM shared_input WHERE id=1').fetchone()[0]
    feed = {key: view.get(key) for key in ('source', 'connection', 'revision', 'receivedAt', 'error')}
    feed['ownerId'] = shared_input.decode(envelope)['ownerId'] if envelope else None
    return {'apiVersion': 'wall-verify/1', 'scenario': marker(directory).get('scenario'), 'feed': feed, 'integration': counts}


# The page's one link out of the run: the header's B.U.N.N.Y. link to the installed Hub dashboard (#191).
INSTALLED_HUB_LINK = b'href="http://127.0.0.1:8788/"'


def paired_page(page, hub_feed):
    """The served page with its B.U.N.N.Y. link pointed at the paired Hub run's origin, or None.

    A hub-paired preview must not lead to an installed service (Hub #495). bridge/wall.html is
    unchanged; only a paired run's server substitutes the link target. It returns None unless the
    page holds the installed link exactly once, so a changed page fails loudly instead of serving
    the installed link.
    """
    if page.count(INSTALLED_HUB_LINK) != 1:
        return None
    return page.replace(INSTALLED_HUB_LINK, b'href="' + hub_feed.encode('ascii') + b'"')


def verification_handler(app, token, instance, directory, hub_feed=None):
    """The wall server's own handler plus one read-only route, `GET /verify/state`, served only by runs.

    With hub_feed, a hub-paired run's origin from its seed, the page at `/` links B.U.N.N.Y. to it.
    """
    class Handler(wall_server.handler(app, token, instance)):
        def respond(self, code, data, kind='application/json'):
            if hub_feed is not None and kind == 'text/html' and urlsplit(self.path).path == '/':
                data = paired_page(data, hub_feed)
                if data is None:
                    return super().respond(503, {'error': 'The paired Hub link could not be set.'})
            return super().respond(code, data, kind)

        def do_GET(self):
            if urlsplit(self.path).path != '/verify/state':
                return super().do_GET()
            if not self.valid_host():
                return self.respond(403, {'error': 'Invalid host.'})
            try:
                return self.respond(200, verification_state(directory))
            except Exception:
                return self.respond(503, {'error': 'Verification state unavailable.'})
    return Handler


def serve(directory, boundary, port=0, now=time.time, controller_port=None):
    """Serve a seeded state directory on 127.0.0.1 until SIGTERM, starting as the installed map does.

    With controller_port, also serve the real controller API on that port, 0 letting the kernel
    choose, and announce it as the `controller` endpoint. A hub-paired run's worker stand-in is the
    PairedWriter; every other scenario keeps the one-pass stand-in.
    """
    directory = owned_state(directory)
    seeded = marker(directory)
    paired = seeded.get('scenario') == HUB_PAIRED
    hub_feed = seeded.get('hubFeed') if paired else None
    if paired and paired_port(hub_feed) != seeded.get('pairedPort'):
        raise PairingError("hub-feed must be the paired Hub run's origin, http://127.0.0.1:<port>/.")
    config = configuration.load_config(directory, request=boundary.light_request)
    wall_server.ensure_geometry(directory, config, request=boundary.light_request)
    writer = PairedWriter(directory, now, boundary.light_request) if paired else None
    launch = writer.wake if writer else worker_stand_in(directory, now, boundary.light_request)
    app = wall_server.App(directory, config, launch=launch, request=boundary.light_request)
    app.geometry_attempts = 1  # As wall_server.serve: startup used the first of the map's bounded layout reads.
    endpoints = {}
    if controller_port is not None:
        endpoints['controller'] = serve_controller(directory, controller_port, launch)
    if writer:
        writer.start()
    instance = secrets.token_hex(16)
    server = ThreadingHTTPServer(('127.0.0.1', port), verification_handler(app, secrets.token_hex(32), instance, directory, hub_feed))
    server.app = app

    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    # The installed map's receipt: a probe matches this instance against /health and the boundary against the scenario.
    jsonfile.write_json(directory / 'map-server.json', {'port': server.server_port, 'instance': instance,
                                                        'boundary': 'paired' if boundary.paired else 'refusing',
                                                        **({'pairedPort': boundary.paired} if boundary.paired else {})})
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'instance': instance,
                      **({'endpoints': endpoints} if endpoints else {})}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    if CONTROLLER_STOPPED.is_set():
        raise SystemExit(1)


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
    seeding.add_argument('--hub-feed', help="hub-paired: the paired Hub run's origin, http://127.0.0.1:<port>/.")
    seeding.add_argument('--credentials', type=Path, help=f'hub-paired: the run directory holding {FEED_TOKEN} and {CONTROLLER_TOKEN}.')
    serving.add_argument('--port', type=int, default=0, help='Port on 127.0.0.1; 0 picks a free one.')
    serving.add_argument('--controller-port', type=int, help='Also serve the controller API on this 127.0.0.1 port; 0 picks a free one.')
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
    try:
        (outside_installation if args.command == 'seed' else owned_state)(directory)
    except ValueError as error:
        parser.error(str(error))
    # A seed connects nowhere; serve and drive of a hub-paired run may reach its paired Hub's feed port.
    boundary = install_boundary(directory / BOUNDARY_LOG, None if args.command == 'seed' else marker(directory).get('pairedPort'))
    if args.command == 'seed':
        try:
            seed(directory, args.scenario, hub_feed=args.hub_feed, credentials=args.credentials)
        except PairingError as error:
            parser.error(str(error))
        print(json.dumps({'scenario': args.scenario}))
    elif args.command == 'drive':
        print(json.dumps(drive(directory, args.transition, request=boundary.light_request)))
    else:
        serve(directory, boundary, args.port, controller_port=args.controller_port)


if __name__ == '__main__':
    main()
