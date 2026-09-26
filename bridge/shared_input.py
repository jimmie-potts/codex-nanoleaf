"""Nanoleaf presentation of validated shared state; no provider interpretation."""
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parent / 'vendor/agent-state-1.0.0/package'


def validate_snapshot(value):
    # Legacy startup does not need the optional schema dependency.
    location = str(PACKAGE / 'python')
    if location not in sys.path:
        sys.path.insert(0, location)
    from agent_state import validate_snapshot as validate
    if type(value) is not dict or value.get('apiVersion') != '1.1':
        return validate(value)
    revision=value.get('revision');sessions=value.get('sessions')
    if (type(revision) is not int or not 0 <= revision <= 9007199254740991
            or type(sessions) is not list or len(sessions)>128):
        return {'ok':False,'code':'invalid-snapshot'}
    generations=[];legacy=[]
    for session in sessions:
        if (type(session) is not dict or type(session.get('generation')) is not int
                or not 0 <= session['generation'] <= revision):
            return {'ok':False,'code':'invalid-snapshot'}
        generations.append(session['generation'])
        legacy.append({key:item for key,item in session.items() if key!='generation'})
    # All other fields have the closed 1.0 shape. Its pinned validator returns
    # a detached copy; only the independently checked generation is restored.
    checked=validate(dict(value,apiVersion='1.0',sessions=legacy))
    if checked['ok']:
        checked['value']['apiVersion']='1.1'
        for session,generation in zip(checked['value']['sessions'],generations):
            session['generation']=generation
    return checked

import contextlib
import hashlib
import http.client
import json
import os
import re
import socket
import sqlite3
import stat
import threading
import time
from urllib.parse import urlsplit

MAX_RESPONSE = 16 * 1024 * 1024
TIMEOUT = 2.5
IDENTITY = ('provider', 'client', 'hostId', 'sourceId', 'sessionId')
SOURCE = IDENTITY[:-1]
ID = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')


class FeedError(ValueError):
    """Fixed codes only, never host error text or response content."""


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise FeedError('invalid-json')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(FeedError('invalid-json')))
    except (ValueError, UnicodeError, RecursionError):
        raise FeedError('invalid-json') from None


def identity_key(identity):
    return 'shared-' + hashlib.sha256(dumps([identity[k] for k in IDENTITY]).encode()).hexdigest()


def valid_identity(value, fields=IDENTITY):
    return (type(value) is dict and set(value) == set(fields)
            and all(type(value[k]) is str and ID.fullmatch(value[k]) for k in fields)
            and ((value['provider'] == 'codex' and value['client'] in ('cli', 'desktop'))
                 or (value['provider'] == 'claude' and value['client'] == 'code')))


def validate_config(value):
    try:
        if (type(value) is not dict or set(value) - {'version','ownerId','consumerId','endpoint','tokenFile',
                'controlTokenFile','clearOnNewTurn','qualifiedSources','bindings'}
                or type(value['version']) is not int or value['version'] != 1
                or value['clearOnNewTurn'] is not True
                or any(type(value[k]) is not str or not ID.fullmatch(value[k]) for k in ('ownerId','consumerId'))):
            raise FeedError('invalid-config')
        endpoint = value['endpoint']
        url = urlsplit(endpoint)
        if (type(endpoint) is not str or len(endpoint) > 256 or url.scheme != 'http'
                or url.hostname != '127.0.0.1' or not url.port or url.username or url.password
                or url.query or url.fragment or url.path != '/api/monitor/v1'
                or endpoint != f'http://127.0.0.1:{url.port}/api/monitor/v1'):
            raise FeedError('invalid-config')
        for key in ('tokenFile','controlTokenFile'):
            if key in value and (type(value[key]) is not str or not Path(value[key]).is_absolute()):
                raise FeedError('invalid-config')
        if 'tokenFile' not in value:
            raise FeedError('invalid-config')
        sources = value['qualifiedSources']
        bindings = value.get('bindings', [])
        if (type(sources) is not list or not 1 <= len(sources) <= 128
                or any(not valid_identity(source, SOURCE) for source in sources)
                or len({dumps(source) for source in sources}) != len(sources)
                or type(bindings) is not list or len(bindings) > 128):
            raise FeedError('invalid-config')
        keys, locals_ = set(), set()
        for binding in bindings:
            if (type(binding) is not dict or set(binding) != {'identity','legacySessionId'}
                    or not valid_identity(binding['identity']) or type(binding['legacySessionId']) is not str
                    or not ID.fullmatch(binding['legacySessionId']) or binding['legacySessionId'].startswith('shared-')):
                raise FeedError('invalid-config')
            key = identity_key(binding['identity'])
            if key in keys or binding['legacySessionId'] in locals_:
                raise FeedError('invalid-config')
            keys.add(key); locals_.add(binding['legacySessionId'])
        return decode(dumps(dict(value, bindings=bindings)))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise FeedError('invalid-config') from None


