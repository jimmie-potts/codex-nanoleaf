"""Standard-library controller ledger in the installation's existing database."""
import contextlib
import hashlib
import hmac
import json
import secrets
import sqlite3
import time

import devices

LIMITS = dict(maxPending=32,maxBodyBytes=65536,maxInFlight=32,maxReceipts=256,
              maxEvents=32,maxStreams=16,authenticationTimeoutMs=2000)
UNSUPPORTED = ('media','zones','preview')
UNKNOWN = {'status':'unknown'}
PENDING_SECONDS = 30
MAX_SCENES = 256
MAX_LABEL = 80
CONTROLS = ('power.set','brightness.set','scene.activate')
HOLD = 'controller_hold_revision'
# The HTTP status of each machine-contract failure code, shared by the native and extension routes.
HTTP={'invalid-request':400,'unauthenticated':401,'forbidden':403,'unknown-device':404,
      'revision-conflict':409,'stale-generation':409,'request-conflict':409,'request-order':409,
      'request-expired':410,'unsupported-capability':422,'capacity':429,'transport-failure':503}
# The original tables hold the Lines ledger unchanged, so older source can still read and write it.
# Another device's ledger uses the same tables suffixed `@<device>`, as ADR 0009 names device meta keys.
TABLES = {
    'controller_meta': '(id INTEGER PRIMARY KEY, payload TEXT NOT NULL)',
    'controller_requests': '(sequence INTEGER PRIMARY KEY, request TEXT NOT NULL, receipt TEXT NOT NULL, principal TEXT NOT NULL, phase TEXT NOT NULL, created REAL NOT NULL, mode_revision INTEGER NOT NULL)',
    'controller_events': '(sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL)',
}


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def stored(base,device=devices.DEFAULT):
    """A ledger table's stored name: the original for the Lines, `base@device` for another device."""
    if device==devices.DEFAULT:return base
    if not isinstance(device,str) or not devices.ID.fullmatch(device):raise ValueError('Invalid device identity.')
    return base+'@'+device


def table(base,device=devices.DEFAULT):
    """The quoted identifier of one device's ledger table."""
    return '"'+stored(base,device)+'"'


def present(db, device=None):
    """Whether the controller is configured, or with a device, whether that device has a ledger."""
    exists=lambda name:bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())
    return exists('controller_meta') and (device is None or exists(stored('controller_meta',device)))


def init(db, identity, device=devices.DEFAULT):
    for base,schema in TABLES.items():
        db.execute('CREATE TABLE IF NOT EXISTS '+table(base,device)+' '+schema)
    db.execute('CREATE TABLE IF NOT EXISTS controller_credentials (principal TEXT PRIMARY KEY, digest TEXT NOT NULL, scopes TEXT NOT NULL, active INTEGER NOT NULL)')
    if not db.execute('SELECT 1 FROM '+table('controller_meta',device)).fetchone():
        epoch=secrets.token_hex(16)
        data=dict(identity=dict(identity,controllerEpoch=epoch),epoch=epoch,nextSequence=0,
                  revision=0,generation=0,cursor=0,clockEpoch=secrets.token_hex(16),sceneKey=secrets.token_hex(32),
                  lastSuccessfulSend=UNKNOWN,lastOutcome=UNKNOWN)
        if device!=devices.DEFAULT:
            # Listener-wide flags are kept in every ledger; a new ledger starts from the original's.
            original=read(db)
            data.update(clockEpoch=original['clockEpoch'],**({'stopped':original['stopped']} if 'stopped' in original else {}))
        save(db,data,device)


def drop(db,device):
    """Delete another device's whole ledger when it is unregistered; the Lines ledger is never dropped."""
    if device==devices.DEFAULT:raise ValueError('The Lines ledger cannot be removed.')
    for base in TABLES:
        db.execute('DROP TABLE IF EXISTS '+table(base,device))


def ledgers(db):
    """Devices with a ledger, the original Lines device first, then in the order they were added."""
    if not present(db):return []
    prefix='controller_meta@'
    return [devices.DEFAULT]+[name[len(prefix):] for name, in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND substr(name,1,?)=? ORDER BY rowid",(len(prefix),prefix))]


def device_for(db, device_id):
    """The ledger whose public identity is device_id, or None."""
    for device in ledgers(db):
        if read(db,device)['identity']['deviceId']==device_id:return device
    return None


def read(db, device=devices.DEFAULT):
    return json.loads(db.execute('SELECT payload FROM '+table('controller_meta',device)+' WHERE id=1').fetchone()[0])


def save(db,data,device=devices.DEFAULT):
    db.execute('INSERT OR REPLACE INTO '+table('controller_meta',device)+' VALUES (1,?)',(encoded(data),))


def hold(db,device,revision):
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(devices.meta_key(HOLD,device),str(revision)))


