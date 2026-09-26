"""Configuration edits shared by the wall map and the integration extension.

Each edit runs inside the caller's write transaction. It validates its input against current
state, applies it (a map edit that would move an active comet waits as a pending wall edit), then
records the change once: the controller ledgers it advances and one display wake-up. Shared
project colors, task projects and the palette belong to the Lines ledger; every other edit
advances the ledger of the device it names. Adapters decode their own payloads, so this module
never sees HTTP routes, opaque IDs or requests.
"""
import re

import controller_state
import devices
import project_map as wall
import shared_input
from store import control_state, mark_dirty

SETTINGS = {'style': ('classic', 'project'), 'coverage': ('whole', 'status'), 'rotation': (0, 90, 180, 270),
            'flip_x': (0, 1), 'flip_y': (0, 1)}


def recorded(db, ledgers):
    for ledger in dict.fromkeys(ledgers):
        controller_state.changed(db, device=ledger)
    mark_dirty(db)


def projects(db):
    return {row[0] for row in db.execute('SELECT id FROM projects')}


def settings(db, config, changes):
    """Change the named device's map settings and, with a palette entry, the palette of every device."""
    device = devices.device_of(config)
    values = {k: v for k, v in changes.items() if k != 'palette'}
    if not changes or any(k not in SETTINGS or v not in SETTINGS[k] for k, v in values.items()):
        raise ValueError('Invalid setting.')
    # Animation coverage chooses between a Line's two halves; a one-zone triangle has none.
    if 'coverage' in values and config.get('kind', 'lines') != 'lines':
        raise ValueError('Animation coverage applies to Lines only.')
    # The palette covers every device and moves no comet source, so it applies at once.
    if 'palette' in changes:
        wall.save_palette(db, wall.validate_palette(changes['palette']))
    if values:
        wall.request_patch(db, {'settings': values}, config)
    recorded(db, ([devices.DEFAULT] if 'palette' in changes else []) + ([device] if values else []))


def assign(db, config, lines):
    """Assign projects or swap halves on the named device's elements."""
    known = projects(db)
    ids = {element['id'] for element in devices.elements(config)}
    lines_device = config.get('kind', 'lines') == 'lines'
    if not isinstance(lines, dict) or not lines:
        raise ValueError('Select at least one Line.')
    for key, value in lines.items():
        if key not in ids or not isinstance(value, dict) or not value or set(value) - {'project', 'signature'}:
            raise ValueError('Invalid Line assignment.')
        if 'project' in value and value['project'] is not None and value['project'] not in known:
            raise ValueError('Unknown project.')
        if 'signature' in value and (type(value['signature']) is not int or value['signature'] not in (0, 1)):
            raise ValueError('Invalid half.')
        if 'signature' in value and not lines_device:
            raise ValueError('Half swaps apply to Lines only.')
    wall.request_patch(db, {'lines': lines}, config)
    recorded(db, [devices.device_of(config)])


def project_color(db, project, color):
    if project not in projects(db) or not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('Invalid project color.')
    db.execute('UPDATE projects SET color=? WHERE id=?', (color.lower(), project))
    recorded(db, [devices.DEFAULT])


def task_project(db, config, session, project):
    """Override a task's project, or clear the override with None."""
    known = projects(db)
    if not db.execute('SELECT 1 FROM task_info WHERE session=?', (session,)).fetchone():
        raise ValueError('Unknown task.')
    if project is not None and project not in known:
        raise ValueError('Unknown project.')
    wall.request_patch(db, {'tasks': {session: project}}, config)
    recorded(db, [devices.DEFAULT])


def locate(db, config, line):
    """Flash one element of the named device white."""
    device = devices.device_of(config)
    if line not in {element['id'] for element in devices.elements(config)}:
        raise ValueError('Unknown Line.')
    if control_state(db, device)['mode'] == 'free':
        raise ValueError('Choose Work or Quiet to locate a Line.')
    db.execute('INSERT OR REPLACE INTO locate (line_id,started,device) VALUES (?,NULL,?)', (line, device))
    recorded(db, [device])


def evict(db, config, request):
    """Remove a shared task from the named device, as its eviction token permits."""
    device = devices.device_of(config)
    shared_input.evict(db, device, request)
    recorded(db, [device])