def private_read(path, maximum):
    """Bound regular-file reads; reject symlinks, FIFOs and exposed POSIX secrets."""
    try:
        flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, 'rb') as file:
            info = os.fstat(file.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_size > maximum
                    or info.st_mode & 0o077 or info.st_uid != os.getuid()):
                raise FeedError('private-file-unavailable')
            raw = file.read(maximum + 1)
            if len(raw) > maximum:
                raise FeedError('private-file-unavailable')
            return raw
    except OSError:
        raise FeedError('private-file-unavailable') from None


def request(config, suffix, body=None, control=False):
    config = validate_config(config)
    try:
        token = private_read(config.get('controlTokenFile') if control else config['tokenFile'], 128).decode('ascii').strip() if not control or config.get('controlTokenFile') else None
    except UnicodeError:
        raise FeedError('credential-unavailable') from None
    if not token or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise FeedError('credential-unavailable')
    url = urlsplit(config['endpoint'])
    connection = http.client.HTTPConnection('127.0.0.1', url.port, timeout=TIMEOUT)
    expired = threading.Event()
    sockets = []
    def abort():
        expired.set()
        sock = sockets[0] if sockets else connection.sock
        if sock:
            try: sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            sock.close()
    timer = threading.Timer(TIMEOUT, abort); timer.daemon = True
    try:
        timer.start()
        connection.connect()
        sockets.append(connection.sock)
        if expired.is_set():
            raise FeedError('feed-unavailable')
        headers = {'Authorization': 'Bearer ' + token, 'X-Pixoo-Request': '1', 'Content-Type':'application/json'}
        connection.request('GET' if body is None else 'POST', url.path + suffix,
                           body=None if body is None else dumps(body).encode(), headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise FeedError('feed-rejected')
        if response.getheader('Content-Encoding') not in (None, 'identity'):
            raise FeedError('invalid-feed')
        length = response.getheader('Content-Length')
        if length is not None and (not length.isdecimal() or int(length) > MAX_RESPONSE):
            raise FeedError('feed-limit')
        raw = response.read(MAX_RESPONSE + 1)
        if expired.is_set() or len(raw) > MAX_RESPONSE:
            raise FeedError('feed-limit')
        return decode(raw)
    except FeedError:
        raise
    except (OSError, ValueError, http.client.HTTPException, UnicodeError):
        raise FeedError('feed-unavailable') from None
    finally:
        timer.cancel(); connection.close()


def check_envelope(value, config, minimum_revision=0):
    fields = {'apiVersion','ownerId','connection','snapshot','admissionRejected','nextRequestId'}
    if (type(value) is not dict or set(value) != fields or value['apiVersion'] != '1.0'
            or value['ownerId'] != config['ownerId'] or value['connection'] != 'current'
            or type(value['admissionRejected']) is not int or not 0 <= value['admissionRejected'] <= 9007199254740991
            or type(value['nextRequestId']) is not str or not 1 <= len(value['nextRequestId']) <= 100):
        raise FeedError('invalid-feed')
    checked = validate_snapshot(value['snapshot'])
    if not checked['ok'] or checked['value']['apiVersion']!='1.1' or checked['value']['revision'] < minimum_revision:
        raise FeedError('invalid-feed')
    return dict(value, snapshot=checked['value'])


def declared(snapshot, config):
    """Keep sessions from declared sources. Others are counted, never presented or
    acknowledged, and take no part in parent grouping."""
    sources = {dumps(source) for source in config['qualifiedSources']}
    kept, skipped = [], []
    for session in snapshot['sessions']:
        source = dumps({k: session['identity'][k] for k in SOURCE})
        if source in sources: kept.append(session)
        else: skipped.append(source)
    return dict(snapshot, sessions=kept), {'sessions': len(skipped), 'sources': [decode(source) for source in sorted(set(skipped))]}


def fetch_snapshot(config, minimum_revision=0):
    config = validate_config(config)
    return check_envelope(request(config, '/sessions?snapshotVersion=1.1'), config, minimum_revision)

import devices
import project_map as wall
from store import control_state, mark_dirty

# All tables are local presentation/configuration, never another agent reducer.
TABLES = ('sessions','slots','waits','activity','receipts','comets','task_info')
DEFAULT_DEVICE = devices.DEFAULT  # The original Lines device.


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS shared_input (id INTEGER PRIMARY KEY, source TEXT, generation INTEGER, config TEXT, envelope TEXT, received REAL, connection TEXT, error TEXT, backup TEXT)')
    db.execute("INSERT OR IGNORE INTO shared_input VALUES (1,'legacy',0,NULL,NULL,NULL,'unavailable',NULL,NULL)")
    db.execute('CREATE TABLE IF NOT EXISTS shared_stale (session TEXT PRIMARY KEY)')
    db.execute('CREATE TABLE IF NOT EXISTS shared_suppressed_waves (session TEXT PRIMARY KEY, epoch REAL)')
    db.execute('CREATE TABLE IF NOT EXISTS shared_ack (id INTEGER PRIMARY KEY, payload TEXT, result TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS shared_evictions (session TEXT, device TEXT, token TEXT NOT NULL, PRIMARY KEY (session,device))')


def state(db):
    row = db.execute('SELECT source,generation,config,envelope,received,connection,error,backup FROM shared_input WHERE id=1').fetchone()
    value = dict(zip(('source','generation','config','envelope','received','connection','error','backup'), row))
    for key in ('config','envelope','backup'):
        if value[key] is not None: value[key] = decode(value[key])
    return value


def selected(db):
    row = db.execute('SELECT source FROM shared_input WHERE id=1').fetchone()
    return bool(row and row[0] == 'shared')


def visible_tasks(db, device):
    shared = selected(db)
    statuses = "'working','question','blocked','unread','idle'" if shared else "'working','question','blocked','unread'"
    excluded = 'AND NOT EXISTS (SELECT 1 FROM shared_evictions WHERE session=sessions.id AND device=?) ' if shared else ''
    return db.execute('SELECT id,turn,status FROM sessions WHERE status IN (' + statuses + ') ' + excluded +
                      "ORDER BY CASE status WHEN 'blocked' THEN 0 WHEN 'question' THEN 1 ELSE 2 END, updated, id",
                      (device,) if shared else ()).fetchall()


def eviction_token(current, session):
    """A stale-view guard, not an authentication credential or lifecycle event."""
    return hashlib.sha256(dumps([current['config']['ownerId'], current['generation'],
                                 session['identity'], session.get('generation', 0), session['turn']]).encode()).hexdigest()


def evict(db, device, payload):
    if (set(payload) != {'id','evictionToken'} or not isinstance(payload['id'], str)
            or not isinstance(payload['evictionToken'], str) or not selected(db)):
        raise ValueError('Invalid eviction.')
    current = state(db)
    tasks = presented(current['envelope']['snapshot']) if current['envelope'] else {}
    key = payload['id']
    if (key not in tasks or payload['evictionToken'] != eviction_token(current, tasks[key][0])
            or not db.execute('SELECT 1 FROM sessions WHERE id=?', (key,)).fetchone()):
        raise ValueError('Task changed. Refresh before evicting.')
    db.execute('INSERT OR REPLACE INTO shared_evictions VALUES (?,?,?)', (key,device,payload['evictionToken']))
    for table in ('slots','comets'):
        db.execute('DELETE FROM '+table+' WHERE session=? AND device=?', (key,device))


def dump_tables(db):
    return {table: [list(row) for row in db.execute('SELECT * FROM ' + table)] for table in TABLES}


def restore_tables(db, saved):
    for table in TABLES:
        db.execute('DELETE FROM ' + table)
        legacy = devices.REBUILT.get(table)
        for row in saved[table]:
            columns = ''
            if legacy and len(row) == legacy.count(',') + 1:
                # A backup taken before the device key existed restores to the original device.
                columns = ' (' + legacy + ')'
            db.execute('INSERT INTO ' + table + columns + ' VALUES (' + ','.join('?' for _ in row) + ')', row)


def bound_preferences(db, config):
    result = {}
    for binding in config['bindings']:
        key = identity_key(binding['identity'])
        info = db.execute('SELECT project,manual_project FROM task_info WHERE session=?', (key,)).fetchone()
        # One placement per device; switching keeps each device's bound placement.
        placed = db.execute('SELECT device,slot FROM slots WHERE session=? ORDER BY device', (key,)).fetchall()
        result[binding['legacySessionId']] = (info, placed)
    return result


ALERTS = {'blocked': {'approval','input'}, 'question': {'question'}}
RANK = {'idle': 0, 'unread': 1, 'working': 2, 'question': 3, 'blocked': 4}


def semantic_status(session, consumer, children=()):
    # Subagent attention and owner-counted fresh activity belong to the parent task;
    # a subagent's own turn-ended notices are not task completions.
    kinds = {attention['kind'] for item in (session, *children) for attention in item['attention']}
    if kinds & ALERTS['blocked']: return 'blocked'
    if kinds & ALERTS['question']: return 'question'
    if session['activity'] == 'active' or any(item['children']['active'] for item in (session, *children)): return 'working'
    if session['read'] != 'read' and any(consumer not in notice['acknowledgedBy'] for notice in session['notices']):
        return 'unread'
    return 'idle'


def _parent_key(session):
    if session['parent']['status'] != 'known' or any(
            item['dimension'] == 'parent' and item['reason'] == 'ambiguous' for item in session['unavailable']):
        return None
    return identity_key(session['parent']['identity'])


def presented(snapshot):
    """Task key -> (session, included subagent sessions, orphan). A child joins its topmost
    ancestor in the snapshot, as legacy hooks attributed subagent events to the parent
    session. A group whose top has a missing parent, or a parent cycle keyed by its
    smallest member, is an orphan presented only for its attention."""
    sessions = {identity_key(session['identity']):session for session in snapshot['sessions']}
    def top(key):
        path = [key]
        while (parent := _parent_key(sessions[path[-1]])) in sessions:
            if parent in path: return min(path[path.index(parent):])
            path.append(parent)
        return path[-1]
    tasks = {}
    for key in sessions:
        root = top(key)
        entry = tasks.setdefault(root, (sessions[root], [], _parent_key(sessions[root]) is not None))
        if key != root: entry[1].append(sessions[key])
    return tasks


def _supporters(session, children, status, retained=False):
    """Task members whose evidence supplies a status. For a retained status, a silent child
    that still reports activity counts too, so its later current evidence can clear it."""
    if status in ALERTS:
        return [item for item in (session, *children) if ALERTS[status] & {a['kind'] for a in item['attention']}]
    if status == 'working':
        return [session] * (session['activity'] == 'active') + [child for child in children if child['activity'] == 'active'
                                                                and (retained or child['freshness'] == 'current')]
    return [session]


def _forget_task(db, key):
    for table,column in (('sessions','id'),('activity','session'),('task_info','session'),
                         ('comets','session'),('slots','session'),('waits','session'),
                         ('receipts','session'),('shared_stale','session'),('shared_suppressed_waves','session'),
                         ('shared_evictions','session')):
        db.execute('DELETE FROM '+table+' WHERE '+column+'=?',(key,))


def project_envelope(db, envelope, config, instant, resync=False, targets=(DEFAULT_DEVICE,), metadata=None):
    """Project a checked envelope into local task state inside the caller's transaction."""
    current = state(db)
    previous = current['envelope']
    # The stored envelope holds only declared sessions, plus a local count of the skipped ones.
    snapshot, skipped = declared(envelope['snapshot'], config)
    envelope = dict(envelope, snapshot=snapshot, skipped=skipped)
    prior = {identity_key(s['identity']):s for s in previous['snapshot']['sessions']} if previous else {}
    resync = (resync or not previous or current['connection'] != 'current'
              or snapshot['revision'] > previous['snapshot']['revision'] + 1
              or snapshot['lossCount'] != previous['snapshot']['lossCount']
              or envelope['admissionRejected'] != previous['admissionRejected'])
    if resync:
        db.execute("INSERT OR REPLACE INTO meta VALUES ('shared_wave_cutoff',?)", (str(instant),))
    presentation_changed = metadata.sync_catalog(db) if metadata else False
    live = set()
    prior_tasks = presented(previous['snapshot']) if previous else {}
    for key, (session, children, orphan) in presented(snapshot).items():
        status = semantic_status(session, config['consumerId'], children)
        if orphan and status not in ALERTS: continue
        live.add(key)
        token = eviction_token(current, session)
        db.execute('DELETE FROM shared_evictions WHERE session=? AND token!=?', (key,token))
        recreated=key in prior and session['generation']!=prior[key].get('generation',0)
        if recreated:
            _forget_task(db,key)
            prior.pop(key);prior_tasks.pop(key,None)
        task_resync=resync or recreated
        old = db.execute('SELECT turn,status FROM sessions WHERE id=?', (key,)).fetchone()
        old_activity = db.execute('SELECT turn,status,started FROM activity WHERE session=?', (key,)).fetchone()
        turn = session['turn'].get('id', '')
        # A task is current when current evidence supplies its displayed status.
        supporters = _supporters(session, children, status)
        stale = snapshot['collector'] != 'running' or not any(item['freshness'] == 'current' for item in supporters)
        prior_session = prior.get(key)
        prior_blocked = prior_session and any(item['kind'] == 'approval' and item['id']['status'] == 'unknown'
                                             for member in (prior_session, *prior_tasks.get(key, (None, []))[1])
                                             for item in member['attention'])
        owner_cleared_block = (prior_blocked and old and old[1] == 'blocked' and status != 'blocked'
                               and prior_session['turn'] == session['turn']
                               and snapshot['revision'] > previous['snapshot']['revision'])
        # Current members that supplied the retained status and no longer do clear it, and a
        # higher subagent alert is shown steadily rather than hidden behind an older color.
        members = {identity_key(item['identity']):item for item in (session, *children)}
        prior_support = ({identity_key(item['identity']) for item in _supporters(*prior_tasks[key][:2], old[1], retained=True)}
                         if old and key in prior_tasks and old[1] != status else set())
        still = {identity_key(item['identity']) for item in _supporters(session, children, old[1])} if old else set()
        evidence_cleared = bool(prior_support) and all(
            member in members and members[member]['freshness'] == 'current' and member not in still for member in prior_support)
        child_alert = (bool(old) and status in ALERTS and RANK[status] > RANK.get(old[1], 0)
                       and any(item is not session for item in supporters))
        # Owner read evidence, or this consumer's acknowledgment of every notice, clears a
        # retained unread task even while its lifecycle evidence is stale.
        unread_cleared = bool(old) and old[1] == 'unread' and status == 'idle'
        if stale and old and not (owner_cleared_block or evidence_cleared or child_alert or unread_cleared):
            turn, status = old
        was_stale = bool(db.execute('SELECT 1 FROM shared_stale WHERE session=?', (key,)).fetchone())
        if stale: db.execute('INSERT OR IGNORE INTO shared_stale VALUES (?)', (key,))
        else: db.execute('DELETE FROM shared_stale WHERE session=?', (key,))
        changed = old != (turn,status)
        if changed:
            db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)', (key,turn,status,instant))
            if status in wall.STATUSES:
                # A retained matching phase survives cutover and resync. New resync states
                # use an expired wave epoch; ordinary current transitions get one wave.
                epoch = (old_activity[2] if old_activity and old_activity[:2] == (turn,status)
                         else instant - 10 if task_resync or stale or was_stale else instant)
                db.execute('INSERT OR REPLACE INTO activity VALUES (?,?,?,?)', (key,turn,status,epoch))
            else: db.execute('DELETE FROM activity WHERE session=?', (key,))
            if (old and old[0] != turn) or session['activity'] in ('active','interrupted'):
                db.execute('DELETE FROM comets WHERE session=?', (key,))
            else:
                db.execute('DELETE FROM comets WHERE session=? AND started IS NULL', (key,))
        if stale or was_stale:
            db.execute('INSERT OR REPLACE INTO shared_suppressed_waves SELECT session,started FROM activity WHERE session=?', (key,))
        if stale or task_resync or was_stale:
            db.execute('DELETE FROM comets WHERE session=?', (key,))
        elif changed and status == 'unread' and key in prior:
            old_notices = {n['id'] for n in prior[key]['notices']}
            if any(n['id'] not in old_notices and config['consumerId'] not in n['acknowledgedBy'] for n in session['notices']):
                for device in targets:
                    if (control_state(db, device)['mode'] == 'work'
                            and not db.execute('SELECT 1 FROM shared_evictions WHERE session=? AND device=?', (key,device)).fetchone()):
                        db.execute('INSERT OR IGNORE INTO comets (session,turn,queued,source,started,device) VALUES (?,?,?,NULL,NULL,?)', (key,turn,instant,device))
        project = 'shared-project-' + session['projectId'] if session.get('projectId') else None
        if project:
            db.execute('INSERT OR IGNORE INTO projects VALUES (?,?,?,?)', (project,session['projectId'],wall.default_color(project),'[]'))
        existing = db.execute('SELECT title,cwd,project,manual_project,turn,started FROM task_info WHERE session=?', (key,)).fetchone()
        identity=session['identity']
        local_title,local_project=('',None)
        if metadata and identity['provider']=='codex':
            local_title,local_project=metadata.lookup(db,identity['sessionId'])
        title=session.get('label') or local_title or wall.fallback_title(identity['provider'],identity['sessionId'])
        manual = existing[3] if existing else None
        started = existing[5] if existing and existing[4] == turn else (instant if not task_resync and turn else None)
        details=(title,'',project or local_project,manual,turn,started)
        if existing != details:
            db.execute('INSERT OR REPLACE INTO task_info VALUES (?,?,?,?,?,?,?)', (key,*details))
            presentation_changed=True
    for (key,) in db.execute('SELECT id FROM sessions').fetchall():
        if key not in live:
            _forget_task(db,key)
    db.execute("UPDATE shared_input SET envelope=?,received=?,connection='current',error=NULL WHERE id=1", (dumps(envelope),instant))
    if previous != envelope or presentation_changed: mark_dirty(db)


