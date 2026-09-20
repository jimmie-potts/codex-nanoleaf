"""Nanoleaf-owned configuration extension; never a light transport."""
import contextlib
import hashlib
import hmac
import json
import re
import time

import controller_state as state
import project_map as wall
import shared_input

VERSION = 'nanoleaf.integration/1.0'
MAX_ITEMS = 1000
MAX_RECEIPTS = 256
MAX_BODY = 65536
MAX_SEQUENCE = 9007199254740991
OPERATIONS = ('settings.set', 'elements.assign', 'task.assign', 'project.color')


class Failure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS integration_meta (id INTEGER PRIMARY KEY, sequence INTEGER NOT NULL)')
    db.execute('INSERT OR IGNORE INTO integration_meta VALUES (1,0)')
    db.execute('CREATE TABLE IF NOT EXISTS integration_requests (sequence INTEGER PRIMARY KEY, principal TEXT, request TEXT, receipt TEXT, phase TEXT, created REAL, revision TEXT)')


def groups(directory):
    # Read only the saved physical mapping, never load_config's geometry discovery.
    raw = (directory / 'layout.json').read_bytes()
    if len(raw) > MAX_BODY:
        raise Failure('capacity')
    value = json.loads(raw)['line_groups']
    if (not isinstance(value, list) or not 1 <= len(value) <= 300
            or any(not isinstance(pair, list) or len(pair) != 2
                   or any(type(pid) is not int or not 0 <= pid <= 65535 for pid in pair) for pair in value)):
        raise Failure('unsupported-capability')
    ids = [pid for pair in value for pid in pair]
    if len(set(ids)) != len(ids):
        raise Failure('unsupported-capability')
    return value


def opaque(data, kind, value):
    return kind + '-' + hmac.new(data['epoch'].encode(), (kind + '\0' + value).encode(), hashlib.sha256).hexdigest()


def rows(db, query):
    result = db.execute(query + ' LIMIT 1001').fetchall()
    if len(result) > MAX_ITEMS:
        raise Failure('capacity')
    return result


def projection(db, pairs):
    data = state.read(db)
    project_rows = rows(db, 'SELECT id,color FROM projects ORDER BY id')
    task_rows = rows(db, 'SELECT session,project,manual_project FROM task_info ORDER BY session')
    projects = {opaque(data, 'project', p): p for p, _ in project_rows}
    tasks = {opaque(data, 'task', s): s for s, _, _ in task_rows}
    project_id = lambda p: opaque(data, 'project', p) if p is not None else None
    task_id = lambda s: opaque(data, 'task', s) if s is not None else None
    prefs = dict((line, (p, half)) for line, p, half in rows(db, 'SELECT line_id,project,signature FROM line_prefs ORDER BY line_id'))
    current = shared_input.state(db)
    shared = {}
    if current['source'] == 'shared' and current['envelope']:
        for session in current['envelope']['snapshot']['sessions']:
            shared[shared_input.identity_key(session['identity'])] = session
    view = dict(apiVersion=VERSION, identity=data['identity'], configurationRevision=data['revision'],
                mode=state.snapshot(db)['state']['desired']['mode']['value'],
                settings={k: v for k, v in wall.settings(db).items() if k in ('style', 'coverage')},
                source=current['source'], projects=[], tasks=[], elements=[], wallPending=bool(wall.pending(db)))
    for p, color in project_rows:
        item = dict(id=project_id(p), color=color)
        # These names originate in the qualified shared feed, never local metadata.
        if current['source'] == 'shared' and any(s.get('projectId') is not None and p == 'shared-project-' + s['projectId'] for s in shared.values()):
            item['sharedProjectId'] = p[len('shared-project-'):]
        view['projects'].append(item)
    for s, project, manual in task_rows:
        item = dict(id=task_id(s), projectId=project_id(manual or project), overrideProjectId=project_id(manual))
        if s in shared:
            item['sharedIdentity'] = shared[s]['identity']
        view['tasks'].append(item)
    for pair in pairs:
        key = wall.line_id(pair)
        project, half = prefs.get(key, (None, 0))
        view['elements'].append(dict(id=key, projectId=project_id(project), signature=half))
    # Include full private pending bytes only in the digest, never in public output.
    revision_data = dict(view, pending=wall.pending(db), sourceGeneration=current['generation'])
    view['revision'] = hashlib.sha256(state.encoded(revision_data).encode()).hexdigest()
    return view, projects, tasks


