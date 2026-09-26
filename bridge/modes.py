"""Lighting modes: the explicit mode command for one device and its read-only status."""
import contextlib
import sqlite3
import time

import controller_state
import database
import devices
import integration_api
import launcher
from store import control_state, mark_dirty

MODES = ('work', 'free', 'quiet')


def change_mode(db, mode, instant, notify=True, device=devices.DEFAULT):
    """Apply an explicit mode command inside the caller's transaction; True when a worker pass is needed.

    A native mode.set has already advanced its ledger and passes notify=False.
    """
    key = lambda name: devices.meta_key(name, device)
    state = control_state(db, device)
    # Only a device with a controller ledger publishes its mode changes; other devices stay local.
    ledger = controller_state.present(db, device)
    if ledger and device == devices.DEFAULT:
        integration_api.retire(db)  # Requested animations play only on the Lines.
    notify = notify and ledger
    # Any explicit mode command, including the same mode, ends that device's native power/brightness overrides.
    overridden = ledger and any(value is not None for value in controller_state.overrides(db, device).values())
    if overridden:
        db.execute('DELETE FROM meta WHERE key IN (?, ?)', (key('controller_power'), key('controller_brightness')))
    if state['mode'] == mode and overridden:
        db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)', (key('mode_revision'), str(state['revision'] + 1)))
        mark_dirty(db)
        if notify:
            controller_state.changed(db, mode=True, device=device)
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
            controller_state.changed(db, mode=True, device=device)
        return True
    if notify:
        controller_state.changed(db, mode=True, device=device)
    return state['revision'] != state['applied'] or bool(state['error'])


def set_mode(directory, mode, launch=None, now=time.time, device=devices.DEFAULT):
    if mode not in MODES:
        raise ValueError('Unknown lighting mode.')
    with contextlib.closing(database.connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        needed = change_mode(db, mode, now(), device=device)
    if needed:
        (launch or launcher.launch_worker)(directory)


def get_status(directory, device=devices.DEFAULT):
    # Status reads never initialize or migrate a database.
    with contextlib.closing(sqlite3.connect(
            (directory / 'status.sqlite').resolve().as_uri() + '?mode=ro', uri=True, timeout=0.2)) as db:
        state = control_state(db, device)
    return {'mode': state['mode'], 'pending': state['revision'] != state['applied'],
            'error': state['error']}