def release(db,device):
    db.execute('DELETE FROM meta WHERE key=?',(devices.meta_key(HOLD,device),))


def scene_id(data,name):
    # Keyed by a private ledger secret, never by an epoch the snapshot publishes.
    return 'scene-'+hmac.new(data['sceneKey'].encode(),('scene\0'+name).encode(),hashlib.sha256).hexdigest()


def scenes(data):
    """Discovered saved scenes as [(id, name)], bounded and ordered as the device reported them."""
    if 'sceneKey' not in data:return []
    return [(scene_id(data,name),name) for name in data.get('scenes',[])]


def capabilities(data):
    result={name:{'supported':False} for name in UNSUPPORTED}
    result['power']={'supported':True}
    result['brightness']={'supported':True,'minimum':0,'maximum':100}
    result['scenes']={'supported':True,'sceneIds':[identity for identity,_ in scenes(data)]}
    result['modes']={'supported':True,'values':['Work','Quiet','Free']}
    return result


def discovered(db,names,device=devices.DEFAULT):
    """Called by the device's worker after its scene observation; only a changed list publishes an event."""
    if not present(db,device):return False
    clean=[]
    for name in names:
        if isinstance(name,str) and name and name not in clean and len(clean)<MAX_SCENES:clean.append(name)
    data=read(db,device)
    minted='sceneKey' not in data  # Ledgers created before discovery existed.
    if minted:data['sceneKey']=secrets.token_hex(32)
    if not minted and data.get('scenes',[])==clean:return False
    data['scenes']=clean;save(db,data,device);event(db,device);return True


def overrides(db,device=devices.DEFAULT):
    names=(devices.meta_key('controller_power',device),devices.meta_key('controller_brightness',device))
    meta=dict(db.execute('SELECT key,value FROM meta WHERE key IN (?,?)',names))
    power=meta.get(names[0]);brightness=meta.get(names[1])
    return dict(power=None if power is None else power=='1',brightness=None if brightness is None else int(brightness))


def clock(data):
    return dict(domain='controller-monotonic',epoch=data['clockEpoch'],sampledAtMs=time.monotonic()*1000)


def ticket(data,sequence):
    return dict(epoch=data['epoch'],sequence=sequence)


def snapshot(db,device=devices.DEFAULT):
    data=read(db,device)
    mode=db.execute('SELECT value FROM meta WHERE key=?',(devices.meta_key('mode',device),)).fetchone()
    current=overrides(db,device)
    known=lambda value:UNKNOWN if value is None else {'status':'known','value':value}
    pending=[]
    for request,receipt in db.execute("SELECT request,receipt FROM "+table('controller_requests',device)+" WHERE phase IN ('queued','attempting') ORDER BY sequence LIMIT 32"):
        request=json.loads(request);receipt=json.loads(receipt)
        pending.append(dict(requestId=request['requestId'],command=request['command'],generation=receipt['generation']))
    return dict(apiVersion='1.0',identity=data['identity'],configurationRevision=data['revision'],
                generation=ticket(data,data['generation']),nextRequestId=ticket(data,data['nextSequence']),
                cursor=ticket(data,data['cursor']),sampleClock=clock(data),serviceHealth='unknown',
                capabilities=capabilities(data),limits=LIMITS,
                state=dict(desired=dict(power=known(current['power']),brightness=known(current['brightness']),mode=dict(status='known',value=(mode[0] if mode else 'work').capitalize())),
                           pending=pending,lastSuccessfulSend=data['lastSuccessfulSend'],lastOutcome=data['lastOutcome'],
                           externalControl=UNKNOWN,observation=UNKNOWN))


def event(db,device=devices.DEFAULT):
    data=read(db,device)
    if data['cursor']>=9007199254740991:raise ValueError('Controller event capacity reached.')
    data['cursor']+=1;save(db,data,device)
    snap=snapshot(db,device)
    events=table('controller_events',device)
    db.execute('INSERT INTO '+events+' VALUES (?,?)',(data['cursor'],encoded(dict(apiVersion='1.0',kind='change',cursor=snap['cursor'],snapshot=snap))))
    db.execute('DELETE FROM '+events+' WHERE sequence NOT IN (SELECT sequence FROM '+events+' ORDER BY sequence DESC LIMIT 32)')


