"""Local Codex lifecycle indicator. Python standard library only."""
import argparse
import base64
import contextlib
import getpass
import ipaddress
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import devices
import project_map as wall
import shared_input

EVENTS = ('UserPromptSubmit', 'PreToolUse', 'PermissionRequest',
          'PostToolUse', 'Stop', 'Interrupt', 'SessionEnd')
BASELINE = (25, 60, 255)
COLORS = {'working': (0, 255, 0), 'question': (255, 255, 0),
          'blocked': (255, 0, 0), 'unread': BASELINE}
PRIORITY = {'working': 1, 'question': 2, 'blocked': 3, 'unread': 0}
# The controller uses decisecond frames, so 20 ticks gives a two-second cycle.
PULSE_TICKS = 20
PULSE_SECONDS = PULSE_TICKS / 10
TRAVEL_SECONDS = PULSE_SECONDS * 0.4
MIN_BRIGHTNESS = 0.2
RADIATING_PULSES = 1
COMET_SECONDS = 2.0
COMET_TRAVEL = 1.4
COMET_TAIL = 0.6
READ_SETTLE_SECONDS = 5.0
# Another device's pass may hold the write lock for two 1.2-second requests.
WORKER_BUSY_SECONDS = 5.0
MARKER = 'nanoleaf-codex-status-v1'
INPUT_TOOLS = {'request_user_input', 'request_user_input_async', 'request_permissions'}


def windows_path(value):
    if value.startswith('/mnt/') and len(value) > 7 and value[6] == '/':
        return value[5].upper() + ':\\' + value[7:].replace('/', '\\')
    return value


def data_dir():
    adjacent = Path(__file__).resolve().parent
    if (adjacent / 'config.json').exists():
        return adjacent
    if os.name == 'nt':
        return Path(os.environ['LOCALAPPDATA']) / 'CodexNanoleaf'
    return Path.home() / '.local' / 'share' / 'codex-nanoleaf'


def light_request(config, method, endpoint='', payload=None):
    ip = ipaddress.ip_address(config['ip'])
    if ip.version != 4 or not ip.is_private:
        raise ValueError('Use a private IPv4 address for the lights.')
    token = config['token']
    if not token or not token.isalnum():
        raise ValueError('The token must contain only letters and numbers.')
    url = f'http://{ip}:16021/api/v1/{token}{endpoint}'
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method=method,
                                     headers={'Content-Type': 'application/json'})
    # Keep local-device traffic off configured HTTP proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=1.2) as response:
        data = response.read()
        return json.loads(data) if data else None


def pair_lines(panel_layout):
    """Pair the two collinear light zones of each NL59 Line, excluding connectors."""
    zones = [p for p in panel_layout['layout']['positionData'] if p['shapeType'] == 18]
    if not zones or len(zones) % 2:
        raise ValueError('Expected two light zones per Line.')
    nearest = {}
    by_id = {p['panelId']: p for p in zones}
    for a in zones:
        candidates = []
        angle = math.radians(a['o'])
        for other in zones:
            if a == other or (a['o'] - other['o']) % 180:
                continue
            dx, dy = other['x'] - a['x'], other['y'] - a['y']
            # Orientation zero follows the y axis in the controller's layout.
            if abs(dx * math.cos(angle) + dy * math.sin(angle)) < 3:
                candidates.append((math.hypot(dx, dy), other['panelId']))
        if not candidates:
            raise ValueError('Could not pair a Line zone.')
        nearest[a['panelId']] = min(candidates)[1]
    pairs = set()
    for first, second in nearest.items():
        if nearest.get(second) != first:
            raise ValueError('Line zone pairing is ambiguous.')
        pairs.add(tuple(sorted((first, second))))
    # Follow the installed orientation for a spatially ordered notification sweep.
    orientation = math.radians(panel_layout['globalOrientation']['value'])
    def location(pair):
        x = sum(by_id[p]['x'] for p in pair) / 2
        y = sum(by_id[p]['y'] for p in pair) / 2
        return (round(x * math.cos(orientation) - y * math.sin(orientation)),
                round(x * math.sin(orientation) + y * math.cos(orientation)))
    return [list(pair) for pair in sorted(pairs, key=location)]


def load_config(directory, device=devices.DEFAULT):
    """Configuration and layout for one registered device; the original Lines device by default."""
    config = json.loads((directory / 'config.json').read_text())
    registry = devices.registry(config)
    if device not in registry:
        raise ValueError('Unknown device.')
    entry = registry[device]
    layout_file = directory / 'layout.json'
    saved = json.loads(layout_file.read_text()) if layout_file.exists() else {}
    known = devices.layout_devices(saved)  # A malformed file is rejected and left in place.
    layout = known.get(device)
    if layout is None or any(element['position'] is None for element in layout['elements']):
        transport = {'ip': entry['ip'], 'token': devices.credential(config, entry)}
        panel_layout = light_request(transport, 'GET')['panelLayout']
    if entry['kind'] == 'panels' and (layout is None or any(element['position'] is None for element in layout['elements'])):
        # Reported triangles only; unsupported geometry fails before anything is saved.
        import panels
        layout = panels.read_layout(panel_layout)
        devices.save_device_layout(layout_file, device, layout, write_json)
    elif layout is None or any(element['position'] is None for element in layout['elements']):
        groups = [element['zones'] for element in layout['elements']] if layout else pair_lines(panel_layout)
        zones = {p['panelId']: p for p in panel_layout['layout']['positionData']}
        positions = [[sum(zones[p]['x'] for p in pair) / 2,
                      sum(zones[p]['y'] for p in pair) / 2] for pair in groups]
        layout = devices.lines_entry(groups, positions, layout)
        devices.save_device_layout(layout_file, device, layout, write_json)
    config.update(devices.projection(layout))
    config['device'] = device
    for key, value in (('ip', entry['ip']), ('token', devices.credential(config, entry))):
        if value is not None:
            config[key] = value
    groups = config['line_groups']
    ids = [p for pair in groups for p in pair]
    if (not groups or any(len(pair) != devices.KINDS[entry['kind']] for pair in groups) or
            len(ids) != len(set(ids)) or any(not isinstance(p, int) for p in ids)):
        raise ValueError('Invalid physical Line mapping.')
    if len(config.get('line_positions', ())) != len(groups):
        raise ValueError('Each Line needs a position for outward pulses.')
    return config


def pulse_amplitude(age):
    if age < 0:
        return 0.0
    phase = (age % PULSE_SECONDS) / PULSE_SECONDS
    if phase < 0.2:
        return phase / 0.2
    if phase < 0.3:
        return 1.0
    if phase < 0.5:
        return (0.5 - phase) / 0.2
    return 0.0


def travel_delays(config, source):
    positions = config['line_positions']
    distances = [math.dist(positions[source], target) for target in positions]
    maximum = max(distances) or 1.0
    return [distance / maximum * TRAVEL_SECONDS for distance in distances]


def pixel_color(snapshot, target, instant, delays, wave_cutoff=float('-inf')):
    candidates = []
    for source, activity in enumerate(snapshot):
        if activity is None:
            continue
        status, epoch = activity
        age = instant - epoch
        if source != target:
            if status == 'unread' or epoch <= wave_cutoff:
                continue
            age -= delays[source][target]
            if not 0 <= age < RADIATING_PULSES * PULSE_SECONDS:
                continue
        amplitude = pulse_amplitude(age)
        # An assigned Line keeps its status hue even between flashes. Other
        # Lines receive that hue only while the initial wave passes them.
        if source == target or amplitude > 0.001:
            candidates.append((PRIORITY[status], amplitude, status))
    if not candidates:
        return BASELINE
    _, amount, status = max(candidates)
    brightness = MIN_BRIGHTNESS + (1 - MIN_BRIGHTNESS) * amount
    return tuple(round(color * brightness) for color in COLORS[status])


def comet_color(config, snapshot, target, instant, delays, base):
    comet = config.get('_comet')
    if not comet or config.get('_mode', 'work') != 'work':
        return base
    cutoff = config.get('_wave_cutoff', float('-inf'))
    for source, activity in enumerate(snapshot):
        if not activity or activity[0] not in ('blocked', 'question'):
            continue
        if source == target:
            return base
        age = instant - activity[1] - delays[source][target]
        if activity[1] > cutoff and 0 <= age < PULSE_SECONDS and pulse_amplitude(age) > 0.001:
            return base
    positions = config['line_positions']
    distances = [math.dist(positions[comet['source']], point) for point in positions]
    arrival = COMET_TRAVEL * distances[target] / (max(distances) or 1.0)
    age = instant - comet['started'] - arrival
    if not 0 <= age < COMET_TAIL:
        return base
    blue = min(1.0, max(0.0, (age - 0.1) / 0.1))
    color = [255 + (channel - 255) * blue for channel in BASELINE]
    alpha = min(1.0, (COMET_TAIL - age) / 0.4)
    return tuple(round(background * (1 - alpha) + foreground * alpha)
                 for background, foreground in zip(base, color))


