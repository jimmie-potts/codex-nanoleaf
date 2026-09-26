"""Choosing and following the task source: legacy hooks or the shared feed.

Each operation opens and commits its own transaction. shared_input owns the feed contract and its
projection into local state; this module owns configuration, switching, polling and
acknowledgments around it.
"""
import contextlib
import json
import os
from pathlib import Path
import sqlite3
import time

import codex_hooks
import configuration
import database
import launcher
import project_map as wall
import shared_input
from store import mark_dirty


def configure(directory, config):
    config = shared_input.validate_config(config)
    with contextlib.closing(database.connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        if shared_input.selected(db): raise shared_input.FeedError('select-legacy-before-configure')
        if db.execute('SELECT 1 FROM shared_ack WHERE result IS NULL').fetchone():
            raise shared_input.FeedError('acknowledgment-pending-use-explicit-retry')
        db.execute('UPDATE shared_input SET config=?,generation=generation+1,envelope=NULL,received=NULL,connection=\'unavailable\',error=NULL WHERE id=1', (shared_input.dumps(config),))
        db.execute('DELETE FROM shared_ack')
        db.execute('DELETE FROM shared_evictions')


def source_config(directory):
    with contextlib.closing(database.connect_state(directory)) as db:
        value = shared_input.state(db)
    if not value['config']: raise shared_input.FeedError('not-configured')
    return value


def preflight(directory, fetch=None):
    value = source_config(directory)
    minimum = value['envelope']['snapshot']['revision'] if value['envelope'] else 0
    result = shared_input.check_envelope((fetch or shared_input.fetch_snapshot)(value['config'], minimum_revision=minimum), value['config'], minimum)
    if result['snapshot']['collector'] != 'running': raise shared_input.FeedError('collector-unavailable')
    return value, result


def metadata_reader(directory):
    # Read configuration only; device-aware load_config can perform network I/O.
    try:
        config=json.loads((Path(directory)/'config.json').read_text(encoding='utf-8-sig'))
        if not isinstance(config,dict): config={}
    except (OSError,ValueError):
        config={}
    return wall.Metadata(directory,config)


def select_source(directory, source, fetch=None, now=time.time):
    if source not in ('legacy','shared'): raise shared_input.FeedError('invalid-source')
    if source == 'legacy':
        home = os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))
        if not codex_hooks.has_legacy_hooks(home):
            raise shared_input.FeedError('Legacy hooks are missing; run hooks register --codex-home <path> before selecting legacy.')
    before = source_config(directory)
    if before['source'] == source: return
    envelope = preflight(directory, fetch)[1] if source == 'shared' else None
    instant = now()
    metadata = metadata_reader(directory) if source == 'shared' else None
    if metadata: metadata.refresh()
    with contextlib.closing(database.connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        current = shared_input.state(db)
        if current['generation'] != before['generation']: raise shared_input.FeedError('selection-changed')
        if db.execute('SELECT 1 FROM comets WHERE started IS NOT NULL LIMIT 1').fetchone():
            raise shared_input.FeedError('active-comet')
        config = current['config']
        if source == 'shared':
            saved = shared_input.dump_tables(db)
            # Copy only explicitly bound local presentation continuity.
            bindings = {item['legacySessionId']: shared_input.identity_key(item['identity']) for item in config['bindings']}
            transferred = {table: [] for table in shared_input.TABLES}
            for table in ('slots','activity','task_info'):
                for row in saved[table]:
                    if row[0] in bindings:
                        transferred[table].append([bindings[row[0]], *row[1:]])
            shared_input.restore_tables(db, transferred)
            db.execute('UPDATE shared_input SET backup=?,source=\'shared\',generation=generation+1,envelope=NULL,connection=\'unavailable\' WHERE id=1', (shared_input.dumps(saved),))
            db.execute('DELETE FROM shared_stale')
            shared_input.project_envelope(db, envelope, config, instant, resync=True, targets=configuration.registered_devices(directory), metadata=metadata)
        else:
            prefs = shared_input.bound_preferences(db, config)
            shared_input.restore_tables(db, current['backup'])
            # Release old slots before applying the complete remap to avoid swaps colliding.
            for session in prefs: db.execute('DELETE FROM slots WHERE session=?', (session,))
            for session, (info, placed) in prefs.items():
                if info: db.execute('UPDATE task_info SET project=?,manual_project=? WHERE session=?', (*info, session))
                for device, slot in placed:
                    db.execute('DELETE FROM slots WHERE slot=? AND device=?', (slot, device))
                    db.execute('INSERT INTO slots (session, slot, device) VALUES (?,?,?)', (session, slot, device))
            db.execute('DELETE FROM comets')
            db.execute('DELETE FROM receipts')
            db.execute('DELETE FROM shared_stale')
            db.execute('INSERT INTO shared_stale SELECT id FROM sessions')
            db.execute("UPDATE shared_input SET source='legacy',generation=generation+1,connection='unavailable',error=NULL WHERE id=1")
        db.execute('DELETE FROM shared_suppressed_waves')
        db.execute('DELETE FROM shared_evictions')
        # Switching the task source resets every device's comets and display cache.
        db.execute('DELETE FROM display_v3')
        mark_dirty(db)


def accept(directory, envelope, now=time.time, generation=None, resync=False, metadata=None):
    metadata = metadata if metadata is not None else metadata_reader(directory)
    metadata.refresh()
    with contextlib.closing(database.connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE'); current = shared_input.state(db)
        if current['source'] != 'shared' or generation is not None and current['generation'] != generation:
            return False
        minimum = current['envelope']['snapshot']['revision'] if current['envelope'] else 0
        envelope = shared_input.check_envelope(envelope, current['config'], minimum)
        shared_input.project_envelope(db,envelope,current['config'],now(),resync,targets=configuration.registered_devices(directory),metadata=metadata)
        return True


def failed(directory, generation, code='feed-unavailable'):
    with contextlib.closing(database.connect_state(directory)) as db, db:
        db.execute('BEGIN IMMEDIATE'); current=shared_input.state(db)
        if current['source'] != 'shared' or current['generation'] != generation: return
        db.execute("UPDATE shared_input SET connection=?,error=? WHERE id=1", ('stale' if current['envelope'] else 'unavailable', code))
        db.execute('INSERT OR IGNORE INTO shared_stale SELECT id FROM sessions')
        db.execute('DELETE FROM comets')
        mark_dirty(db)


class Poller:
    """One bounded request at a time, owned by the existing worker lock."""
    def __init__(self, directory, metadata=None):
        self.metadata=metadata if metadata is not None else metadata_reader(directory)
        self.directory=directory; self.next_at=0; self.first=True; self.generation=None

    def tick(self, instant):
        with contextlib.closing(database.connect_state(self.directory)) as db:
            current=shared_input.state(db)
        if current['source'] != 'shared':
            self.first=True; self.generation=None
            return False
        if self.generation != current['generation']:
            self.first=True;self.next_at=0;self.generation=current['generation']
        if instant < self.next_at: return True
        self.next_at=instant+1
        try:
            minimum=current['envelope']['snapshot']['revision'] if current['envelope'] else 0
            envelope=shared_input.fetch_snapshot(current['config'],minimum_revision=minimum)
            accept(self.directory,envelope,now=lambda:instant,generation=self.generation,resync=self.first,metadata=self.metadata)
            self.first=False
        except shared_input.FeedError as error:
            failed(self.directory,self.generation,str(error))
            self.first=True
        return True


def acknowledge(directory, session_key, notice_id, retry=False):
    before=source_config(directory)
    if before['source'] != 'shared' or not before['config'].get('controlTokenFile'):
        raise shared_input.FeedError('acknowledgment-unavailable')
    with contextlib.closing(database.connect_state(directory)) as db:
        pending=db.execute('SELECT payload,result FROM shared_ack WHERE id=1').fetchone()
    if pending and pending[1] is None:
        body=shared_input.decode(pending[0])
        if not retry or shared_input.identity_key(body['identity']) != session_key or body['noticeId'] != notice_id:
            raise shared_input.FeedError('acknowledgment-pending-use-explicit-retry')
    else:
        if retry: raise shared_input.FeedError('no-pending-acknowledgment')
        envelope=shared_input.fetch_snapshot(before['config'],minimum_revision=before['envelope']['snapshot']['revision'])
        sessions=shared_input.declared(envelope['snapshot'],before['config'])[0]['sessions']
        session=next((s for s in sessions if shared_input.identity_key(s['identity'])==session_key),None)
        if not session or not any(n['id']==notice_id for n in session['notices']): raise shared_input.FeedError('notice-unavailable')
        body={'operation':'acknowledge','requestId':envelope['nextRequestId'],'identity':session['identity'],
              'noticeId':notice_id,'consumerId':before['config']['consumerId']}
        with contextlib.closing(database.connect_state(directory)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            if shared_input.state(db)['generation']!=before['generation']:raise shared_input.FeedError('selection-changed')
            if db.execute('SELECT 1 FROM shared_ack WHERE result IS NULL').fetchone():raise shared_input.FeedError('acknowledgment-pending-use-explicit-retry')
            db.execute('INSERT OR REPLACE INTO shared_ack VALUES (1,?,NULL)',(shared_input.dumps(body),))
    result=shared_input.request(before['config'],'/commands',body,control=True)
    if not (type(result) is dict and type(result.get('ok')) is bool):raise shared_input.FeedError('invalid-acknowledgment')
    if result['ok']:
        if (set(result)!={'ok','revision','outcome'} or type(result['revision']) is not int
                or not 0<=result['revision']<=9007199254740991 or result['outcome'] not in ('applied','duplicate','stale','ambiguous')):
            raise shared_input.FeedError('invalid-acknowledgment')
    elif set(result)!={'ok','code'} or result['code'] not in ('invalid-event','invalid-operation','capacity','unavailable','storage-failed'):
        raise shared_input.FeedError('invalid-acknowledgment')
    with contextlib.closing(database.connect_state(directory)) as db,db:
        db.execute('UPDATE shared_ack SET result=? WHERE payload=?',(shared_input.dumps(result),shared_input.dumps(body)))
    return result


def command(argv, launch=None):
    """`bridge.py shared-*`; launch wakes the workers after a source switch."""
    import argparse
    parser=argparse.ArgumentParser(description='Select and inspect shared Nanoleaf task input.')
    parser.add_argument('command',choices=('shared-configure','shared-preflight','shared-select','shared-status','shared-acknowledge'))
    parser.add_argument('source',nargs='?',choices=('legacy','shared'))
    parser.add_argument('--state-dir',type=Path)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--session');parser.add_argument('--notice');parser.add_argument('--retry',action='store_true')
    args=parser.parse_args(argv); directory=args.state_dir or configuration.data_dir()
    try:
        if args.command=='shared-status':
            result=shared_input.inspect(directory)
        elif args.command=='shared-configure':
            if not args.config:raise shared_input.FeedError('configuration-file-required')
            config=shared_input.decode(shared_input.private_read(args.config,65536));configure(directory,config)
            result=shared_input.inspect(directory)
        elif args.command=='shared-preflight':
            _,envelope=preflight(directory)
            result={'feed':'verified','ownerId':envelope['ownerId'],'revision':envelope['snapshot']['revision'],
                    'producerReadiness':'operator-declared','clearOnNewTurn':'operator-declared-true'}
        elif args.command=='shared-select':
            if args.source is None:raise shared_input.FeedError('source-required')
            select_source(directory,args.source)
            (launch or launcher.launch_worker)(directory)
            # Switching the task source resets comets and display caches on every device.
            result=dict(shared_input.inspect(directory),resetDevices='all')
        else:
            if not args.session or not args.notice:raise shared_input.FeedError('notice-required')
            result=acknowledge(directory,args.session,args.notice,retry=args.retry)
        print(shared_input.dumps(result))
    except shared_input.FeedError as error:
        if str(error).startswith('Legacy hooks are missing; run hooks register'):
            print(shared_input.dumps({'error':'legacy-hooks-missing','message':'Run hooks register --codex-home <path> before selecting legacy.'}))
            raise SystemExit(1)
        print(shared_input.dumps({'error':'shared-input-operation-failed'}))
        raise SystemExit(1)
    except (ImportError,OSError,sqlite3.Error,UnicodeError):
        # Fixed output, including configuration paths and dependency failures.
        print(shared_input.dumps({'error':'shared-input-operation-failed'}))
        raise SystemExit(1)
