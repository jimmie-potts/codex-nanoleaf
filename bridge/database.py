"""Opens the integration's SQLite state, initializes every owner's tables in one transaction and seeds synthetic tasks."""
import sqlite3
import time

import devices
import integration_api
import project_map as wall
import shared_input


def connect_state(directory, timeout=2.5):
    db = sqlite3.connect(directory / 'status.sqlite', timeout=timeout)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            wall.init(db)
            shared_input.init(db)
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


def seed_synthetic(db, projects, tasks):
    """Add synthetic projects and tasks for the demo and browser fixtures inside the caller's transaction.

    Each project is a dict with id, name and color. Each task is a dict with id, title, project,
    status (one a Line indicates) and since, the time of its status. A task is on turn '1' and its
    wave epoch is `since`, so the map shows it as though a worker had already recorded it.
    """
    for project in projects:
        db.execute('INSERT INTO projects (id,name,color,roots) VALUES (?,?,?,?)',
                   (project['id'], project['name'], project['color'], '[]'))
    for task in tasks:
        if task['status'] not in wall.STATUSES:
            raise ValueError('A synthetic task needs a status a Line indicates.')
        db.execute('INSERT INTO sessions (id,turn,status,updated) VALUES (?,?,?,?)', (task['id'], '1', task['status'], task['since']))
        db.execute('INSERT INTO activity (session,turn,status,started) VALUES (?,?,?,?)', (task['id'], '1', task['status'], task['since']))
        db.execute('INSERT INTO task_info (session,title,cwd,project,manual_project,turn,started) VALUES (?,?,?,?,?,?,?)',
                   (task['id'], task['title'], '', task['project'], None, '1', task['since']))