def introduction_ends(snapshot):
    return max((epoch + (RADIATING_PULSES - 0.5) * PULSE_SECONDS + TRAVEL_SECONDS
                for activity in snapshot if activity and activity[0] != 'unread' for _, epoch in [activity]), default=0)


def unread_reader(config):
    """Read the desktop's unread indicator, never write to its saved state."""
    if config.get('desktop_state_path'):
        path = Path(config['desktop_state_path'])
    elif os.name == 'nt':
        path = Path(os.environ.get('USERPROFILE', str(Path.home()))) / '.codex' / '.codex-global-state.json'
    else:
        path = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / '.codex-global-state.json'
    stamp, cached = None, None
    def read():
        nonlocal stamp, cached
        try:
            stat = path.stat()
            current = (stat.st_mtime_ns, stat.st_size)
            if current != stamp:
                state = json.loads(path.read_text(encoding='utf-8-sig'))
                if 'electron-thread-read-state-v1' in state:
                    marker = state['electron-thread-read-state-v1']
                    if (not isinstance(marker, dict) or type(marker.get('version')) is not int
                            or marker['version'] != 1 or not isinstance(marker.get('unreadByIdentity'), dict)):
                        return None
                    ids = []
                    for host in marker['unreadByIdentity'].values():
                        if not isinstance(host, dict):
                            return None
                        for unread in host.values():
                            if not isinstance(unread, list) or any(not isinstance(i, str) or not i for i in unread):
                                return None
                            ids.extend(unread)
                else:
                    # Older Desktop releases have only this unversioned local bucket.
                    ids = state['electron-persisted-atom-state']['unread-thread-ids-by-host-v1']['local']
                if not isinstance(ids, list) or any(not isinstance(i, str) or not i for i in ids):
                    return None
                cached, stamp = set(ids), current
            return cached
        except (OSError, ValueError, KeyError, TypeError):
            return None  # Missing or partial state is not evidence that a task was read.
    return read


def reconcile_read_state(db, unread, instant):
    if unread is None:
        return
    # Rollback retains unread tasks but drops their old completion receipts.
    # Rebuild only missing receipts, preserving completion time and settle delay.
    db.execute("INSERT OR IGNORE INTO receipts SELECT id,turn,updated,0 FROM sessions WHERE status='unread'")
    # Include completed tasks already known to the integration when it upgrades.
    for session, turn, completed in db.execute("SELECT id,turn,updated FROM sessions WHERE status='ended'").fetchall():
        if session in unread:
            db.execute("UPDATE sessions SET status='unread' WHERE id=?", (session,))
            db.execute('INSERT OR REPLACE INTO receipts VALUES (?, ?, ?, 1)', (session, turn, completed))
            db.execute("INSERT OR REPLACE INTO activity VALUES (?, ?, 'unread', ?)", (session, turn, instant))
            mark_dirty(db)
    for session, turn, completed, observed in db.execute('SELECT * FROM receipts').fetchall():
        if session in unread:
            if not observed:
                db.execute('UPDATE receipts SET observed=1 WHERE session=?', (session,))
        elif observed or instant >= completed + READ_SETTLE_SECONDS:
            # The app can publish its unread flag after Stop. Allow that write
            # to settle before interpreting an absent flag as an already-viewed task.
            db.execute("UPDATE sessions SET status='ended' WHERE id=? AND turn=? AND status='unread'", (session, turn))
            db.execute('DELETE FROM receipts WHERE session=?', (session,))
            db.execute("DELETE FROM activity WHERE session=? AND turn=? AND status='unread'", (session, turn))
            mark_dirty(db)


def zone_color(config, snapshot, index, half, instant, delays):
    quiet = config.get('_mode') == 'quiet'
    suppressed = set(config.get('_steady_slots', ())) | set(config.get('_wave_suppressed_slots', ()))
    snapshot = [None if i in suppressed and i != index else item for i,item in enumerate(snapshot)]
    activity = snapshot[index]
    steady = index in config.get('_steady_slots', ())
    base = (COLORS[activity[0]] if activity else BASELINE) if quiet or steady else pixel_color(
        snapshot, index, instant, delays, config.get('_wave_cutoff', float('-inf')))
    signature = None
    # Project/status halves need a two-zone Line; one-zone triangles always show status.
    if config.get('_style') == 'project' and len(config['line_groups'][index]) == 2:
        signatures = config.get('_signatures', [])
        if index < len(signatures):
            color, side = signatures[index]
            if half == side: signature = tuple(color) if color is not None else BASELINE
    if signature is not None:
        base = signature
        if not quiet and not steady and config.get('_coverage') == 'whole':
            candidates = []
            for source, item in enumerate(snapshot):
                if not item or item[0] == 'unread' or item[1] <= config.get('_wave_cutoff', float('-inf')): continue
                age = instant - item[1] - (delays[source][index] if source != index else 0)
                if not 0 <= age < PULSE_SECONDS: continue
                amount = pulse_amplitude(age)
                if amount <= .001: continue
                if activity and PRIORITY[activity[0]] > PRIORITY[item[0]]: continue
                candidates.append((PRIORITY[item[0]], amount, item[0]))
            if candidates:
                _, amount, status = max(candidates)
                base = tuple(round(a*(1-amount)+b*amount) for a,b in zip(signature,COLORS[status]))
    if not quiet and not steady and (signature is None or config.get('_coverage') == 'whole'):
        base = comet_color(config, snapshot, index, instant, delays, base)
    locate = config.get('_locate')
    if locate and locate['source'] == index and 0 <= instant - locate['started'] < 1:
        return (255,255,255)
    return base


def effect_payload(config, snapshot, instant, loop):
    groups = config['line_groups']
    if len(snapshot) != len(groups):
        raise ValueError('Task display does not match the physical Lines.')
    quiet = config.get('_mode') == 'quiet'
    comet = config.get('_comet') if config.get('_mode', 'work') == 'work' else None
    locate = config.get('_locate')
    animated = bool(any(snapshot) or comet or locate) and not quiet
    delays = [travel_delays(config, source) for source in range(len(groups))]
    data = [sum(len(zones) for zones in groups)]
    for index, pair in enumerate(groups):
        ticks = [1] + list(range(2, PULSE_TICKS, 2)) + [PULSE_TICKS] if animated else [1]
        if comet: ticks = list(range(1, PULSE_TICKS + 1))
        for half, panel in enumerate(pair):
            frames, previous = [], 0
            for tick in ticks:
                instant_at = instant + tick / 10
                color = zone_color(config, snapshot, index, half, instant_at, delays)
                frames.append((*color, 0, tick - previous))
                previous = tick
            data.extend([panel, len(frames)])
            for step in frames: data.extend(step)
    write = {'command': 'display', 'version': '2.0',
             'animType': 'custom' if animated else 'static',
             'animData': ' '.join(map(str, data)), 'loop': bool(loop and animated and not comet and not locate),
             'colorType': 'HSB', 'palette': [{'hue': 0, 'saturation': 0, 'brightness': 100}]}
    if config.get('kind', 'lines') == 'lines':
        # Lines address their two logical zones; the Light Panels API defines no such flag.
        write['logicalPanelsEnabled'] = True
    return {'write': write}


def render(config, snapshot, instant, loop):
    request = config.get('_controller_request', light_request)
    now = config.get('_now', time.time)
    effect = effect_payload(config, snapshot, instant, loop)
    send_started = now()
    request(config, 'PUT', '/effects', effect)
    effect_accepted = now()
    brightness = indicator_brightness(config)
    request(config, 'PUT', '/state', {'on': {'value': True},
                                           'brightness': {'value': brightness, 'duration': 0}})
    return {'apiVersion': '1.0', 'deviceId': devices.device_of(config),
            'lineGroups': [list(pair) for pair in config['line_groups']],
            'mode': config.get('_mode', 'work'), 'brightness': brightness,
            'loop': effect['write']['loop'], 'effect': effect,
            'animationEpochMs': round(instant * 1000),
            'sendStartedAtMs': round(send_started * 1000),
            'effectAcceptedAtMs': round(effect_accepted * 1000),
            'acceptedAtMs': round(now() * 1000)}


def indicator_brightness(config):
    """A native brightness override governs every worker write until the next explicit mode command."""
    override = config.get('_brightness')
    if override is not None:
        return override
    return 10 if config.get('_mode') == 'quiet' else 30