def finish(db,sequence,outcome,failure=None,device=devices.DEFAULT):
    requests=table('controller_requests',device)
    row=db.execute('SELECT receipt FROM '+requests+' WHERE sequence=?',(sequence,)).fetchone()
    if not row:return
    receipt=json.loads(row[0]);receipt['outcome']=outcome
    if failure:receipt['failure']={'code':failure}
    else:receipt.pop('failure',None)
    receipt['priorEffects']='confirmed-transmission' if receipt['completedOperations'] else ('possible' if receipt['uncertainOperations'] else 'none')
    db.execute("UPDATE "+requests+" SET receipt=?,phase='done' WHERE sequence=?",(encoded(receipt),sequence))
    data=read(db,device);data['lastOutcome']={'status':'known','receipt':receipt};save(db,data,device)
    db.execute("DELETE FROM "+requests+" WHERE phase='done' AND sequence NOT IN (SELECT sequence FROM "+requests+" WHERE phase='done' ORDER BY sequence DESC LIMIT 256)")
    event(db,device)


def changed(db, mode=False, native=False, device=devices.DEFAULT):
    """Called inside the owning browser/CLI/native desired-state transaction for one device's ledger."""
    if not present(db,device):return
    data=read(db,device)
    if data['revision']>=9007199254740991 or data['generation']>=9007199254740991:
        raise ValueError('Controller revision capacity reached.')
    if not native:data['revision']+=1
    if mode:data['generation']+=1
    save(db,data,device)
    if mode:
        release(db,device)
        for sequence, in list(db.execute("SELECT sequence FROM "+table('controller_requests',device)+" WHERE phase IN ('queued','attempting')")):
            finish(db,sequence,'cancelled','stale-generation',device)
    event(db,device)


def credential(db, token):
    digest=hashlib.sha256(token.encode()).hexdigest()
    for principal,known,scopes,active in db.execute('SELECT principal,digest,scopes,active FROM controller_credentials'):
        if secrets.compare_digest(digest,known) and active:
            return principal,json.loads(scopes)
    return None


def recover(db,now=None,attempts=False,device=None):
    """Only a device's locked worker may recover its attempts; the listener expires every device's unsent work."""
    if not present(db):return
    now=time.time() if now is None else now
    for owner in (ledgers(db) if device is None else [device]):
        for sequence,phase,created,revision in list(db.execute("SELECT sequence,phase,created,mode_revision FROM "+table('controller_requests',owner)+" WHERE phase!='done'")):
            if phase=='attempting' and attempts:
                finish(db,sequence,'uncertain','uncertain-result',owner)
                hold(db,owner,revision)
            elif phase=='queued' and now-created>=PENDING_SECONDS:
                finish(db,sequence,'failed','transport-failure',owner)
                hold(db,owner,revision)


def held(db,revision,device=devices.DEFAULT):
    row=db.execute('SELECT value FROM meta WHERE key=?',(devices.meta_key(HOLD,device),)).fetchone()
    return row==(str(revision),)


class Cancelled(Exception):
    pass


