"""Nanoleaf-owned configuration extension. Its only light operation is a Free-only
animation that the existing worker plays; this module never contacts the device."""
import contextlib
import hashlib
import hmac
import json
import re
import time

import controller_state as state
from controller_state import HTTP, admission_transaction, check_deadline
import devices
import edits
import effects
import project_map as wall
import shared_input
from store import control_state

VERSION = 'nanoleaf.integration/1.0'
MAX_ITEMS = 1000
MAX_RECEIPTS = 256
MAX_BODY = 65536
MAX_SEQUENCE = 9007199254740991
# The saved layout of every device; two of 300 elements with their geometry caches stay well inside this.
MAX_LAYOUT_BYTES = 1048576
OPERATIONS = ('settings.set', 'elements.assign', 'task.assign', 'project.color')
# Advertised by its own read route so the 1.0 snapshot keeps its exact shape.
ANIMATION = 'animation.play'
FAVORITE_OPERATIONS = ('animation.save', 'animation.rename', 'animation.forget')
PRIOR_EFFECTS = {'applied': 'configuration', 'sent': 'confirmed-transmission', 'uncertain': 'possible'}


class Failure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS integration_meta (id INTEGER PRIMARY KEY, sequence INTEGER NOT NULL)')
    db.execute('INSERT OR IGNORE INTO integration_meta VALUES (1,0)')
    db.execute('CREATE TABLE IF NOT EXISTS animation_favorites (name TEXT PRIMARY KEY, recipe TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS integration_requests (sequence INTEGER PRIMARY KEY, principal TEXT, request TEXT, receipt TEXT, phase TEXT, created REAL, revision TEXT)')


def favorites(db):
    """Bounded private recipes; callers choose whether to expose them on the machine-only route."""
    entries = db.execute('SELECT name,recipe FROM animation_favorites ORDER BY name LIMIT ?', (effects.MAX_FAVORITES + 1,)).fetchall()
    if len(entries) > effects.MAX_FAVORITES:
        raise Failure('capacity')
    return [dict(name=name, animation=json.loads(recipe)) for name, recipe in entries]


def resolve_animation(db, command):
    if 'favorite' not in command:
        return command
    row = db.execute('SELECT recipe FROM animation_favorites WHERE name=?', (command['favorite'],)).fetchone()
    if row is None:
        raise effects.Rejected('unsupported-capability')
    recipe = json.loads(row[0])
    if not effects.valid(dict(kind=ANIMATION, **recipe)) or 'favorite' in recipe or 'preset' in recipe:
        raise effects.Rejected('unsupported-capability')
    return dict(kind=ANIMATION, **recipe)


def favorite_edit(db, command, apply=False):
    """Check now, then check and commit again inside the worker's receipt transaction."""
    name, kind = command['name'], command['kind']
    exists = db.execute('SELECT 1 FROM animation_favorites WHERE name=?', (name,)).fetchone()
    if kind == 'animation.save':
        if exists: raise Failure('revision-conflict')
        if db.execute('SELECT COUNT(*) FROM animation_favorites').fetchone()[0] >= effects.MAX_FAVORITES:
            raise Failure('capacity')
        if apply:
            db.execute('INSERT INTO animation_favorites VALUES (?,?)', (name, state.encoded(effects.freeze(command['animation']))))
    else:
        if not exists: raise Failure('unsupported-capability')
        if kind == 'animation.rename':
            if db.execute('SELECT 1 FROM animation_favorites WHERE name=?', (command['newName'],)).fetchone():
                raise Failure('revision-conflict')
            if apply:
                db.execute('UPDATE animation_favorites SET name=? WHERE name=?', (command['newName'], name))
        elif apply:
            db.execute('DELETE FROM animation_favorites WHERE name=?', (name,))
    if apply:
        # These recipes do not change the current display or authorize another transport attempt.
        state.changed(db)


def geometry(directory):
    """Saved Lines zone pairs and positions; positions are None until every Line has one."""
    # Read only the saved physical mapping, never load_config's geometry discovery.
    raw = (directory / 'layout.json').read_bytes()
    if len(raw) > MAX_LAYOUT_BYTES:
        raise Failure('capacity')
    try:
        entry = devices.layout_devices(json.loads(raw)).get(devices.DEFAULT)
    except (ValueError, TypeError):
        raise Failure('unsupported-capability') from None
    if entry is None or entry['kind'] != 'lines':
        raise Failure('unsupported-capability')
    positions = [element['position'] for element in entry['elements']]
    return [list(element['zones']) for element in entry['elements']], None if None in positions else positions