class SceneRestorer:
    """Remember named scenes before takeover, and restore after the last indicator."""
    def __init__(self, directory, config, request=None, draw=None):
        self.path = directory / devices.scene_file(devices.device_of(config))
        self.config = config
        self.request = request or light_request
        self.draw = draw or render
        # quiet_scene names the playing scene whose brightness the bridge changed while idle
        # (Quiet's 10% or a native override); quiet_brightness is the level it wrote.
        self.state = {'version': 1, 'scene': None, 'owned': False, 'quiet_scene': None, 'quiet_brightness': None}
        if self.path.exists():
            saved = json.loads(self.path.read_text(encoding='utf-8-sig'))
            scene = saved.get('scene')
            level = saved.get('quiet_brightness')
            if (saved.get('version') != 1 or type(saved.get('owned')) is not bool or
                    (scene is not None and not self.valid_scene(scene)) or
                    (level is not None and (type(level) is not int or not 0 <= level <= 100))):
                raise ValueError('Invalid saved scene state.')
            if 'quiet_brightness' not in saved and saved.get('quiet_scene') is not None:
                saved['quiet_brightness'] = 10  # The only level earlier versions wrote.
            self.state.update({key: saved[key] for key in self.state if key in saved})
        self.selected = None
        self.available = set()
        self.names = []

    @staticmethod
    def valid_scene(scene):
        return (isinstance(scene, dict) and isinstance(scene.get('name'), str) and
                bool(scene['name']) and type(scene.get('brightness')) is int and
                0 <= scene['brightness'] <= 100)

    def save(self, **changes):
        updated = {**self.state, **changes}
        if updated != self.state:
            write_json(self.path, updated)
            self.state = updated

    def observe(self):
        effects = self.request(self.config, 'GET', '/effects')
        names = effects.get('effectsList')
        selected = effects.get('select')
        if (not isinstance(names, list) or any(not isinstance(name, str) for name in names)
                or not isinstance(selected, str)):
            raise ValueError('Invalid scene list from controller.')
        self.available = set(names)
        self.names = list(names)
        self.selected = selected
        if selected in self.available:
            state = self.request(self.config, 'GET', '/state')
            scene = {'name': selected, 'brightness': state['brightness']['value']}
            if not self.valid_scene(scene):
                raise ValueError('Invalid scene brightness from controller.')
            # Save before taking over. Temporary *Dynamic* task effects are
            # absent from the saved scene list and can never replace this target.
            # A level the bridge itself wrote onto this scene is not a new preference.
            if not (selected == self.state['quiet_scene'] and scene['brightness'] == self.state['quiet_brightness']):
                self.save(scene=scene, quiet_scene=None, quiet_brightness=None)
            return True
        return False

    def wrote(self, name, level):
        """Record a one-shot native brightness written onto the playing saved scene."""
        if name in self.available:
            self.save(quiet_scene=name, quiet_brightness=level)

    def send(self, config, snapshot, instant, loop):
        if any(snapshot) or config.get('_comet') or config.get('_locate'):
            self.save(owned=True)
            output = self.draw(config, snapshot, instant, loop)
            self.save(quiet_scene=None, quiet_brightness=None)
            self.selected = '*Dynamic*'
            return output
        quiet = config.get('_mode') == 'quiet'
        override = config.get('_brightness')
        if self.selected == '*ExtControl*' and config.get('_mode') == 'free':
            self.save(owned=False, quiet_scene=None, quiet_brightness=None)
            return
        if self.selected in self.available:
            # A manually chosen scene is already playing. Leave its animation
            # running instead of restarting it on every idle hook event.
            if quiet:
                level = 10 if override is None else override
                if self.state['quiet_scene'] != self.selected or self.state['quiet_brightness'] != level:
                    self.save(quiet_scene=self.selected, quiet_brightness=level, owned=True)
                    self.request(config, 'PUT', '/state', {'brightness': {'value': level, 'duration': 0}})
            elif self.state['quiet_scene'] == self.selected:
                if override is None:
                    # The mode policy applies again: the remembered brightness returns.
                    self.request(config, 'PUT', '/state', {'brightness': {
                        'value': self.state['scene']['brightness'], 'duration': 0}})
                    self.save(quiet_scene=None, quiet_brightness=None)
                elif self.state['quiet_brightness'] != override:
                    self.request(config, 'PUT', '/state', {'brightness': {'value': override, 'duration': 0}})
                    self.save(quiet_brightness=override)
            self.save(owned=quiet)
            return
        if not self.state['owned'] and not quiet:
            return
        scene = self.state['scene']
        if scene and scene['name'] in self.available:
            # Restore brightness first. If selection succeeds but its response
            # is lost, the next observation still sees the correct saved values.
            level = override if override is not None else (10 if quiet else scene['brightness'])
            changed = quiet or override is not None
            self.save(quiet_scene=scene['name'] if changed else None, quiet_brightness=level if changed else None)
            self.request(config, 'PUT', '/state', {'on': {'value': True},
                         'brightness': {'value': level, 'duration': 0}})
            self.request(config, 'PUT', '/effects', {'select': scene['name']})
            self.selected = scene['name']
        else:
            # The first scene has not been chosen yet, or it was deleted.
            output = self.draw(config, snapshot, instant, loop)
            self.selected = '*Static*'
            self.save(owned=quiet)
            return output
        self.save(owned=quiet)


def connect_state(directory, timeout=2.5):
    db = sqlite3.connect(directory / 'status.sqlite', timeout=timeout)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            wall.init(db)
            shared_input.init(db)
            import integration_api
            integration_api.init(db)
            db.execute('CREATE TABLE IF NOT EXISTS sessions '
                       '(id TEXT PRIMARY KEY, turn TEXT, status TEXT, updated REAL)')
            devices.create(db, 'slots')
            db.execute('CREATE TABLE IF NOT EXISTS waits '
                       '(session TEXT, turn TEXT, key TEXT, kind TEXT, tool TEXT, '
                       'PRIMARY KEY(session, turn, key))')
            db.execute('CREATE TABLE IF NOT EXISTS activity '
                       '(session TEXT PRIMARY KEY, turn TEXT, status TEXT, started REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS receipts '
                       '(session TEXT PRIMARY KEY, turn TEXT, completed REAL, observed INTEGER)')
            devices.create(db, 'display_v3')
            devices.create(db, 'comets')
            db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)')
            # Existing Linux state gains its device key in place; a repeat is a no-op.
            devices.migrate(db)
            wall.seed(db)
            if db.execute("SELECT value FROM meta WHERE key='model_version'").fetchone() != ('4',):
                # This is only the integration's own database. Replace old lighting
                # notifications and initialize the outward pulse for current work.
                for table in ('signals', 'notifications'):
                    if db.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone():
                        db.execute('DELETE FROM ' + table)
                db.execute("UPDATE sessions SET status='blocked' WHERE status='approval'")
                db.execute('INSERT OR REPLACE INTO activity '
                           "SELECT id,turn,status,? FROM sessions WHERE status IN ('working','question','blocked','unread')",
                           (time.time(),))
                db.execute("INSERT OR REPLACE INTO meta VALUES ('model_version','4')")
    except BaseException:
        db.close()
        raise
    return db


MODES = ('work', 'free', 'quiet')


def control_state(db, device=devices.DEFAULT):
    meta = dict(db.execute('SELECT key,value FROM meta'))
    key = lambda name: devices.meta_key(name, device)
    return {'mode': meta.get(key('mode'), 'work'),
            'revision': int(meta.get(key('mode_revision'), '0')),
            'applied': int(meta.get(key('mode_applied'), '0')),
            'wave_cutoff': float(meta.get(key('wave_cutoff'), '-inf')),
            'error': meta.get(key('control_error'))}


def change_mode(db, mode, instant, notify=True, device=devices.DEFAULT):
    import controller_state
    key = lambda name: devices.meta_key(name, device)
    state = control_state(db, device)
    # The configured controller identity is the original device; other devices stay local.
    notify = notify and device == devices.DEFAULT
    # Any explicit mode command, including the same mode, ends native power/brightness overrides.
    overridden = device == devices.DEFAULT and any(value is not None for value in controller_state.overrides(db).values())
    if overridden:
        db.execute("DELETE FROM meta WHERE key IN ('controller_power', 'controller_brightness')")
    if state['mode'] == mode and overridden:
        db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)', (key('mode_revision'), str(state['revision'] + 1)))
        mark_dirty(db)
        if notify:
            controller_state.changed(db, mode=True)
        return True
    if state['mode'] != mode:
        values = {key('mode'): mode, key('mode_revision'): str(state['revision'] + 1)}
        if mode == 'work':
            values[key('wave_cutoff')] = str(instant)
        db.executemany('INSERT OR REPLACE INTO meta VALUES (?, ?)', values.items())
        db.execute('DELETE FROM meta WHERE key=?', (key('preview'),))
        db.execute('DELETE FROM comets WHERE device=?', (device,))
        db.execute('DELETE FROM locate WHERE device=?', (device,))
        mark_dirty(db)
        if notify:
            controller_state.changed(db, mode=True)
        return True
    if notify:
        controller_state.changed(db, mode=True)
    return state['revision'] != state['applied'] or bool(state['error'])