def inspect(directory, now=time.time):
    path = Path(directory) / 'status.sqlite'
    default = {'source':'legacy','configured':False,'connection':'unavailable','ownerId':None,
               'consumerId':None,'revision':None,'receivedAt':None,'error':None,'sessions':[],
               'skipped':{'sessions':0,'sources':[]}}
    if not path.exists(): return default
    try:
        with contextlib.closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='shared_input'").fetchone(): return default
            current=state(db)
            config=current['config']; envelope=current['envelope']; instant=now()
            view=dict(default,source=current['source'],configured=config is not None,connection=current['connection'],error=current['error'])
            if config: view.update(ownerId=config['ownerId'],consumerId=config['consumerId'],clearOnNewTurn=True,readiness='operator-declared')
            if envelope:
                elapsed = instant-current['received']
                disconnected=elapsed < 0 or elapsed > 4 or current['connection'] != 'current'
                if disconnected and current['source']=='shared': view['connection']='stale'
                snap=envelope['snapshot']; view.update(revision=snap['revision'],receivedAt=current['received'],collector=snap['collector'],lossCount=snap['lossCount'])
                # Envelopes stored before #111 never held an undeclared session.
                view['skipped']=envelope.get('skipped',default['skipped'])
                for session in snap['sessions']:
                    age=session['observationAgeMs']+max(0,elapsed)*1000
                    view['sessions'].append({'id':identity_key(session['identity']),'identity':session['identity'],
                        'projectId':session.get('projectId'),'read':session['read'],'activity':session['activity'],
                        'attention':session['attention'],'notices':session['notices'],'unavailable':session['unavailable'],
                        'observationAgeMs':age,
                        'freshness':'uncertain' if disconnected or snap['collector'] != 'running' or session['freshness']=='uncertain' or age>=300000 else 'current'})
            return view
    except (sqlite3.Error, ValueError, KeyError, TypeError):
        return dict(default,error='local-state-unavailable')


def render_config(db, config):
    device = config.get('device', DEFAULT_DEVICE)
    config['_steady_slots'] = [slot for (slot,) in db.execute("SELECT slot FROM slots JOIN sessions ON sessions.id=slots.session WHERE slots.device=? AND (sessions.status='idle' OR EXISTS (SELECT 1 FROM shared_stale WHERE shared_stale.session=slots.session))", (device,))]
    config['_wave_suppressed_slots'] = [slot for (slot,) in db.execute('SELECT slot FROM slots JOIN shared_suppressed_waves USING (session) JOIN activity USING (session) WHERE epoch=started AND slots.device=?', (device,))]
    row = db.execute("SELECT value FROM meta WHERE key='shared_wave_cutoff'").fetchone()
    if row: config['_wave_cutoff'] = max(config.get('_wave_cutoff',float('-inf')),float(row[0]))