def groups(directory):
    return geometry(directory)[0]


def opaque(data, kind, value):
    return kind + '-' + hmac.new(data['epoch'].encode(), (kind + '\0' + value).encode(), hashlib.sha256).hexdigest()


def rows(db, query, params=()):
    result = db.execute(query + ' LIMIT 1001', params).fetchall()
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
    prefs = dict((line, (p, half)) for line, p, half in rows(db, 'SELECT line_id,project,signature FROM line_prefs WHERE device=? ORDER BY line_id', (devices.DEFAULT,)))
    current = shared_input.state(db)
    shared = {}
    if current['source'] == 'shared' and current['envelope']:
        for session in current['envelope']['snapshot']['sessions']:
            shared[shared_input.identity_key(session['identity'])] = session
    pending = wall.pending(db)
    pending_view = None
    if pending:
        pending_view = dict(settings={k:v for k,v in pending.get('settings', {}).items() if k in ('style','coverage')}, elements=[], tasks=[])
        for key, value in pending.get('lines', {}).items():
            if key not in {wall.line_id(pair) for pair in pairs}: continue
            item = {'id': key}
            if 'project' in value: item['projectId'] = project_id(value['project'])
            if 'signature' in value: item['signature'] = value['signature']
            pending_view['elements'].append(item)
        for key, value in pending.get('tasks', {}).items():
            pending_view['tasks'].append(dict(taskId=task_id(key), projectId=project_id(value)))
        if len(pending_view['tasks']) > MAX_ITEMS: raise Failure('capacity')
    view = dict(apiVersion=VERSION, identity=data['identity'], configurationRevision=data['revision'],
                mode=state.snapshot(db)['state']['desired']['mode']['value'],
                settings={k: v for k, v in wall.settings(db).items() if k in ('style', 'coverage')},
                source=current['source'], projects=[], tasks=[], elements=[], wallPending=pending_view)
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
    revision_data = dict(view, pending=wall.pending(db), sourceGeneration=current['generation'], favorites=favorites(db))
    view['revision'] = hashlib.sha256(state.encoded(revision_data).encode()).hexdigest()
    return view, projects, tasks


def authorize(app, db, token, device, scope, checks):
    decision = app.contract.authorize(app.facts(db, token, device, scope, **checks))['decision']
    if decision != 'allowed':
        raise Failure(decision)
    if state.device_for(db, device) is None:
        raise Failure('unknown-device')
    return state.credential(db, token)[0]


def lines(db, device):
    """Whether device names the Lines ledger; the extension's queue, edits and animations belong to it alone."""
    return state.device_for(db, device) == devices.DEFAULT


def scene_list(data):
    # Scene names are the user's Nanoleaf app names; shared v1 carries only the opaque IDs.
    return [dict(id=identity, **({'name': name} if len(name) <= state.MAX_LABEL else {}))
            for identity, name in state.scenes(data)]


def device_view(db, device):
    """Read-only view for a device other than the Lines, in the extension's exact shape."""
    data = state.read(db, device)
    view, _, _ = projection(db, [])
    view.update(identity=data['identity'], configurationRevision=data['revision'],
                mode=state.snapshot(db, device)['state']['desired']['mode']['value'],
                settings={k: v for k, v in wall.settings(db, device).items() if k in ('style', 'coverage')},
                elements=[], wallPending=None)
    del view['revision']
    revision_data = dict(view, sourceGeneration=shared_input.state(db)['generation'])
    view['revision'] = hashlib.sha256(state.encoded(revision_data).encode()).hexdigest()
    view.update(nextRequestId=state.ticket(data, 0), pending=[], outcomes=[], scenes=scene_list(data))
    view['capabilities'] = {op: {'supported': False, 'scope': 'control'} for op in OPERATIONS}
    view['capabilities']['mode.set'] = {'supported': True, 'scope': 'control', 'route': '/controller/v1/commands'}
    view['limits'] = dict(maxItems=MAX_ITEMS, maxPending=1, maxReceipts=MAX_RECEIPTS, maxBodyBytes=MAX_BODY)
    return view