def set_mode(directory, mode, launch=None, now=time.time, device=devices.DEFAULT):
    if mode not in MODES:
        raise ValueError('Unknown lighting mode.')
    with contextlib.closing(connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        needed = change_mode(db, mode, now(), device=device)
    if needed:
        (launch or launch_worker)(directory)


def get_status(directory, device=devices.DEFAULT):
    # Tray polling never initializes or migrates a database.
    with contextlib.closing(sqlite3.connect(
            (directory / 'status.sqlite').resolve().as_uri() + '?mode=ro', uri=True, timeout=0.2)) as db:
        state = control_state(db, device)
    return {'mode': state['mode'], 'pending': state['revision'] != state['applied'],
            'error': state['error']}


def mark_dirty(db):
    db.execute("INSERT INTO meta VALUES ('event_revision', '1') ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1")
    db.execute("INSERT OR REPLACE INTO meta VALUES ('dirty', '1')")


def transition(db, event, now, targets=(devices.DEFAULT,)):
    """Separate a question during work from a request that blocks progress."""
    name, session = event.get('hook_event_name'), event.get('session_id')
    if name not in EVENTS or not isinstance(session, str) or not session:
        return False
    old = db.execute('SELECT turn, status FROM sessions WHERE id=?', (session,)).fetchone()
    if name == 'SessionEnd':
        if old and old[1] == 'unread':
            return False  # Closing a runtime is not a read receipt.
        for table in ('waits', 'slots', 'activity', 'receipts'):
            db.execute('DELETE FROM ' + table + ' WHERE session=?', (session,))
        db.execute('DELETE FROM sessions WHERE id=?', (session,))
        return bool(old)
    turn = event.get('turn_id')
    if not isinstance(turn, str) or not turn:
        return False
    if old and old[0] != turn and name != 'UserPromptSubmit':
        return False
    if old and old[1] in ('ended', 'idle', 'unread') and name not in ('UserPromptSubmit', 'Interrupt'):
        return False
    tool = str(event.get('tool_name') or '')
    short_tool = tool.rsplit('.', 1)[-1]
    call_id = str(event.get('tool_use_id') or tool)
    if name in ('UserPromptSubmit', 'Interrupt'):
        db.execute('DELETE FROM comets WHERE session=?', (session,))
        db.execute('DELETE FROM receipts WHERE session=?', (session,))
    if name == 'UserPromptSubmit':
        db.execute('DELETE FROM waits WHERE session=?', (session,))
        db.execute('DELETE FROM receipts WHERE session=?', (session,))
        status = 'working'
    elif name == 'Interrupt':
        db.execute('DELETE FROM waits WHERE session=?', (session,))
        status = 'idle'
    else:
        if name == 'PermissionRequest':
            db.execute('INSERT OR REPLACE INTO waits VALUES (?, ?, ?, ?, ?)',
                       (session, turn, 'permission:' + tool, 'permission', tool))
        elif name == 'PreToolUse' and short_tool in INPUT_TOOLS:
            kind = 'async' if short_tool.endswith('_async') else 'input'
            db.execute('INSERT OR REPLACE INTO waits VALUES (?, ?, ?, ?, ?)',
                       (session, turn, 'input:' + call_id, kind, tool))
        elif name == 'PostToolUse':
            db.execute("DELETE FROM waits WHERE session=? AND turn=? AND "
                       "((kind='permission' AND tool=?) OR (kind='input' AND key=?))",
                       (session, turn, tool, 'input:' + call_id))
        elif name == 'Stop':
            db.execute("DELETE FROM waits WHERE session=? AND kind NOT IN ('async','async_stopped')", (session,))
            db.execute("UPDATE waits SET kind='async_stopped' WHERE session=? AND kind='async'", (session,))
        kinds = {row[0] for row in db.execute('SELECT kind FROM waits WHERE session=?', (session,))}
        if kinds - {'async'}:
            status = 'blocked'
        elif kinds:
            status = 'question'
        else:
            status = 'unread' if name == 'Stop' else 'working'
            if name == 'Stop':
                db.execute('INSERT OR REPLACE INTO receipts VALUES (?, ?, ?, 0)', (session, turn, now))
    db.execute('INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?)',
               (session, turn, status, now))
    changed = old != (turn, status)
    if changed:
        if status == 'unread' and name == 'Stop':
            # Completion evidence is shared; each device in Work queues its own comet.
            for device in targets:
                if control_state(db, device)['mode'] == 'work':
                    db.execute('INSERT OR IGNORE INTO comets (session, turn, queued, source, started, device) '
                               'VALUES (?, ?, ?, NULL, NULL, ?)', (session, turn, now, device))
        if status in COLORS:
            db.execute('INSERT OR REPLACE INTO activity VALUES (?, ?, ?, ?)',
                       (session, turn, status, now))
        else:
            db.execute('DELETE FROM activity WHERE session=?', (session,))
    return changed


def dashboard(db, config, instant):
    rows = db.execute("SELECT id,turn,status FROM sessions WHERE status IN ('working','question','blocked','unread') "
                      "ORDER BY CASE status WHEN 'blocked' THEN 0 WHEN 'question' THEN 1 ELSE 2 END, updated, id").fetchall()
    active = {row[0] for row in rows}
    db.execute('DELETE FROM slots WHERE session NOT IN (SELECT id FROM sessions)')
    count = len(config['line_groups'])
    reserved = {row[0] for row in db.execute('SELECT source FROM comets WHERE started IS NOT NULL AND device=?',
                                             (devices.device_of(config),))}
    assigned = wall.allocate(db, config, rows, reserved)
    epochs = {s: (turn, status, epoch) for s, turn, status, epoch in db.execute('SELECT * FROM activity')}
    snapshot = [None] * count
    for session, turn, status in rows:
        if session not in assigned or assigned[session] >= count:
            continue
        old = epochs.get(session)
        if not old or old[:2] != (turn, status):
            old = (turn, status, instant)
            db.execute('INSERT OR REPLACE INTO activity VALUES (?, ?, ?, ?)', (session, *old))
        snapshot[assigned[session]] = (status, old[2])
    return snapshot


def prune_comets(db, instant, mode, device=devices.DEFAULT):
    if mode != 'work':
        db.execute('DELETE FROM comets WHERE device=?', (device,))
        return
    db.execute('DELETE FROM comets WHERE device=? AND started IS NOT NULL AND started + ? <= ?',
               (device, COMET_SECONDS, instant))
    db.execute("DELETE FROM comets WHERE device=? AND started IS NULL AND NOT EXISTS "
               "(SELECT 1 FROM sessions s WHERE s.id=comets.session AND s.turn=comets.turn AND s.status='unread')",
               (device,))


def current_comet(db, instant, device=devices.DEFAULT):
    row = db.execute('SELECT source,started FROM comets WHERE started IS NOT NULL AND device=?', (device,)).fetchone()
    if not row:
        candidate = db.execute('SELECT c.session,s.slot FROM comets c JOIN slots s ON s.session=c.session AND s.device=c.device '
                               'WHERE c.device=? AND c.started IS NULL ORDER BY c.queued,c.rowid LIMIT 1', (device,)).fetchone()
        if candidate:
            session, source = candidate
            db.execute('UPDATE comets SET source=?,started=? WHERE session=? AND device=?', (source, instant, session, device))
            row = (source, instant)
    return dict(zip(('source', 'started'), row)) if row else None


def update_display(db, config, snapshot, instant, loop, send=None):
    device = devices.device_of(config)
    encoded = json.dumps([snapshot, config.get('_comet'), config.get('_locate'),
                          config.get('_style'), config.get('_coverage'), config.get('_signatures'),
                          config.get('_steady_slots'), config.get('_wave_suppressed_slots'), config.get('_wave_cutoff')])
    previous = db.execute('SELECT snapshot,looping FROM display_v3 WHERE device=?', (device,)).fetchone()
    if not loop or previous != (encoded, 1):
        output = (send or render)(config, snapshot, instant, loop)
        receipt_key = devices.meta_key('rendering_receipt', device)
        if isinstance(output, dict):
            db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)',
                       (receipt_key, json.dumps(output, separators=(',', ':'), allow_nan=False)))
        else:
            db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)',
                       (receipt_key, json.dumps({'apiVersion': '1.0', 'deviceId': device,
                                                 'outcome': 'unknown'}, separators=(',', ':'))))
        db.execute('INSERT OR REPLACE INTO display_v3 (snapshot, looping, rendered, device) VALUES (?, ?, ?, ?)',
                   (encoded, int(loop), instant, device))


def registered_devices(directory):
    """Registered device ids, the original Lines device first; an unreadable configuration means Lines only."""
    try:
        registry = devices.registry(json.loads((directory / 'config.json').read_text(encoding='utf-8-sig')))
    except (OSError, ValueError):
        return [devices.DEFAULT]
    return [devices.DEFAULT] + [device for device in registry if device != devices.DEFAULT]


def launch_worker(directory, device=None):
    """Wake one worker instance per registered device, or only the named device."""
    options = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
               'stderr': subprocess.DEVNULL, 'close_fds': True}
    if os.name == 'nt':
        options['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options['start_new_session'] = True
    for target in [device] if device else registered_devices(directory):
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker',
                          '--state-dir', str(directory.resolve()), '--device', target], **options)