def authorize(app, db, token, device, scope, checks):
    decision = app.contract.authorize(app.facts(db, token, device, scope, **checks))['decision']
    if decision != 'allowed':
        raise Failure(decision)
    if device != state.read(db)['identity']['deviceId']:
        raise Failure('unknown-device')
    return state.credential(db, token)[0]


def snapshot(app, token, device, **checks):
    with contextlib.closing(state.readonly(app.directory)) as db:
        principal = authorize(app, db, token, device, 'read', checks)
        view, _, _ = projection(db, groups(app.directory))
        sequence = db.execute('SELECT sequence FROM integration_meta WHERE id=1').fetchone()[0]
        view['nextRequestId'] = state.ticket(state.read(db), sequence)
        view['pending'] = [json.loads(r[0]) for r in db.execute("SELECT request FROM integration_requests WHERE phase='queued' AND principal=?", (principal,))]
        view['outcomes'] = [json.loads(r[0]) for r in db.execute("SELECT receipt FROM integration_requests WHERE principal=? ORDER BY sequence DESC LIMIT 32", (principal,))]
        view['capabilities'] = {op: {'supported': True, 'scope': 'control'} for op in OPERATIONS}
        view['capabilities']['mode.set'] = {'supported': True, 'scope': 'control', 'route': '/controller/v1/commands'}
        view['limits'] = dict(maxItems=MAX_ITEMS, maxPending=1, maxReceipts=MAX_RECEIPTS, maxBodyBytes=MAX_BODY)
        return view


def valid_ticket(value):
    return (type(value) is dict and set(value) == {'epoch', 'sequence'}
            and type(value['epoch']) is str and re.fullmatch(r'[a-f0-9]{32}', value['epoch'])
            and type(value['sequence']) is int and 0 <= value['sequence'] <= MAX_SEQUENCE)


def valid_ref(value, kind, nullable=False):
    return (nullable and value is None) or (type(value) is str and bool(re.fullmatch(kind + r'-[a-f0-9]{64}', value)))