def snapshot(app, token, device, **checks):
    with contextlib.closing(state.readonly(app.directory)) as db:
        principal = authorize(app, db, token, device, 'read', checks)
        if not lines(db, device):
            return device_view(db, state.device_for(db, device))
        view, _, _ = projection(db, groups(app.directory))
        sequence = db.execute('SELECT sequence FROM integration_meta WHERE id=1').fetchone()[0]
        view['nextRequestId'] = state.ticket(state.read(db), sequence)
        view['pending'] = [json.loads(r[0]) for r in db.execute("SELECT request FROM integration_requests WHERE phase IN ('queued','attempting') AND principal=?", (principal,))]
        view['outcomes'] = [json.loads(r[0]) for r in db.execute("SELECT receipt FROM integration_requests WHERE principal=? ORDER BY sequence DESC LIMIT 32", (principal,))]
        view['scenes'] = scene_list(state.read(db))
        view['capabilities'] = {op: {'supported': True, 'scope': 'control'} for op in OPERATIONS}
        view['capabilities']['mode.set'] = {'supported': True, 'scope': 'control', 'route': '/controller/v1/commands'}
        view['limits'] = dict(maxItems=MAX_ITEMS, maxPending=1, maxReceipts=MAX_RECEIPTS, maxBodyBytes=MAX_BODY)
        return view