def handle_event(directory, event, launch=None, now=time.time):
    targets = registered_devices(directory)
    with contextlib.closing(connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        instant = now()
        if shared_input.selected(db):
            return
        db.execute('DELETE FROM shared_stale WHERE session=?', (event.get('session_id'),))
        changed = transition(db, event, instant, targets)
        metadata_changed = wall.record_event(db, event, instant)
        if changed or metadata_changed:
            mark_dirty(db)
        needed = db.execute("SELECT 1 FROM meta WHERE key IN ('dirty','rendering','preview') "
                            "OR key LIKE 'rendering@%' OR key LIKE 'preview@%' LIMIT 1").fetchone()
    if needed:
        (launch or launch_worker)(directory)


def record_failure(directory, device=devices.DEFAULT):
    """Record a failed pass for this device only; False when even that cannot be written."""
    try:
        with contextlib.closing(connect_state(directory)) as db, db:
            db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)',
                       (devices.meta_key('control_error', device), 'Light update failed; retrying.'))
            mark_dirty(db)
        return True
    except Exception:
        return False


def play_preview(config, choice, send, sleep, now):
    config = dict(config, _comet=None, _locate=None)
    if choice == 'comet':
        cfg = dict(config, _comet={'source': len(config['line_groups']) // 2, 'started': now()})
        send(cfg, [None] * len(config['line_groups']), now(), False)
        sleep(COMET_SECONDS)
        return
    choices = tuple(COLORS) if choice == 'all' else (choice,)
    source = len(config['line_groups']) // 2
    for status in choices:
        epoch = now()
        snapshot = [None] * len(config['line_groups'])
        snapshot[source] = (status, epoch)
        for _ in range(RADIATING_PULSES):
            started = now()
            send(config, snapshot, started, False)
            sleep(max(0, started + PULSE_SECONDS - now()))
        send(config, snapshot, now(), True)
        sleep(PULSE_SECONDS)
    send(config, [None] * len(config['line_groups']), now(), True)
    sleep(2)


def run_worker(directory, send=None, sleep=time.sleep, now=time.time, read_unread=None,
               scene_factory=SceneRestorer, device=devices.DEFAULT, feed=None):
    # One locked instance per device. Only the original Lines instance polls the shared
    # feed and owns the protected controller's journal, controls, overrides and hold.
    primary = device == devices.DEFAULT
    key = lambda name: devices.meta_key(name, device)
    connect = lambda: connect_state(directory, WORKER_BUSY_SECONDS)
    with contextlib.closing(sqlite3.connect(directory / devices.lock_file(device), timeout=0)) as guard:
        try:
            guard.execute('BEGIN EXCLUSIVE')
        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode == sqlite3.SQLITE_BUSY:
                return False
            raise
        import controller_state
        held_at = lambda db, revision: primary and controller_state.held(db, revision)
        current_overrides = lambda db: controller_state.overrides(db) if primary else {'power': None, 'brightness': None}
        if primary:
            with contextlib.closing(connect()) as db, db:
                db.execute('BEGIN IMMEDIATE')
                controller_state.recover(db, attempts=True)
                if controller_state.held(db, control_state(db)['revision']) and not shared_input.selected(db):
                    return
        config = load_config(directory, device)
        config['_now'] = now
        read_unread = read_unread or unread_reader(config)
        scenes = scene_factory(directory, config) if scene_factory else None
        metadata = wall.Metadata(directory, config)
        sender = send or (scenes.send if scenes else render)
        active_execution = [None]
        request = scenes.request if scenes else light_request
        def controller_request(*args, **kwargs):
            execution = active_execution[0]
            if execution is not None and args[1] != 'GET':
                return execution.call(request, *args, **kwargs)
            return request(*args, **kwargs)
        config['_controller_request'] = controller_request
        if scenes:
            scenes.request = controller_request
        from types import SimpleNamespace
        projection = SimpleNamespace(connect_state=connect_state, mark_dirty=mark_dirty,
                                     control_state=control_state, COLORS=COLORS, wall=wall,
                                     registered_devices=registered_devices)
        # The caller's feed state survives a failed Lines pass, so a Lines outage does not turn
        # every later feed read into a resync that drops the other devices' comets and waves.
        feed = {} if feed is None else feed
        poller = feed.setdefault('poller', shared_input.Poller(directory, projection)) if primary else None
        while True:
            if not primary and device not in registered_devices(directory):
                return  # The device was removed; its instance stops without another request.
            if poller:
                shared = poller.tick(now())
            else:
                with contextlib.closing(connect()) as db:
                    shared = shared_input.selected(db)
            if not shared: metadata.refresh()
            with contextlib.closing(connect()) as db, db:
                if not shared_input.selected(db) and metadata.sync(db): mark_dirty(db)
                control = control_state(db, device)
                held = held_at(db, control['revision'])
                overrides = current_overrides(db)
            if held:
                if not shared: return
                sleep(1)
                continue
            mode = control['mode']
            pending_mode = control['revision'] != control['applied']
            config.update(_mode=mode, _wave_cutoff=control['wave_cutoff'], _brightness=overrides['brightness'])
            # Desired power off silences indicator, restoration and preview writes; a
            # pending mode command still applies its own policy (it cleared any override).
            dark = overrides['power'] is False and not pending_mode
            # Free mode does not even poll the light controller after handoff.
            observing = bool(scenes) and (mode != 'free' or pending_mode)
            external_scene = scenes.observe() if observing else False
            with contextlib.closing(connect()) as db, db:
                db.execute('BEGIN IMMEDIATE')
                if held_at(db, control['revision']):
                    return
                if control_state(db, device)['revision'] != control['revision']:
                    continue
                if observing and primary:
                    controller_state.discovered(db, scenes.names)
                if current_overrides(db) != overrides:
                    continue  # A control admitted during the device round trip restarts the pass.
                preview = db.execute('SELECT value FROM meta WHERE key=?', (key('preview'),)).fetchone()
                if preview:
                    db.execute('DELETE FROM meta WHERE key=?', (key('preview'),))
            if preview and mode != 'free' and not dark:
                def preview_send(cfg, snap, instant, loop):
                    with contextlib.closing(connect()) as check, check:
                        check.execute('BEGIN IMMEDIATE')
                        if (held_at(check, control['revision']) or
                                control_state(check, device)['revision'] != control['revision']):
                            raise PreviewCancelled()
                        sender(cfg, snap, instant, loop)
                def preview_sleep(seconds):
                    deadline = now() + seconds
                    while now() < deadline:
                        sleep(min(0.25, deadline - now()))
                        with contextlib.closing(connect()) as check:
                            if control_state(check, device)['revision'] != control['revision']:
                                raise PreviewCancelled()
                try:
                    play_preview(config, preview[0], preview_send, preview_sleep, now)
                except PreviewCancelled:
                    pass
                with contextlib.closing(connect()) as db, db:
                    db.execute('DELETE FROM display_v3 WHERE device=?', (device,))
                continue
            started = now()
            unread = None if shared else read_unread()
            with contextlib.closing(connect()) as db, db:
                db.execute('BEGIN IMMEDIATE')
                if held_at(db, control['revision']):
                    return
                if control_state(db, device)['revision'] != control['revision']:
                    continue
                # Read evidence is shared; every instance may apply it idempotently.
                if not shared_input.selected(db): reconcile_read_state(db, unread, started)
                prune_comets(db, started, mode, device)
                if primary:
                    import integration_api
                    integration_api.process(db, projection, config, now=started)
                if wall.apply_pending(db, device): mark_dirty(db)
                config['_locate'] = wall.locate_state(db, config, started, mode)
                snapshot = dashboard(db, config, started)
                config['_comet'] = current_comet(db, started, device) if mode == 'work' and not config['_locate'] else None
                wall.render_config(db, config, snapshot)
                shared_input.render_config(db, config)
                generation = db.execute("SELECT value FROM meta WHERE key='event_revision'").fetchone()
                db.commit()
                db.execute('BEGIN IMMEDIATE')
                if held_at(db, control['revision']):
                    return
                if (control_state(db, device)['revision'] != control['revision'] or
                        db.execute("SELECT value FROM meta WHERE key='event_revision'").fetchone() != generation):
                    continue
                if current_overrides(db) != overrides:
                    continue  # Overrides and queued controls must come from one locked read.
                waves = [item if item and item[1] > control['wave_cutoff'] else None for item in snapshot]
                loop = not config['_locate'] and (mode != 'work' or (not config['_comet'] and started >= introduction_ends(waves)))
                if pending_mode or (scenes and mode != 'free' and
                        (external_scene or (bool(any(snapshot) or config['_comet'] or config['_locate']) or mode == 'quiet') != scenes.state['owned'])):
                    db.execute('DELETE FROM display_v3 WHERE device=?', (device,))
                # Other devices never journal into the protected controller's receipts.
                execution = controller_state.Execution(db, control['revision']) if primary else None
                def guarded_sender(*args):
                    return execution.call(sender, *args) if send and execution else sender(*args)
                def apply_mode():
                    active_execution[0] = execution
                    if mode == 'free':
                        if pending_mode:
                            guarded_sender(config, [None] * len(snapshot), started, True)
                        db.execute('DELETE FROM display_v3 WHERE device=?', (device,))
                    elif not dark:
                        update_display(db, config, snapshot, started, loop, guarded_sender)
                    if execution:
                        execution.complete()
                def apply_controls():
                    # Native one-shot writes, each journaled under its own request, oldest first.
                    for sequence, command in controller_state.controls(db, control['revision']) if primary else ():
                        target = controller_state.control_payload(controller_state.read(db), command)
                        if target is None:
                            controller_state.finish(db, sequence, 'failed', 'unsupported-capability')
                            continue
                        active_execution[0] = controller_state.Execution(db, control['revision'], sequence)
                        controller_request(config, 'PUT', target[0], target[1])
                        active_execution[0].complete()
                        if scenes and command['kind'] == 'brightness.set' and mode != 'free':
                            scenes.wrote(scenes.selected, command['percent'])
                try:
                    # A pending mode applies first so a control admitted behind it lands last.
                    if pending_mode:
                        apply_mode(); apply_controls()
                    else:
                        apply_controls(); apply_mode()
                except controller_state.Cancelled:
                    db.commit()
                    continue
                finally:
                    active_execution[0] = None
                # A concurrent decision can commit between journaled sends.
                if held_at(db, control['revision']):
                    return
                if control_state(db, device)['revision'] != control['revision']:
                    continue
                if current_overrides(db) != overrides or (primary and controller_state.controls(db, control['revision'])):
                    continue  # A control admitted mid-apply keeps its wake-up and runs next pass.
                db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)', (key('mode_applied'), str(control['revision'])))
                db.execute('DELETE FROM meta WHERE key IN (?, ?)', ('dirty', key('control_error')))
                watching = (shared_input.selected(db) or bool(db.execute('SELECT 1 FROM receipts LIMIT 1').fetchone()) or
                            bool(scenes and mode != 'free' and (any(snapshot) or config['_comet'] or config['_locate'] or mode == 'quiet')))
                settling = db.execute('SELECT MIN(completed + ?) FROM receipts WHERE observed=0',
                                      (READ_SETTLE_SECONDS,)).fetchone()[0]
                if loop and not watching:
                    db.execute('DELETE FROM meta WHERE key=?', (key('rendering'),))
                    guard.rollback()
                    return
                db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)', (key('rendering'), '1'))
            deadline = started + (1.0 if loop else PULSE_SECONDS)
            if shared: deadline = min(deadline, started + 1)
            if config['_locate']:
                deadline = min(deadline, config['_locate']['started'] + 1)
            if config['_comet']:
                deadline = min(deadline, config['_comet']['started'] + COMET_SECONDS)
            if unread is not None and settling is not None and settling > started:
                deadline = min(deadline, settling)
            while now() < deadline:
                sleep(min(0.25, deadline - now()))
                with contextlib.closing(sqlite3.connect(directory / 'status.sqlite', timeout=2.5)) as db:
                    # Another device's instance may already have cleared the global dirty flag;
                    # any change since this pass's rendered revision still wakes this device.
                    woken = db.execute("SELECT 1 FROM meta WHERE (key='event_revision' AND value IS NOT ?) OR key=? LIMIT 1",
                                       (generation[0] if generation else None, key('preview'))).fetchone()
                if woken or (watching and not shared and read_unread() != unread):
                    break


