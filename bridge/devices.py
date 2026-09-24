"""Device registry, per-device layout shape and device-scoped state migration."""
import contextlib
import json
import math
import os
import re

DEFAULT = 'wall'
KINDS = {'lines': 2, 'panels': 1}
ID = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
LAYOUT_VERSION = 2
GEOMETRY_KEYS = ('zone_geometry', 'connector_geometry', 'panel_geometry')
_QUOTED = "'" + DEFAULT + "'"
# Column order keeps the legacy columns first so positional readers of the
# shared-input backup keep working; the device key is last.
SCHEMAS = {
    'slots': f'(session TEXT NOT NULL, slot INTEGER NOT NULL, device TEXT NOT NULL DEFAULT {_QUOTED}, '
             'PRIMARY KEY (device, session), UNIQUE (device, slot))',
    'comets': f'(session TEXT NOT NULL, turn TEXT, queued REAL, source INTEGER, started REAL, '
              f'device TEXT NOT NULL DEFAULT {_QUOTED}, PRIMARY KEY (device, session))',
    'line_prefs': f'(line_id TEXT NOT NULL, project TEXT, signature INTEGER DEFAULT 0, '
                  f'device TEXT NOT NULL DEFAULT {_QUOTED}, PRIMARY KEY (device, line_id))',
    'map_settings': '(id INTEGER PRIMARY KEY, style TEXT, coverage TEXT, rotation INTEGER, flip_x INTEGER, '
                    f'flip_y INTEGER, device TEXT NOT NULL DEFAULT {_QUOTED})',
    'map_pending': f'(id INTEGER PRIMARY KEY, payload TEXT, device TEXT NOT NULL DEFAULT {_QUOTED})',
    'locate': f'(id INTEGER PRIMARY KEY, line_id TEXT, started REAL, device TEXT NOT NULL DEFAULT {_QUOTED})',
    'display_v3': '(id INTEGER PRIMARY KEY, snapshot TEXT, looping INTEGER, rendered REAL, '
                  f'device TEXT NOT NULL DEFAULT {_QUOTED})',
}
# Tables whose key must include the device are rebuilt; singleton tables gain a column.
REBUILT = {'slots': 'session, slot', 'comets': 'session, turn, queued, source, started',
           'line_prefs': 'line_id, project, signature'}
EXTENDED = ('map_settings', 'map_pending', 'locate', 'display_v3')


def element_id(zones):
    return ':'.join(str(zone) for zone in sorted(zones))


def device_of(config):
    return config.get('device', DEFAULT)


def meta_key(name, device=DEFAULT):
    return name if device == DEFAULT else name + '@' + device


def scene_file(device=DEFAULT):
    if device != DEFAULT and not ID.fullmatch(device):
        raise ValueError('Invalid device identity.')
    return 'scene-state.json' if device == DEFAULT else 'scene-state.' + device + '.json'


def lock_file(device=DEFAULT):
    """The worker's exclusive lock; the original device keeps the existing file name."""
    if device != DEFAULT and not ID.fullmatch(device):
        raise ValueError('Invalid device identity.')
    return 'notification-lock.sqlite' if device == DEFAULT else 'notification-lock.' + device + '.sqlite'


def registry(config):
    """Registered devices from the private configuration; the original Lines device is implied."""
    if not isinstance(config, dict):
        raise ValueError('Invalid configuration.')
    raw = config.get('devices') or {}
    if not isinstance(raw, dict):
        raise ValueError('Invalid device registry.')
    devices = {}
    for device, entry in raw.items():
        if (not isinstance(device, str) or not ID.fullmatch(device) or not isinstance(entry, dict)
                or entry.get('kind') not in KINDS or not isinstance(entry.get('ip'), str)
                or not isinstance(entry.get('token_ref'), str) or not entry['token_ref']):
            raise ValueError('Invalid device registry entry.')
        devices[device] = {'kind': entry['kind'], 'ip': entry['ip'], 'token_ref': entry['token_ref']}
    if DEFAULT not in devices:
        # A configuration that predates the registry describes the original Lines device.
        ip = config.get('ip')
        devices = {DEFAULT: {'kind': 'lines', 'ip': ip if isinstance(ip, str) else None, 'token_ref': 'token'}, **devices}
    return devices


def credential(config, entry):
    """The referenced credential, or None when the configuration holds none."""
    value = config.get(entry['token_ref'])
    return value if isinstance(value, str) else None


def _numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_elements(kind, elements):
    per_element = KINDS.get(kind)
    if per_element is None:
        raise ValueError('Unsupported device kind.')
    if not isinstance(elements, list) or not 1 <= len(elements) <= 300:
        raise ValueError('Invalid element list.')
    seen, clean = set(), []
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            raise ValueError('Invalid element.')
        zones = element.get('zones')
        if (not isinstance(zones, list) or len(zones) != per_element
                or any(type(zone) is not int or not 0 <= zone <= 65535 for zone in zones)
                or len(set(zones)) != len(zones) or seen & set(zones)):
            raise ValueError('Invalid element zones.')
        if element.get('id') != element_id(zones):
            raise ValueError('Element identity must follow its zones.')
        if element.get('number') != index + 1:
            raise ValueError('Element numbering must follow the saved order.')
        position = element.get('position')
        if position is not None and (not isinstance(position, list) or len(position) != 2
                                     or not all(_numeric(value) for value in position)):
            raise ValueError('Invalid element position.')
        seen.update(zones)
        clean.append({'id': element['id'], 'number': index + 1, 'zones': list(zones),
                      'position': None if position is None else [position[0], position[1]]})
    return clean


