"""Installation configuration: the state directory, registered devices and their geometry."""
import json
import math
from pathlib import Path

import devices
import jsonfile
import panels
import transport


def data_dir():
    adjacent = Path(__file__).resolve().parent
    if (adjacent / 'config.json').exists():
        return adjacent
    return Path.home() / '.local' / 'share' / 'codex-nanoleaf'


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


def load_config(directory, device=devices.DEFAULT, request=None):
    """Configuration and layout for one registered device; the original Lines device by default.

    A saved layout needs no device request. A missing or incomplete one is read from the device
    through request, a transport.light_request-compatible reader, and saved before use.
    """
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
        address = {'ip': entry['ip'], 'token': devices.credential(config, entry)}
        panel_layout = (request or transport.light_request)(address, 'GET')['panelLayout']
    if entry['kind'] == 'panels' and (layout is None or any(element['position'] is None for element in layout['elements'])):
        # Reported triangles only; unsupported geometry fails before anything is saved.
        layout = panels.read_layout(panel_layout)
        devices.save_device_layout(layout_file, device, layout, jsonfile.write_json)
    elif layout is None or any(element['position'] is None for element in layout['elements']):
        groups = [element['zones'] for element in layout['elements']] if layout else pair_lines(panel_layout)
        zones = {p['panelId']: p for p in panel_layout['layout']['positionData']}
        positions = [[sum(zones[p]['x'] for p in pair) / 2,
                      sum(zones[p]['y'] for p in pair) / 2] for pair in groups]
        layout = devices.lines_entry(groups, positions, layout)
        devices.save_device_layout(layout_file, device, layout, jsonfile.write_json)
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


def registered_devices(directory):
    """Registered device ids, the original Lines device first; an unreadable configuration means Lines only."""
    try:
        registry = devices.registry(json.loads((directory / 'config.json').read_text(encoding='utf-8-sig')))
    except (OSError, ValueError):
        return [devices.DEFAULT]
    return [devices.DEFAULT] + [device for device in registry if device != devices.DEFAULT]


def follow_registry(directory, config, device):
    """Point a running pass at its device's registered address and credential; keep them if unreadable."""
    try:
        saved = json.loads((directory / 'config.json').read_text(encoding='utf-8-sig'))
        entry = devices.registry(saved).get(device)
    except (OSError, ValueError):
        return
    if entry is None:
        return
    for key, value in (('ip', entry['ip']), ('token', devices.credential(saved, entry))):
        if value is not None:
            config[key] = value