class PreviewCancelled(Exception):
    pass


def hook_command(script, state_dir=None):
    state_args = ['--state-dir', str(state_dir)] if state_dir is not None else []
    if os.name == 'nt':
        # Select PowerShell explicitly, regardless of Codex's command shell.
        quote = lambda text: "'" + str(text).replace("'", "''") + "'"
        source = '& ' + quote(sys.executable) + ' ' + quote(script) + ' hook'
        if state_args:
            source += ' --state-dir ' + quote(state_dir)
        encoded = base64.b64encode(source.encode('utf-16le')).decode('ascii')
        windows = 'powershell.exe -NoProfile -NonInteractive -EncodedCommand ' + encoded
        drive, rest = str(script).split(':', 1)
        wsl_script = '/mnt/' + drive.lower() + rest.replace('\\', '/')
        return shlex.join(['python3', wsl_script, 'hook', *state_args]), windows
    return shlex.join([sys.executable, str(script), 'hook', *state_args]), None


def merge_hooks(original, command, remove=False, windows_command=None):
    result = json.loads(json.dumps(original))
    hooks = result.setdefault('hooks', {})
    for name in EVENTS:
        groups = hooks.get(name, [])
        # Remove only handlers belonging to this integration, keeping others intact.
        clean = []
        for group in groups:
            item = dict(group)
            item['hooks'] = [h for h in group.get('hooks', [])
                             if h.get('statusMessage') != MARKER]
            if item['hooks']:
                clean.append(item)
        if not remove:
            handler = {'type': 'command', 'command': command,
                       'timeout': 3 if name in ('SessionEnd', 'Interrupt') else 5,
                       'statusMessage': MARKER}
            if windows_command:
                handler['commandWindows'] = windows_command
            clean.append({'hooks': [handler]})
        if clean:
            hooks[name] = clean
        else:
            hooks.pop(name, None)
    return result


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    if os.name != 'nt':
        temporary.chmod(0o600)
    temporary.replace(path)