def validate(request):
    if (type(request) is not dict or set(request) != {'apiVersion', 'controllerId', 'deviceId', 'requestId', 'expectedRevision', 'command'}
            or request['apiVersion'] != VERSION or not valid_ticket(request['requestId'])
            or any(type(request[k]) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', request[k]) for k in ('controllerId', 'deviceId'))
            or type(request['expectedRevision']) is not str or not re.fullmatch(r'[a-f0-9]{64}', request['expectedRevision'])
            or type(request['command']) is not dict):
        raise Failure('invalid-request')
    c = request['command']; kind = c.get('kind')
    if kind not in OPERATIONS:
        raise Failure('unsupported-capability')
    if kind == 'settings.set':
        if (not 2 <= len(c) <= 3 or set(c) - {'kind', 'style', 'coverage'}
                or ('style' in c and c['style'] not in ('classic', 'project'))
                or ('coverage' in c and c['coverage'] not in ('whole', 'status'))):
            raise Failure('invalid-request')
    elif kind == 'elements.assign':
        if set(c) != {'kind', 'elements'} or type(c['elements']) is not list or not 1 <= len(c['elements']) <= 300:
            raise Failure('invalid-request')
        seen = set()
        for e in c['elements']:
            if (type(e) is not dict or 'id' not in e or not 2 <= len(e) <= 3 or set(e) - {'id', 'projectId', 'signature'}
                    or type(e['id']) is not str or not re.fullmatch(r'[0-9]{1,5}:[0-9]{1,5}', e['id']) or e['id'] in seen
                    or ('projectId' in e and not valid_ref(e['projectId'], 'project', nullable=True))
                    or ('signature' in e and (type(e['signature']) is not int or e['signature'] not in (0, 1)))):
                raise Failure('invalid-request')
            seen.add(e['id'])
    elif kind == 'task.assign':
        if set(c) != {'kind', 'taskId', 'projectId'} or not valid_ref(c['taskId'], 'task') or not valid_ref(c['projectId'], 'project', nullable=True):
            raise Failure('invalid-request')
    elif (set(c) != {'kind', 'projectId', 'color'} or not valid_ref(c['projectId'], 'project')
          or type(c['color']) is not str or not re.fullmatch(r'#[a-fA-F0-9]{6}', c['color'])):
        raise Failure('invalid-request')


def operation(db, pairs, command):
    _, projects, tasks = projection(db, pairs)
    def project(value):
        if value is None: return None
        if value not in projects: raise Failure('revision-conflict')
        return projects[value]
    kind = command['kind']
    if kind == 'settings.set':
        return '/api/settings', {k: v for k, v in command.items() if k != 'kind'}
    if kind == 'project.color':
        return '/api/project', dict(id=project(command['projectId']), color=command['color'])
    if kind == 'task.assign':
        if command['taskId'] not in tasks: raise Failure('revision-conflict')
        return '/api/task', dict(id=tasks[command['taskId']], project=project(command['projectId']))
    ids = {wall.line_id(pair) for pair in pairs}; lines = {}
    for e in command['elements']:
        if e['id'] not in ids: raise Failure('unsupported-capability')
        value = {}
        if 'projectId' in e: value['project'] = project(e['projectId'])
        if 'signature' in e: value['signature'] = e['signature']
        lines[e['id']] = value
    return '/api/assign', dict(lines=lines)


def finish(db, sequence, outcome, code=None):
    row = db.execute('SELECT receipt FROM integration_requests WHERE sequence=?', (sequence,)).fetchone()
    if not row: return
    receipt = json.loads(row[0]); receipt['outcome'] = outcome
    receipt['priorEffects'] = 'configuration' if outcome == 'applied' else 'none'
    if code: receipt['failure'] = {'code': code}
    db.execute("UPDATE integration_requests SET receipt=?,phase='done' WHERE sequence=?", (state.encoded(receipt), sequence))
    db.execute("DELETE FROM integration_requests WHERE phase='done' AND sequence NOT IN (SELECT sequence FROM integration_requests WHERE phase='done' ORDER BY sequence DESC LIMIT 256)")
    return receipt


def recover(db, now=None, principal=None, cancel=False):
    if not state.present(db): return
    now = time.time() if now is None else now
    stopped = state.read(db).get('stopped')
    for sequence, owner, created in list(db.execute("SELECT sequence,principal,created FROM integration_requests WHERE phase='queued'")):
        active = db.execute('SELECT active FROM controller_credentials WHERE principal=?', (owner,)).fetchone()
        if stopped or active != (1,) or (cancel and (principal is None or owner == principal)):
            finish(db, sequence, 'cancelled', 'forbidden')
        elif now - created >= 30 or now < created:
            finish(db, sequence, 'failed', 'request-expired')


def process(db, b, config, now=None):
    """Only the existing worker calls this, inside its configuration transaction."""
    if not state.present(db): return
    recover(db, now)
    row = db.execute("SELECT sequence,request,revision FROM integration_requests WHERE phase='queued'").fetchone()
    if not row: return
    sequence, raw, revision = row
    try:
        view, _, _ = projection(db, config['line_groups'])
        if view['revision'] != revision: raise Failure('revision-conflict')
        if wall.pending(db) or db.execute('SELECT 1 FROM comets WHERE started IS NOT NULL').fetchone(): return
        import wall_server
        route, payload = operation(db, config['line_groups'], json.loads(raw)['command'])
        wall_server.apply_operation(db, b, config, route, payload)
        state.changed(db)
        b.mark_dirty(db)
        finish(db, sequence, 'applied')
    except Failure as error:
        finish(db, sequence, 'failed', error.code)


def error_result(error):
    from controller_server import HTTP
    return HTTP.get(error.code, 400), {'failure': {'code': error.code}}


def receipt(app, token, device, ticket, **checks):
    with contextlib.closing(state.readonly(app.directory)) as db:
        principal = authorize(app, db, token, device, 'read', checks)
        if not valid_ticket(ticket): raise Failure('invalid-request')
        if ticket['epoch'] != state.read(db)['epoch']: raise Failure('request-expired')
        row = db.execute('SELECT principal,receipt FROM integration_requests WHERE sequence=?', (ticket['sequence'],)).fetchone()
        if not row: raise Failure('request-expired')
        if row[0] != principal: raise Failure('forbidden')
        return json.loads(row[1])


def admit(app, token, request, body_bytes=None, deadline=None, **checks):
    from controller_server import admission_transaction, check_deadline
    try:
        with admission_transaction(app.directory, deadline) as db:
            device = request.get('deviceId') if type(request) is dict else None
            principal = authorize(app, db, token, device, 'control', checks)
            if (body_bytes is not None and body_bytes > MAX_BODY) or len(state.encoded(request).encode()) > MAX_BODY: raise Failure('capacity')
            validate(request)
            data = state.read(db); ticket = request['requestId']; sequence = ticket['sequence']
            if request['controllerId'] != data['identity']['controllerId']: raise Failure('unknown-device')
            if ticket['epoch'] != data['epoch']: raise Failure('request-expired')
            row = db.execute('SELECT principal,request,receipt FROM integration_requests WHERE sequence=?', (sequence,)).fetchone()
            if row:
                if row[0] != principal: raise Failure('forbidden')
                if row[1] != state.encoded(request): raise Failure('request-conflict')
                receipt = json.loads(row[2])
                return (202 if receipt['outcome'] == 'queued' else 200), receipt
            next_id = db.execute('SELECT sequence FROM integration_meta WHERE id=1').fetchone()[0]
            if sequence != next_id: raise Failure('request-expired' if sequence < next_id else 'request-order')
            if next_id == MAX_SEQUENCE or db.execute("SELECT 1 FROM integration_requests WHERE phase='queued'").fetchone(): raise Failure('capacity')
            pairs = groups(app.directory)
            view, _, _ = projection(db, pairs)
            if request['expectedRevision'] != view['revision'] or wall.pending(db): raise Failure('revision-conflict')
            operation(db, pairs, request['command'])
            check_deadline(deadline)
            receipt = dict(apiVersion=VERSION, requestId=ticket, outcome='queued', priorEffects='none', physicalOutcome='unknown')
            db.execute('UPDATE integration_meta SET sequence=? WHERE id=1', (sequence + 1,))
            db.execute('INSERT INTO integration_requests VALUES (?,?,?,?,?,?,?)',
                       (sequence, principal, state.encoded(request), state.encoded(receipt), 'queued', time.time(), view['revision']))
        try:
            app.launch(app.directory)
        except Exception:
            # An already running worker can commit despite a failed launch attempt.
            with admission_transaction(app.directory, None) as db:
                row = db.execute('SELECT phase,receipt FROM integration_requests WHERE sequence=?', (sequence,)).fetchone()
                receipt = finish(db, sequence, 'failed', 'transport-failure') if row[0] == 'queued' else json.loads(row[1])
            return (503 if receipt['outcome'] == 'failed' else 200), receipt
        return 202, receipt
    except Failure as error:
        return error_result(error)


def cancel(app, token, device, ticket, deadline=None, **checks):
    from controller_server import admission_transaction
    try:
        with admission_transaction(app.directory, deadline) as db:
            principal = authorize(app, db, token, device, 'control', checks)
            if not valid_ticket(ticket): raise Failure('invalid-request')
            if ticket['epoch'] != state.read(db)['epoch']: raise Failure('request-expired')
            row = db.execute('SELECT principal,phase,receipt FROM integration_requests WHERE sequence=?', (ticket['sequence'],)).fetchone()
            if not row: raise Failure('request-expired')
            if row[0] != principal: raise Failure('forbidden')
            receipt = finish(db, ticket['sequence'], 'cancelled') if row[1] == 'queued' else json.loads(row[2])
            return 200, receipt
    except Failure as error:
        return error_result(error)