def _entry(kind, elements, source):
    entry = {'kind': kind, 'elements': elements}
    for key in GEOMETRY_KEYS:
        if isinstance(source, dict) and source.get(key) is not None:
            entry[key] = source[key]
    return entry


def lines_entry(groups, positions=None, source=None):
    """A Lines device entry from the legacy zone pairing and optional pulse positions."""
    if not isinstance(groups, list) or any(not isinstance(pair, list) for pair in groups):
        raise ValueError('Invalid physical Line mapping.')
    if positions is not None and (not isinstance(positions, list) or len(positions) != len(groups)):
        raise ValueError('Each Line needs a position for outward pulses.')
    elements = []
    for index, pair in enumerate(groups):
        if any(type(zone) is not int for zone in pair):
            raise ValueError('Invalid physical Line mapping.')
        elements.append({'id': element_id(pair), 'number': index + 1, 'zones': list(pair),
                         'position': positions[index] if positions else None})
    return _entry('lines', validate_elements('lines', elements), source)


def layout_devices(saved):
    """Normalize a saved layout, Lines-only or per-device, into {device: entry}."""
    if not isinstance(saved, dict):
        raise ValueError('Invalid layout file.')
    if 'devices' in saved:
        if saved.get('version') != LAYOUT_VERSION or not isinstance(saved['devices'], dict):
            raise ValueError('Unsupported layout version.')
        result = {}
        for device, entry in saved['devices'].items():
            if not isinstance(device, str) or not ID.fullmatch(device) or not isinstance(entry, dict):
                raise ValueError('Invalid layout device.')
            kind = entry.get('kind')
            result[device] = _entry(kind, validate_elements(kind, entry.get('elements')), entry)
        return result
    if not saved.get('line_groups'):
        return {}
    return {DEFAULT: lines_entry(saved['line_groups'], saved.get('line_positions'), saved)}


def projection(entry):
    """Configuration keys the renderer and map read for one loaded device."""
    elements = entry['elements']
    result = {'kind': entry['kind'],
              'elements': [dict(e, zones=list(e['zones']), position=None if e['position'] is None else list(e['position']))
                           for e in elements],
              'line_groups': [list(e['zones']) for e in elements]}
    if all(e['position'] is not None for e in elements):
        result['line_positions'] = [list(e['position']) for e in elements]
    for key in GEOMETRY_KEYS:
        if key in entry:
            result[key] = entry[key]
    return result


def elements(config):
    """Elements of the loaded device, derived from the Lines pairing when only that is supplied."""
    if config.get('elements'):
        return config['elements']
    positions = config.get('line_positions') or []
    return [{'id': element_id(pair), 'number': index + 1, 'zones': list(pair),
             'position': list(positions[index]) if index < len(positions) else None}
            for index, pair in enumerate(config.get('line_groups') or [])]


def serialized(devices):
    """Validate a per-device layout and return the version-2 file content."""
    if not isinstance(devices, dict) or not devices:
        raise ValueError('Invalid layout devices.')
    output = {}
    for device, entry in devices.items():
        if not isinstance(device, str) or not ID.fullmatch(device) or not isinstance(entry, dict):
            raise ValueError('Invalid layout device.')
        kind = entry.get('kind')
        output[device] = _entry(kind, validate_elements(kind, entry.get('elements')), entry)
    return {'version': LAYOUT_VERSION, 'devices': output}


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.chmod(0o600)
    temporary.replace(path)


def save_layout(path, devices, write=write_json):
    """Write the per-device layout atomically; an invalid layout leaves the last valid file."""
    write(path, serialized(devices))


def save_device_layout(path, device, entry, write=write_json):
    """Merge one device's discovered entry into the current file under an exclusive lock.

    Each device's worker may discover its layout at the same time; re-reading under the
    lock keeps the other device's entry instead of overwriting it with a stale copy.
    An entry of None removes that device's entry.
    """
    import sqlite3
    with contextlib.closing(sqlite3.connect(path.with_name('layout-lock.sqlite'), timeout=5)) as lock:
        lock.execute('BEGIN EXCLUSIVE')
        current = layout_devices(json.loads(path.read_text())) if path.exists() else {}
        if entry is not None:
            current[device] = entry
            save_layout(path, current, write)
        elif current.pop(device, None) is not None:
            if current:
                save_layout(path, current, write)
            else:
                path.unlink()
        lock.rollback()


def create(db, table):
    db.execute('CREATE TABLE IF NOT EXISTS ' + table + ' ' + SCHEMAS[table])


def columns(db, table):
    return [row[1] for row in db.execute('PRAGMA table_info("' + table + '")')]


def migrate(db):
    """Guarded, idempotent device-scoped upgrade inside the caller's initialization transaction."""
    for table, legacy_columns in REBUILT.items():
        if 'device' in columns(db, table):
            continue
        db.execute('ALTER TABLE ' + table + ' RENAME TO ' + table + '_legacy')
        create(db, table)
        db.execute('INSERT INTO ' + table + ' (' + legacy_columns + ') SELECT ' + legacy_columns + ' FROM ' + table + '_legacy')
        db.execute('DROP TABLE ' + table + '_legacy')
    for table in EXTENDED:
        if 'device' not in columns(db, table):
            db.execute('ALTER TABLE ' + table + ' ADD COLUMN device TEXT NOT NULL DEFAULT ' + _QUOTED)
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS ' + table + '_device ON ' + table + ' (device)')