def manage_hooks(codex_home, operation, script, state_dir=None):
    """Change this integration's hooks in one explicitly selected Codex home."""
    if operation not in ('remove', 'register'):
        raise ValueError('invalid hook operation')
    codex_home = Path(codex_home)
    hooks_file = codex_home / 'hooks.json'
    original_bytes = hooks_file.read_bytes() if hooks_file.exists() else None
    original = json.loads(original_bytes.decode('utf-8-sig')) if original_bytes is not None else {}
    if original_bytes is not None:
        json_spans(original_bytes.decode('utf-8-sig'))
    if type(original) is not dict or type(original.get('hooks', {})) is not dict:
        raise ValueError('invalid hooks.json structure')
    hooks = original.get('hooks', {})
    if any(type(groups) is not list or any(type(group) is not dict
           or type(group.get('hooks', [])) is not list
           or any(type(handler) is not dict for handler in group.get('hooks', []))
           for group in groups) for groups in hooks.values()):
        raise ValueError('invalid hooks.json structure')
    command, windows_command = hook_command(Path(script), state_dir=state_dir)
    saved = original if has_legacy_hooks_value(original) else None
    if operation == 'register' and saved is None:
        for candidate in sorted(codex_home.glob('hooks.nanoleaf-backup-*.json'), reverse=True):
            try:
                value = json.loads(candidate.read_text(encoding='utf-8-sig'))
            except (OSError, ValueError, UnicodeError):
                continue
            if type(value) is dict and has_legacy_hooks_value(value):
                saved = value
                break
    if operation == 'remove':
        if not has_legacy_hooks_value(original):
            return False
        rendered = remove_marked_hooks_json(original_bytes)
    else:
        fresh = merge_hooks({}, command, windows_command=windows_command)
        groups_by_event = marked_groups(fresh)
        if saved is not None:
            groups_by_event.update(marked_groups(saved))
        rendered = remove_marked_hooks_json(original_bytes) if original_bytes is not None else b'{}'
        for event, groups in groups_by_event.items():
            rendered = append_hook_groups_json(rendered, event, groups)
        # Re-registering an already-correct configuration must not rewrite bytes.
    if isinstance(rendered, str):
        bom = b'\xef\xbb\xbf' if original_bytes is not None and original_bytes.startswith(b'\xef\xbb\xbf') else b''
        rendered = bom + rendered.encode('utf-8')
    if original_bytes is not None and json.loads(rendered.decode('utf-8-sig')) == original:
        return False
    codex_home.mkdir(parents=True, exist_ok=True)
    if original_bytes is not None:
        backup = hooks_file.with_name('hooks.nanoleaf-backup-' + str(time.time_ns()) + '.json')
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as backup_file:
            backup_file.write(original_bytes)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=codex_home, prefix='.hooks-', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write(rendered)
        temporary.replace(hooks_file)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def hooks_command(argv):
    parser = argparse.ArgumentParser(description='Manage Nanoleaf hooks in one Codex home.')
    parser.add_argument('operation', choices=('remove', 'register'))
    parser.add_argument('--codex-home', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    directory = args.state_dir or data_dir()
    if args.operation == 'remove':
        if shared_input.inspect(directory)['source'] != 'shared':
            parser.error('Cannot remove legacy hooks while legacy input is selected.')
    try:
        changed = manage_hooks(args.codex_home, args.operation, Path(__file__).resolve(), state_dir=directory)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        parser.error('Cannot update hooks.json; it is malformed or unavailable, and no changes were made.')
    print(('Updated' if changed else 'Already current') + ' Nanoleaf hooks in ' + str(args.codex_home / 'hooks.json'))
    print('Restart Codex to reload hook configuration.')


def has_legacy_hooks(codex_home):
    """Legacy input needs marked handlers for every lifecycle event."""
    hooks_file = Path(codex_home) / 'hooks.json'
    try:
        text = hooks_file.read_text(encoding='utf-8-sig')
        value = json.loads(text)
        json_spans(text)
        hooks = value.get('hooks', {}) if type(value) is dict else {}
        return type(hooks) is dict and all(
            has_legacy_hooks_value({'hooks': {event: hooks.get(event)}}) for event in EVENTS)
    except (OSError, ValueError, UnicodeError):
        return False


def has_legacy_hooks_value(value):
    hooks = value.get('hooks', {}) if type(value) is dict else {}
    return type(hooks) is dict and any(
        type(groups) is list and any(type(group) is dict and type(group.get('hooks', [])) is list
        and any(type(handler) is dict and handler.get('statusMessage') == MARKER
                for handler in group.get('hooks', [])) for group in groups)
        for name, groups in hooks.items() if name in EVENTS)


def marked_groups(value):
    hooks = value.get('hooks', {}) if type(value) is dict else {}
    result = {}
    if type(hooks) is not dict:
        return result
    for event in EVENTS:
        groups = hooks.get(event, [])
        if type(groups) is not list:
            continue
        selected = []
        for group in groups:
            if type(group) is not dict or type(group.get('hooks', [])) is not list:
                continue
            marked = [handler for handler in group['hooks']
                      if type(handler) is dict and handler.get('statusMessage') == MARKER]
            if marked:
                selected.append({**group, 'hooks': marked})
        if selected:
            result[event] = selected
    return result


def json_spans(text):
    """Parse JSON while retaining value and property byte-span boundaries."""
    def whitespace(index):
        while index < len(text) and text[index] in ' \t\r\n':
            index += 1
        return index

    def parse(index):
        index = whitespace(index)
        start = index
        char = text[index]
        if char == '{':
            index = whitespace(index + 1)
            members = []
            if text[index] == '}':
                return ('object', start, index + 1, members), index + 1
            while True:
                key_start = index
                key_node, index = parse(index)
                if key_node[0] != 'string':
                    raise ValueError('invalid JSON object key')
                key = json.loads(text[key_node[1]:key_node[2]])
                if any(member[0] == key for member in members):
                    raise ValueError('duplicate JSON object key')
                index = whitespace(index)
                if text[index] != ':':
                    raise ValueError('invalid JSON object')
                value_node, index = parse(index + 1)
                members.append((key, key_start, key_node[2], value_node))
                index = whitespace(index)
                if text[index] == '}':
                    return ('object', start, index + 1, members), index + 1
                if text[index] != ',':
                    raise ValueError('invalid JSON object')
                index = whitespace(index + 1)
        if char == '[':
            index = whitespace(index + 1)
            values = []
            if text[index] == ']':
                return ('array', start, index + 1, values), index + 1
            while True:
                value_node, index = parse(index)
                values.append(value_node)
                index = whitespace(index)
                if text[index] == ']':
                    return ('array', start, index + 1, values), index + 1
                if text[index] != ',':
                    raise ValueError('invalid JSON array')
                index = whitespace(index + 1)
        if char == '"':
            index += 1
            escaped = False
            while index < len(text):
                current = text[index]
                index += 1
                if escaped:
                    escaped = False
                elif current == '\\':
                    escaped = True
                elif current == '"':
                    return ('string', start, index, None), index
            raise ValueError('invalid JSON string')
        while index < len(text) and text[index] not in ',]} \t\r\n':
            index += 1
        json.loads(text[start:index])
        return ('value', start, index, None), index

    node, end = parse(0)
    if whitespace(end) != len(text):
        raise ValueError('trailing JSON data')
    return node


def json_member(node, key):
    if node[0] != 'object':
        return None
    return next((member for member in node[3] if member[0] == key), None)


def remove_marked_hooks_json(raw):
    """Remove marked handlers while retaining every unrelated JSON value verbatim."""
    if raw is None:
        return b'{}'
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text = raw.decode('utf-8-sig')
    root = json_spans(text)
    hooks_member = json_member(root, 'hooks')
    if not hooks_member:
        return raw
    hooks = hooks_member[3]
    patches = []
    if hooks[0] != 'object':
        return raw
    for event in EVENTS:
        event_member = json_member(hooks, event)
        if not event_member or event_member[3][0] != 'array':
            continue
        groups = event_member[3]
        updated_groups = []
        changed = False
        for group in groups[3]:
            hooks_member = json_member(group, 'hooks')
            if not hooks_member or hooks_member[3][0] != 'array':
                updated_groups.append(text[group[1]:group[2]])
                continue
            array = hooks_member[3]
            retained = [item for item in array[3]
                        if not (type(json.loads(text[item[1]:item[2]])) is dict
                                and json.loads(text[item[1]:item[2]]).get('statusMessage') == MARKER)]
            if len(retained) == len(array[3]):
                updated_groups.append(text[group[1]:group[2]])
                continue
            changed = True
            if not retained:
                continue
            group_text = text[group[1]:group[2]]
            left = array[1] - group[1] + 1
            right = array[2] - group[1] - 1
            replacement = ','.join(text[item[1]:item[2]] for item in retained)
            updated_groups.append(group_text[:left] + replacement + group_text[right:])
        if changed:
            array = groups
            left = array[1] + 1
            right = array[2] - 1
            patches.append((left, right, ','.join(updated_groups)))
    for left, right, replacement in sorted(patches, reverse=True):
        text = text[:left] + replacement + text[right:]
    return bom + text.encode('utf-8')


def append_hook_groups_json(raw, event, groups):
    text = raw.decode('utf-8-sig') if isinstance(raw, bytes) else raw
    root = json_spans(text)
    hooks_member = json_member(root, 'hooks')
    serialized = ','.join(json.dumps(group, ensure_ascii=True) for group in groups)
    if not hooks_member:
        hooks_text = '{' + json.dumps(event) + ':[' + serialized + ']}'
        insert = (', ' if root[3] else '') + json.dumps('hooks') + ': ' + hooks_text
        return text[:root[2] - 1] + insert + text[root[2] - 1:]
    hooks = hooks_member[3]
    event_member = json_member(hooks, event)
    if event_member:
        array = event_member[3]
        insert = (',' if array[3] else '') + serialized
        return text[:array[2] - 1] + insert + text[array[2] - 1:]
    insert = (', ' if hooks[3] else '') + json.dumps(event) + ': [' + serialized + ']'
    return text[:hooks[2] - 1] + insert + text[hooks[2] - 1:]


def setup(args):
    directory = getattr(args, 'state_dir', None) or data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    config_file = directory / 'config.json'
    if args.check or args.demo or args.reset or args.notify or args.refresh or args.comet:
        # Previews, checks and refresh address one device; reset clears the shared tasks of every device.
        device = getattr(args, 'device', None) or devices.DEFAULT
        preview = devices.meta_key('preview', device)
        config = load_config(directory, device)
        if (args.demo or args.notify) and get_status(directory, device)['mode'] == 'free':
            print('Choose Work or Quiet before running a preview.')
            return
        if args.comet:
            if get_status(directory, device)['mode'] != 'work':
                print('Choose Work before previewing a completion comet.')
                return
            with contextlib.closing(connect_state(directory)) as db, db:
                db.execute("INSERT OR REPLACE INTO meta VALUES (?,'comet')", (preview,))
            launch_worker(directory)
            print('Previewing one completion comet; live status returns afterward.')
        if args.check:
            info = light_request(config, 'GET')
            print('Connected:', info.get('name', 'Nanoleaf'), 'at', config['ip'],
                  'with', len(config['line_groups']), 'physical Lines' if config.get('kind', 'lines') == 'lines' else 'triangles')
            saved = SceneRestorer(directory, config).state['scene']
            print('Restore scene:', saved['name'] if saved else 'Choose a scene in the Nanoleaf app.')
        if args.demo:
            with contextlib.closing(connect_state(directory)) as db, db:
                db.execute("INSERT OR REPLACE INTO meta VALUES (?,'all')", (preview,))
            launch_worker(directory)
            print('Previewing green, yellow, red, and unread blue pulses; live status returns afterward.')
        if args.reset:
            with contextlib.closing(connect_state(directory)) as db, db:
                db.execute('DELETE FROM comets')
                db.execute('DELETE FROM sessions')
                db.execute('DELETE FROM display_v3')
                db.execute('DELETE FROM activity')
                db.execute('DELETE FROM receipts')
                db.execute('DELETE FROM slots')
                db.execute('DELETE FROM waits')
                db.execute("DELETE FROM meta WHERE key='preview' OR key LIKE 'preview@%'")
                mark_dirty(db)
            launch_worker(directory)
            print('Status cleared on every device. Each saved scene returns, or blue if no scene has been remembered.')
        if args.notify:
            with contextlib.closing(connect_state(directory)) as db, db:
                db.execute("INSERT OR REPLACE INTO meta VALUES (?,'working')", (preview,))
            launch_worker(directory)
            print('Queued one outward green pulse, then a local pulse. Live status returns afterward.')
        if args.refresh:
            with contextlib.closing(connect_state(directory)) as db, db:
                db.execute('DELETE FROM display_v3 WHERE device=?', (device,))
                mark_dirty(db)
            launch_worker(directory)
        return
    codex_base = os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))
    codex_dir = Path(windows_path(codex_base) if os.name == 'nt' else codex_base)
    hooks_file = codex_dir / 'hooks.json'
    original = json.loads(hooks_file.read_text(encoding='utf-8-sig')) if hooks_file.exists() else {}
    if args.uninstall:
        if (directory / 'status.sqlite').exists():
            # Removing the hooks hands every registered device back to the Nanoleaf app.
            for device in registered_devices(directory):
                set_mode(directory, 'free', device=device)
        remover = directory / 'remove-modes.ps1'
        if os.name == 'nt' and remover.exists():
            subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(remover)], check=True)
        write_json(hooks_file, merge_hooks(original, '', remove=True))
        print('Removed Nanoleaf hooks. Restart Codex. Saved light credentials remain in', directory)
        return
    print('Connect Codex status to Nanoleaf at 192.168.1.207.')
    print('This installs local hooks; it preserves existing hooks and notification settings.')
    token = getpass.getpass('Paste the working Nanoleaf auth_token (hidden): ').strip()
    config = {'ip': '192.168.1.207', 'token': token}
    info = light_request(config, 'GET')  # Validate before changing hook configuration.
    print('Connected:', info.get('name', 'Nanoleaf'))
    write_json(directory / 'layout.json', {'line_groups': pair_lines(info['panelLayout'])})
    write_json(config_file, config)
    installed_script = directory / 'bridge.py'
    if Path(__file__).resolve() != installed_script.resolve():
        shutil.copytree(Path(__file__).parent / 'vendor', directory / 'vendor', dirs_exist_ok=True)
        for name in ('project_map.py', 'devices.py', 'wall_server.py', 'wall.html', 'prism.js', 'prism-adapters.js', 'prism-labels.js', 'tray.ps1', 'remove-modes.ps1', 'install-modes.ps1', 'backup_install.py', 'controller_state.py', 'controller_server.py', 'controller_contract.py', 'requirements-controller.txt', 'README.md'):
            shutil.copyfile(Path(__file__).with_name(name), directory / name)
        shutil.copyfile(__file__, installed_script)
    codex_dir.mkdir(parents=True, exist_ok=True)
    if hooks_file.exists():
        backup = hooks_file.with_name('hooks.nanoleaf-backup-' + str(time.time_ns()) + '.json')
        shutil.copyfile(hooks_file, backup)
    command, windows_command = hook_command(installed_script)
    write_json(hooks_file, merge_hooks(original, command, windows_command=windows_command))
    with contextlib.closing(connect_state(directory)) as db, db:
        db.execute('DELETE FROM comets')
        db.execute('DELETE FROM sessions')
        db.execute('DELETE FROM display_v3')
        db.execute('DELETE FROM activity')
        db.execute('DELETE FROM receipts')
        db.execute('DELETE FROM slots')
        db.execute('DELETE FROM waits')
        mark_dirty(db)
    print('Installed hooks in', hooks_file)
    print('Review and trust the Nanoleaf hooks in the hook section of Codex Desktop Settings.')
    print('Task Lines pulse green while working, yellow for a question during work, and red when blocked.')
    print('Unread completions pulse blue until viewed. The first pulse of each state spreads outward.')
    print('Choose scenes in the Nanoleaf app. The latest one returns after all indicators clear.')
    print('If desktop hooks do not fire, report that here; installation alone is not verification.')