class Execution:
    """Journal each transport operation of one device using its worker's transaction and lock."""
    def __init__(self,db,revision,sequence=None,device=devices.DEFAULT):
        self.db=db;self.revision=revision;self.sequence=sequence;self.device=device;self.count=0
        if sequence is not None or not present(db,device):return
        for row in db.execute("SELECT sequence,request FROM "+table('controller_requests',device)+" WHERE phase='queued' AND mode_revision=? ORDER BY sequence DESC",(revision,)):
            if json.loads(row[1])['command']['kind']=='mode.set':
                self.sequence=row[0];break

    def current(self):
        row=self.db.execute('SELECT receipt,principal,phase,mode_revision FROM '+table('controller_requests',self.device)+' WHERE sequence=?',(self.sequence,)).fetchone()
        if not row or row[2]=='done':return False
        receipt=json.loads(row[0]);data=read(self.db,self.device)
        active=self.db.execute('SELECT active FROM controller_credentials WHERE principal=?',(row[1],)).fetchone()
        # The Lines ledger carries the listener-wide disable. A revoke or disable that missed this ledger,
        # such as one run by older source, ends the request as revocation would instead of retrying it.
        if active!=(1,) or read(self.db).get('stopped'):
            finish(self.db,self.sequence,'cancelled','forbidden',self.device)
            hold(self.db,self.device,row[3])
            return False
        return receipt['generation']==ticket(data,data['generation'])

    def call(self,send,*args,**kwargs):
        db=self.db;device=self.device
        revision=db.execute('SELECT value FROM meta WHERE key=?',(devices.meta_key('mode_revision',device),)).fetchone()
        if held(db,self.revision,device) or int(revision[0] if revision else '0')!=self.revision:
            raise Cancelled()
        if self.sequence is None:return send(*args,**kwargs)
        if not self.current():raise Cancelled()
        self.count+=1;operation='transport-'+str(self.count)
        receipt=json.loads(db.execute('SELECT receipt FROM '+table('controller_requests',device)+' WHERE sequence=?',(self.sequence,)).fetchone()[0])
        receipt['uncertainOperations'].append(operation)
        db.execute("UPDATE "+table('controller_requests',device)+" SET phase='attempting',receipt=? WHERE sequence=?",(encoded(receipt),self.sequence))
        db.commit()  # A crash after this point cannot be classified as no effect.
        db.execute('BEGIN IMMEDIATE')
        if not self.current():raise Cancelled()
        try:
            result=send(*args,**kwargs)
        except Exception:
            finish(db,self.sequence,'partially-applied' if receipt['completedOperations'] else 'uncertain','uncertain-result',device)
            revision=db.execute('SELECT mode_revision FROM '+table('controller_requests',device)+' WHERE sequence=?',(self.sequence,)).fetchone()[0]
            hold(db,device,revision)
            db.commit();db.execute('BEGIN IMMEDIATE')
            raise
        receipt['uncertainOperations'].remove(operation);receipt['completedOperations'].append(operation)
        receipt['priorEffects']='confirmed-transmission'
        db.execute('UPDATE '+table('controller_requests',device)+' SET receipt=? WHERE sequence=?',(encoded(receipt),self.sequence))
        data=read(db,device);data['lastSuccessfulSend']=dict(status='known',requestId=receipt['requestId'],clock=clock(data),operationIds=receipt['completedOperations']);save(db,data,device)
        db.commit();db.execute('BEGIN IMMEDIATE')
        return result

    def complete(self):
        if self.sequence is not None and self.current():
            finish(self.db,self.sequence,'sent' if self.count else 'cancelled',device=self.device)


def controls(db,revision,device=devices.DEFAULT):
    """One device's queued one-shot general controls at this mode revision as (created, sequence, command), oldest first."""
    if not present(db,device):return []
    result=[]
    for sequence,request,created in db.execute("SELECT sequence,request,created FROM "+table('controller_requests',device)+" WHERE phase='queued' AND mode_revision=? ORDER BY sequence",(revision,)):
        command=json.loads(request)['command']
        if command['kind'] in CONTROLS:result.append((created,sequence,command))
    return result


def control_payload(data,command):
    """The single device write for a general control, or None when its scene is no longer advertised."""
    kind=command['kind']
    if kind=='power.set':return '/state',{'on':{'value':command['on']}}
    if kind=='brightness.set':return '/state',{'brightness':{'value':command['percent'],'duration':0}}
    for identity,name in scenes(data):
        if identity==command['sceneId']:return '/effects',{'select':name}
    return None


def readonly(directory):
    # A rollback-journal writer briefly blocks new readers while committing.
    # Wait for that commit without changing the database or retrying forever.
    db=sqlite3.connect((directory/'status.sqlite').resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
    db.execute('BEGIN')
    return db


def check_deadline(deadline):
    if deadline is not None and time.monotonic()>=deadline:
        raise TimeoutError('Admission deadline expired.')


@contextlib.contextmanager
def admission_transaction(directory,deadline):
    check_deadline(deadline)
    remaining=2.5 if deadline is None else max(0,deadline-time.monotonic())
    # The configured database already exists. Admission must not run migrations.
    with contextlib.closing(sqlite3.connect((directory/'status.sqlite').resolve().as_uri()+'?mode=rw',uri=True,timeout=remaining)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        check_deadline(deadline)
        yield db
        check_deadline(deadline)
        if deadline is not None:
            db.execute('PRAGMA busy_timeout='+str(max(0,int((deadline-time.monotonic())*1000))))
        # Commit may wait for readers; its busy timeout is the remaining budget.
        db.commit()
