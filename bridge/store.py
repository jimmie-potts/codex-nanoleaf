"""Shared records in the integration database's meta table: the display wake-up and each device's control state.

Each runs inside the caller's transaction; none opens a connection.
"""
import devices


def mark_dirty(db):
    db.execute("INSERT INTO meta VALUES ('event_revision', '1') ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1")
    db.execute("INSERT OR REPLACE INTO meta VALUES ('dirty', '1')")


def control_state(db, device=devices.DEFAULT):
    meta = dict(db.execute('SELECT key,value FROM meta'))
    key = lambda name: devices.meta_key(name, device)
    return {'mode': meta.get(key('mode'), 'work'),
            'revision': int(meta.get(key('mode_revision'), '0')),
            'applied': int(meta.get(key('mode_applied'), '0')),
            'wave_cutoff': float(meta.get(key('wave_cutoff'), '-inf')),
            'error': meta.get(key('control_error'))}


def mark_applied(db, revision, device=devices.DEFAULT):
    """Record that the device's worker has applied every mode command up to `revision`."""
    db.execute('INSERT OR REPLACE INTO meta VALUES (?, ?)', (devices.meta_key('mode_applied', device), str(revision)))