def remembered_scene_id(directory, data):
    """Read the worker's saved target; advertise only an existing ledger scene ID."""
    try:
        saved = json.loads((directory / devices.scene_file(devices.DEFAULT)).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None
    scene = saved.get('scene') if isinstance(saved, dict) else None
    if not isinstance(scene, dict) or not isinstance(scene.get('name'), str):
        return None
    return next((identity for identity, name in state.scenes(data) if name == scene['name']), None)


def animations(app, token, device, **checks):
    """The animation option set with the identity values a play request needs, in one read."""
    with contextlib.closing(state.readonly(app.directory)) as db:
        authorize(app, db, token, device, 'read', checks)
        if not lines(db, device):
            raise Failure('unsupported-capability')  # Animations play only on the Lines.
        view, _, _ = projection(db, groups(app.directory))
        sequence = db.execute('SELECT sequence FROM integration_meta WHERE id=1').fetchone()[0]
        return dict(apiVersion=VERSION, identity=view['identity'], mode=view['mode'], revision=view['revision'],
                    nextRequestId=state.ticket(state.read(db), sequence),
                    rememberedSceneId=remembered_scene_id(app.directory, state.read(db)),
                    presets=[dict(fields, id=name, colors=list(fields['colors'])) for name, fields in effects.PRESETS.items()],
                    favorites=favorites(db),
                    patterns=[dict(id=name, spatial=spatial) for name, spatial in effects.PATTERNS.items()],
                    speeds=list(effects.SPEEDS), directions=list(effects.DIRECTIONS), defaults=dict(effects.DEFAULTS),
                    limits=dict(minColors=effects.MIN_COLORS, maxColors=effects.MAX_COLORS,
                                maxFramesPerZone=effects.MAX_FRAMES, maxEffectBytes=effects.MAX_BYTES,
                                maxFavorites=effects.MAX_FAVORITES, maxFavoriteName=effects.MAX_NAME))


def saved_layout(directory, device):
    """One device's saved layout entry, or None when the file or the entry is absent; never discovers geometry."""
    try:
        raw = (directory / 'layout.json').read_bytes()
    except FileNotFoundError:
        return None
    if len(raw) > MAX_LAYOUT_BYTES:
        raise Failure('capacity')
    try:
        return devices.layout_devices(json.loads(raw)).get(device)
    except (ValueError, TypeError):
        raise Failure('unsupported-capability') from None


def drawn(config):
    """The map's display points per element, or None when the saved layout cannot draw every element."""
    try:
        shapes = wall.geometry(config) if config['kind'] == 'lines' else wall.triangle_geometry(config)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return [shape['points'] for shape in shapes] if len(shapes) == len(config['elements']) else None


def geometry_view(app, token, device, **checks):
    """Saved element geometry of one configured device in the map's display coordinates, without its drawing cache."""
    with contextlib.closing(state.readonly(app.directory)) as db:
        authorize(app, db, token, device, 'read', checks)
        ledger = state.device_for(db, device)
        identity = state.read(db, ledger)['identity']
    view = dict(apiVersion=VERSION, identity=identity, kind=None, elements=[], connectors=None)
    entry = saved_layout(app.directory, ledger)
    if entry is None:
        return view
    config = devices.projection(entry)
    points = drawn(config) or [None] * len(config['elements'])
    view['kind'] = entry['kind']
    view['elements'] = [dict(id=e['id'], number=e['number'], zones=list(e['zones']), points=p)
                        for e, p in zip(config['elements'], points)]
    graph = wall.connector_layout(config) if entry['kind'] == 'lines' else None
    if graph:
        view['connectors'] = dict(nodes=[dict(id=n['id'], x=n['x'], y=n['y']) for n in graph['nodes']],
                                  lines=[dict(id=l['id'], a=l['a'], b=l['b']) for l in graph['lines']])
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
    if kind == ANIMATION:
        if not effects.valid(c):
            raise Failure('invalid-request')
        return
    if kind in FAVORITE_OPERATIONS:
        fields = {'kind', 'name', 'animation'} if kind == 'animation.save' else ({'kind', 'name', 'newName'} if kind == 'animation.rename' else {'kind', 'name'})
        if set(c) != fields or not effects.valid_name(c['name']):
            raise Failure('invalid-request')
        if kind == 'animation.rename' and not effects.valid_name(c['newName']):
            raise Failure('invalid-request')
        if kind == 'animation.save':
            recipe = c['animation']
            if (type(recipe) is not dict or 'kind' in recipe or 'favorite' in recipe
                    or not effects.valid(dict(kind=ANIMATION, **recipe))):
                raise Failure('invalid-request')
        return
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


def edit(db, pairs, command):
    """The shared configuration edit a validated command requests, with its opaque IDs resolved.

    Returns edit(db, config), which applies it inside the caller's transaction.
    """
    if command['kind'] in FAVORITE_OPERATIONS:
        favorite_edit(db, command)
        return lambda db, config: favorite_edit(db, command, apply=True)
    _, projects, tasks = projection(db, pairs)
    def project(value):
        if value is None: return None
        if value not in projects: raise Failure('revision-conflict')
        return projects[value]
    kind = command['kind']
    if kind == 'settings.set':
        changes = {k: v for k, v in command.items() if k != 'kind'}
        return lambda db, config: edits.settings(db, config, changes)
    if kind == 'project.color':
        target, color = project(command['projectId']), command['color']
        return lambda db, config: edits.project_color(db, target, color)
    if kind == 'task.assign':
        if command['taskId'] not in tasks: raise Failure('revision-conflict')
        session, target = tasks[command['taskId']], project(command['projectId'])
        return lambda db, config: edits.task_project(db, config, session, target)
    ids = {wall.line_id(pair) for pair in pairs}; lines = {}
    for e in command['elements']:
        if e['id'] not in ids: raise Failure('unsupported-capability')
        value = {}
        if 'projectId' in e: value['project'] = project(e['projectId'])
        if 'signature' in e: value['signature'] = e['signature']
        lines[e['id']] = value
    return lambda db, config: edits.assign(db, config, lines)


def finish(db, sequence, outcome, code=None):
    row = db.execute('SELECT receipt FROM integration_requests WHERE sequence=?', (sequence,)).fetchone()
    if not row: return
    receipt = json.loads(row[0]); receipt['outcome'] = outcome
    receipt['priorEffects'] = PRIOR_EFFECTS.get(outcome, 'none')
    if code: receipt['failure'] = {'code': code}
    db.execute("UPDATE integration_requests SET receipt=?,phase='done' WHERE sequence=?", (state.encoded(receipt), sequence))
    db.execute("DELETE FROM integration_requests WHERE phase='done' AND sequence NOT IN (SELECT sequence FROM integration_requests WHERE phase='done' ORDER BY sequence DESC LIMIT 256)")
    return receipt


def hold(db):
    """Unsent animation work holds the Lines again, as unsent shared v1 work does."""
    revision = db.execute('SELECT value FROM meta WHERE key=?', (devices.meta_key('mode_revision'),)).fetchone()
    state.hold(db, devices.DEFAULT, revision[0] if revision else '0')


def recover(db, now=None, principal=None, cancel=False):
    if not state.present(db): return
    now = time.time() if now is None else now
    stopped = state.read(db).get('stopped')
    for sequence, owner, created, raw in list(db.execute("SELECT sequence,principal,created,request FROM integration_requests WHERE phase='queued'")):
        active = db.execute('SELECT active FROM controller_credentials WHERE principal=?', (owner,)).fetchone()
        if stopped or active != (1,) or (cancel and (principal is None or owner == principal)):
            finish(db, sequence, 'cancelled', 'forbidden')
        elif now - created >= 30 or now < created:
            finish(db, sequence, 'failed', 'request-expired')
            if json.loads(raw)['command']['kind'] == ANIMATION: hold(db)


def queued_animations(db):
    """Queued animations as (created, sequence, command), oldest first."""
    if not state.present(db): return []
    result = []
    for sequence, raw, created in db.execute("SELECT sequence,request,created FROM integration_requests WHERE phase='queued' ORDER BY sequence"):
        command = json.loads(raw)['command']
        if command['kind'] == ANIMATION: result.append((created, sequence, command))
    return result


def retire(db):
    """Every explicit mode command retires queued animations, as shared v1 retires queued controls."""
    for _, sequence, _ in queued_animations(db):
        finish(db, sequence, 'cancelled', 'stale-generation')


def recover_attempts(db):
    """Only the locked Lines worker calls this: an attempt without a result may have reached the device."""
    if not state.present(db): return
    for sequence, in list(db.execute("SELECT sequence FROM integration_requests WHERE phase='attempting'")):
        finish(db, sequence, 'uncertain', 'uncertain-result')


def attempt(db, sequence):
    """Record the attempt durably before the single write; returns the controller generation it belongs to."""
    generation = state.read(db)['generation']
    db.execute("UPDATE integration_requests SET phase='attempting' WHERE sequence=?", (sequence,))
    db.commit()  # A crash after this point cannot be classified as no effect.
    return generation


def play(db, sequence, generation, send):
    """Retake the write lock, then make the attempt's one write unless a mode command, revocation or disable intervened."""
    db.execute('BEGIN IMMEDIATE')
    row = db.execute('SELECT principal,phase FROM integration_requests WHERE sequence=?', (sequence,)).fetchone()
    if not row or row[1] != 'attempting': return
    data = state.read(db)
    active = db.execute('SELECT active FROM controller_credentials WHERE principal=?', (row[0],)).fetchone()
    if data['generation'] != generation:
        finish(db, sequence, 'cancelled', 'stale-generation'); return
    if data.get('stopped') or active != (1,):
        finish(db, sequence, 'cancelled', 'forbidden'); return
    try:
        send()
    except Exception:
        finish(db, sequence, 'uncertain', 'uncertain-result')
        db.commit(); db.execute('BEGIN IMMEDIATE')
        raise
    finish(db, sequence, 'sent')


def process(db, config, now=None):
    """Only the existing worker calls this, inside its configuration transaction.

    The configuration edit and its receipt commit together with the caller's transaction.
    """
    if not state.present(db): return
    recover(db, now)
    row = db.execute("SELECT sequence,request,revision FROM integration_requests WHERE phase='queued'").fetchone()
    if not row: return
    sequence, raw, revision = row
    if json.loads(raw)['command']['kind'] == ANIMATION: return  # The worker plays it through its own journal.
    try:
        view, _, _ = projection(db, config['line_groups'])
        if view['revision'] != revision: raise Failure('revision-conflict')
        if wall.pending(db) or db.execute('SELECT 1 FROM comets WHERE started IS NOT NULL AND device=?', (devices.DEFAULT,)).fetchone(): return
        edit(db, config['line_groups'], json.loads(raw)['command'])(db, config)
        finish(db, sequence, 'applied')
    except Failure as error:
        finish(db, sequence, 'failed', error.code)


def error_result(error):
    return HTTP.get(error.code, 400), {'failure': {'code': error.code}}


def receipt(app, token, device, ticket, **checks):
    with contextlib.closing(state.readonly(app.directory)) as db:
        principal = authorize(app, db, token, device, 'read', checks)
        if not valid_ticket(ticket): raise Failure('invalid-request')
        if not lines(db, device) or ticket['epoch'] != state.read(db)['epoch']: raise Failure('request-expired')
        row = db.execute('SELECT principal,receipt FROM integration_requests WHERE sequence=?', (ticket['sequence'],)).fetchone()
        if not row: raise Failure('request-expired')
        if row[0] != principal: raise Failure('forbidden')
        return json.loads(row[1])


def admit(app, token, request, body_bytes=None, deadline=None, **checks):
    try:
        with admission_transaction(app.directory, deadline) as db:
            device = request.get('deviceId') if type(request) is dict else None
            principal = authorize(app, db, token, device, 'control', checks)
            if (body_bytes is not None and body_bytes > MAX_BODY) or len(state.encoded(request).encode()) > MAX_BODY: raise Failure('capacity')
            validate(request)
            if not lines(db, device): raise Failure('unsupported-capability')  # Read-only for other devices.
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
            if next_id == MAX_SEQUENCE or db.execute("SELECT 1 FROM integration_requests WHERE phase IN ('queued','attempting')").fetchone(): raise Failure('capacity')
            pairs, positions = geometry(app.directory)
            view, _, _ = projection(db, pairs)
            if request['command']['kind'] == ANIMATION:
                # Content for Free only; Work and Quiet present agent status (hub ADR 0005).
                if control_state(db)['mode'] != 'free': raise Failure('unsupported-capability')
                if request['expectedRevision'] != view['revision']: raise Failure('revision-conflict')
                try:
                    effects.render(resolve_animation(db, request['command']), pairs, positions)
                except effects.Rejected as error:
                    raise Failure(error.code) from None
            else:
                if request['expectedRevision'] != view['revision'] or wall.pending(db): raise Failure('revision-conflict')
                edit(db, pairs, request['command'])  # Resolves every opaque ID before admission.
            check_deadline(deadline)
            receipt = dict(apiVersion=VERSION, requestId=ticket, outcome='queued', priorEffects='none', physicalOutcome='unknown')
            db.execute('UPDATE integration_meta SET sequence=? WHERE id=1', (sequence + 1,))
            db.execute('INSERT INTO integration_requests VALUES (?,?,?,?,?,?,?)',
                       (sequence, principal, state.encoded(request), state.encoded(receipt), 'queued', time.time(), view['revision']))
            if request['command']['kind'] == ANIMATION:
                # Like a fresh v1 control, a native light request authorizes another attempt.
                state.release(db, devices.DEFAULT)
        try:
            app.launch(app.directory)
        except Exception:
            # An already running worker can commit despite a failed launch attempt.
            with admission_transaction(app.directory, None) as db:
                row = db.execute('SELECT phase,receipt FROM integration_requests WHERE sequence=?', (sequence,)).fetchone()
                receipt = finish(db, sequence, 'failed', 'transport-failure') if row[0] == 'queued' else json.loads(row[1])
                if row[0] == 'queued' and request['command']['kind'] == ANIMATION: hold(db)
            return (503 if receipt['outcome'] == 'failed' else 200), receipt
        return 202, receipt
    except Failure as error:
        return error_result(error)


def cancel(app, token, device, ticket, deadline=None, **checks):
    try:
        with admission_transaction(app.directory, deadline) as db:
            principal = authorize(app, db, token, device, 'control', checks)
            if not valid_ticket(ticket): raise Failure('invalid-request')
            if not lines(db, device) or ticket['epoch'] != state.read(db)['epoch']: raise Failure('request-expired')
            row = db.execute('SELECT principal,phase,receipt FROM integration_requests WHERE sequence=?', (ticket['sequence'],)).fetchone()
            if not row: raise Failure('request-expired')
            if row[0] != principal: raise Failure('forbidden')
            receipt = finish(db, ticket['sequence'], 'cancelled') if row[1] == 'queued' else json.loads(row[2])
            return 200, receipt
    except Failure as error:
        return error_result(error)