def main():
    # Windows and WSL SQLite locks on the same mounted file do not exclude
    # each other. Installed WSL hooks delegate before opening any state files,
    # so all live state writes and workers use Windows Python and its locks.
    if os.name != 'nt' and sys.argv[1:2] and (sys.argv[1].startswith('shared-') or sys.argv[1] in ('hook', 'hooks', 'worker', 'setup', 'mode', 'status', 'tray', 'map', 'serve', 'style', 'map-status', 'controller-configure', 'controller-token', 'controller-revoke', 'controller-serve', 'controller-status', 'controller-disable')):
        installed = Path(__file__).resolve()
        if installed.parent.name == 'CodexNanoleaf' and installed.parent.parent.name == 'Local':
            account = installed.parent.parents[2]
            runtime = account / '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
            if not runtime.is_file():
                print('Nanoleaf Windows runtime is unavailable; no state was changed.', file=sys.stderr)
                if sys.argv[1] == 'hook':
                    print('{}')
                return
            command = [str(runtime), windows_path(str(installed)),
                       *(windows_path(arg) for arg in sys.argv[1:])]
            raise SystemExit(subprocess.call(command))
    if sys.argv[1:2] and sys.argv[1].startswith('shared-'):
        from types import SimpleNamespace
        return shared_input.command(sys.argv[1:], SimpleNamespace(**globals()))
    if sys.argv[1:2] and sys.argv[1] == 'hooks':
        return hooks_command(sys.argv[2:])
    if sys.argv[1:2] and sys.argv[1].startswith('controller-'):
        import controller_server
        return controller_server.command(sys.argv[1:], sys.modules[__name__])
    if sys.argv[1:2] and sys.argv[1].startswith('device-'):
        # Linux-only enrollment; it refuses Windows and Windows-mounted state itself.
        import enrollment
        from types import SimpleNamespace
        raise SystemExit(enrollment.command(sys.argv[1:], SimpleNamespace(**globals())))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['setup', 'hook', 'worker', 'mode', 'status', 'tray', 'map', 'serve', 'style', 'map-status'])
    parser.add_argument('--state-dir', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('selection', nargs='?', choices=MODES + ('classic', 'project'))
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--port', type=int, help='Wall-map loopback port; overrides the installation setting.')
    parser.add_argument('--no-open', action='store_true', help='Print the wall-map URL without opening a browser.')
    parser.add_argument('--device', help='Registered device for mode, status, worker and device setup operations; defaults to the original Lines device.')
    group = parser.add_mutually_exclusive_group()
    for flag in ('check', 'demo', 'reset', 'uninstall', 'notify', 'refresh', 'comet'):
        group.add_argument('--' + flag, action='store_true')
    args = parser.parse_args()
    if os.name != 'nt' and args.mode == 'setup' and not any(
            getattr(args, flag) for flag in ('check', 'demo', 'reset', 'uninstall', 'notify', 'refresh', 'comet')):
        parser.error('Use bridge/install_linux.py from the reviewed source checkout for a fresh Linux installation.')
    directory = args.state_dir or data_dir()
    device = devices.DEFAULT
    if args.device is not None:
        # An unknown target never falls back to the original device.
        targeted = args.mode in ('mode', 'status', 'worker') or (args.mode == 'setup' and any(
            getattr(args, flag) for flag in ('check', 'demo', 'notify', 'refresh', 'comet')))
        if not targeted or args.device not in registered_devices(directory):
            parser.error('Unknown or unsupported device target.')
        device = args.device
    if args.mode == 'map-status':
        with contextlib.closing(connect_state(directory)) as db:
            print(json.dumps({**get_status(directory), **wall.settings(db), 'map_pending': wall.pending(db) is not None}))
        return
    if args.mode in ('map', 'serve', 'style'):
        import wall_server
        try:
            wall_server.command(args, directory, sys.modules[__name__])
        except RuntimeError as error:
            parser.exit(1, f'Wall map: {error}\n')
        except Exception:
            parser.exit(1, 'Wall map command failed. Check local configuration and the selected port.\n')
        return
    if args.mode == 'mode':
        if args.selection not in MODES:
            parser.error('Choose work, free, or quiet.')
        set_mode(directory, args.selection, device=device)
        print(json.dumps(get_status(directory, device)))
        return
    if args.mode == 'status':
        try:
            print(json.dumps(get_status(directory, device)))
        except Exception:
            print(json.dumps({'mode': None, 'pending': True, 'error': 'Local status unavailable.'}))
            sys.exit(1)
        return
    if args.mode == 'tray':
        if os.name != 'nt':
            parser.error('The tray control runs on Windows.')
        subprocess.Popen(['powershell.exe', '-NoProfile', '-STA', '-WindowStyle', 'Hidden',
                          '-File', str(Path(__file__).with_name('tray.ps1'))],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return
    if args.mode == 'worker':
        feed = {}
        while True:
            try:
                if run_worker(directory, device=device, feed=feed) is False: return
                with contextlib.closing(connect_state(directory)) as db:
                    resume_shared = shared_input.selected(db)
                if not resume_shared: return
                time.sleep(1)
            except Exception:
                # A failed pass records and retries this device only, while it is still registered.
                if device not in registered_devices(directory) or not record_failure(directory, device):
                    return
                # Release locks between attempts. All retries read the newest mode.
                time.sleep(2)
    if args.mode == 'hook':
        try:
            event = json.load(sys.stdin)
            handle_event(directory, event)
        except Exception:
            # Never block an agent or put a credential-containing exception in its output.
            print('Nanoleaf status hook could not update. Run setup --check.', file=sys.stderr)
        print('{}')
        return
    try:
        setup(args)
    except urllib.error.HTTPError as error:
        print('Nanoleaf HTTP status:', error.code, file=sys.stderr)
        sys.exit(1)
    except Exception:
        print('Setup failed. Check the IP, token, local network, and writable configuration folder.',
              file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
