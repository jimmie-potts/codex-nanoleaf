"""Standard-library controller ledger in the installation's existing database."""
import contextlib
import hashlib
import hmac
import json
import secrets
import sqlite3
import time

LIMITS = dict(maxPending=32,maxBodyBytes=65536,maxInFlight=32,maxReceipts=256,
              maxEvents=32,maxStreams=16,authenticationTimeoutMs=2000)
UNSUPPORTED = ('media','zones','preview')
UNKNOWN = {'status':'unknown'}
PENDING_SECONDS = 30
MAX_SCENES = 256
MAX_LABEL = 80
CONTROLS = ('power.set','brightness.set','scene.activate')


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def present(db):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='controller_meta'").fetchone())


def init(db, identity):
    db.execute('CREATE TABLE IF NOT EXISTS controller_meta (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS controller_credentials (principal TEXT PRIMARY KEY, digest TEXT NOT NULL, scopes TEXT NOT NULL, active INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS controller_requests (sequence INTEGER PRIMARY KEY, request TEXT NOT NULL, receipt TEXT NOT NULL, principal TEXT NOT NULL, phase TEXT NOT NULL, created REAL NOT NULL, mode_revision INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS controller_events (sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
    if not db.execute('SELECT 1 FROM controller_meta').fetchone():
        epoch=secrets.token_hex(16)
        data=dict(identity=dict(identity,controllerEpoch=epoch),epoch=epoch,nextSequence=0,
                  revision=0,generation=0,cursor=0,clockEpoch=secrets.token_hex(16),sceneKey=secrets.token_hex(32),
                  lastSuccessfulSend=UNKNOWN,lastOutcome=UNKNOWN)
        save(db,data)


def read(db):
    return json.loads(db.execute('SELECT payload FROM controller_meta WHERE id=1').fetchone()[0])


def save(db,data):
    db.execute('INSERT OR REPLACE INTO controller_meta VALUES (1,?)',(encoded(data),))


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


def discovered(db,names):
    """Called by the worker after its scene observation; only a changed list publishes an event."""
    if not present(db):return False
    clean=[]
    for name in names:
        if isinstance(name,str) and name and name not in clean and len(clean)<MAX_SCENES:clean.append(name)
    data=read(db)
    minted='sceneKey' not in data  # Ledgers created before discovery existed.
    if minted:data['sceneKey']=secrets.token_hex(32)
    if not minted and data.get('scenes',[])==clean:return False
    data['scenes']=clean;save(db,data);event(db);return True


def overrides(db):
    meta=dict(db.execute("SELECT key,value FROM meta WHERE key IN ('controller_power','controller_brightness')"))
    power=meta.get('controller_power');brightness=meta.get('controller_brightness')
    return dict(power=None if power is None else power=='1',brightness=None if brightness is None else int(brightness))


def clock(data):
    return dict(domain='controller-monotonic',epoch=data['clockEpoch'],sampledAtMs=time.monotonic()*1000)


def ticket(data,sequence):
    return dict(epoch=data['epoch'],sequence=sequence)


def snapshot(db):
    data=read(db)
    mode=db.execute("SELECT value FROM meta WHERE key='mode'").fetchone()
    current=overrides(db)
    known=lambda value:UNKNOWN if value is None else {'status':'known','value':value}
    pending=[]
    for request,receipt in db.execute("SELECT request,receipt FROM controller_requests WHERE phase IN ('queued','attempting') ORDER BY sequence LIMIT 32"):
        request=json.loads(request);receipt=json.loads(receipt)
        pending.append(dict(requestId=request['requestId'],command=request['command'],generation=receipt['generation']))
    return dict(apiVersion='1.0',identity=data['identity'],configurationRevision=data['revision'],
                generation=ticket(data,data['generation']),nextRequestId=ticket(data,data['nextSequence']),
                cursor=ticket(data,data['cursor']),sampleClock=clock(data),serviceHealth='unknown',
                capabilities=capabilities(data),limits=LIMITS,
                state=dict(desired=dict(power=known(current['power']),brightness=known(current['brightness']),mode=dict(status='known',value=(mode[0] if mode else 'work').capitalize())),
                           pending=pending,lastSuccessfulSend=data['lastSuccessfulSend'],lastOutcome=data['lastOutcome'],
                           externalControl=UNKNOWN,observation=UNKNOWN))


def event(db):
    data=read(db)
    if data['cursor']>=9007199254740991:raise ValueError('Controller event capacity reached.')
    data['cursor']+=1;save(db,data)
    snap=snapshot(db)
    db.execute('INSERT INTO controller_events VALUES (?,?)',(data['cursor'],encoded(dict(apiVersion='1.0',kind='change',cursor=snap['cursor'],snapshot=snap))))
    db.execute('DELETE FROM controller_events WHERE sequence NOT IN (SELECT sequence FROM controller_events ORDER BY sequence DESC LIMIT 32)')


def finish(db,sequence,outcome,failure=None):
    row=db.execute('SELECT receipt FROM controller_requests WHERE sequence=?',(sequence,)).fetchone()
    if not row:return
    receipt=json.loads(row[0]);receipt['outcome']=outcome
    if failure:receipt['failure']={'code':failure}
    else:receipt.pop('failure',None)
    receipt['priorEffects']='confirmed-transmission' if receipt['completedOperations'] else ('possible' if receipt['uncertainOperations'] else 'none')
    db.execute("UPDATE controller_requests SET receipt=?,phase='done' WHERE sequence=?",(encoded(receipt),sequence))
    data=read(db);data['lastOutcome']={'status':'known','receipt':receipt};save(db,data)
    db.execute("DELETE FROM controller_requests WHERE phase='done' AND sequence NOT IN (SELECT sequence FROM controller_requests WHERE phase='done' ORDER BY sequence DESC LIMIT 256)")
    event(db)


def changed(db, mode=False, native=False):
    """Called inside the owning browser/tray/native desired-state transaction."""
    if not present(db):return
    data=read(db)
    if data['revision']>=9007199254740991 or data['generation']>=9007199254740991:
        raise ValueError('Controller revision capacity reached.')
    if not native:data['revision']+=1
    if mode:data['generation']+=1
    save(db,data)
    if mode:
        db.execute("DELETE FROM meta WHERE key='controller_hold_revision'")
        for sequence, in list(db.execute("SELECT sequence FROM controller_requests WHERE phase IN ('queued','attempting')")):
            finish(db,sequence,'cancelled','stale-generation')
    event(db)


def credential(db, token):
    digest=hashlib.sha256(token.encode()).hexdigest()
    for principal,known,scopes,active in db.execute('SELECT principal,digest,scopes,active FROM controller_credentials'):
        if secrets.compare_digest(digest,known) and active:
            return principal,json.loads(scopes)
    return None


def recover(db,now=None,attempts=False):
    """Only the locked worker may recover attempts; the listener expires unsent work."""
    if not present(db):return
    now=time.time() if now is None else now
    for sequence,phase,created,revision in list(db.execute("SELECT sequence,phase,created,mode_revision FROM controller_requests WHERE phase!='done'")):
        if phase=='attempting' and attempts:
            finish(db,sequence,'uncertain','uncertain-result')
            db.execute("INSERT OR REPLACE INTO meta VALUES ('controller_hold_revision',?)",(str(revision),))
        elif phase=='queued' and now-created>=PENDING_SECONDS:
            finish(db,sequence,'failed','transport-failure')
            db.execute("INSERT OR REPLACE INTO meta VALUES ('controller_hold_revision',?)",(str(revision),))


def held(db,revision):
    row=db.execute("SELECT value FROM meta WHERE key='controller_hold_revision'").fetchone()
    return row==(str(revision),)


class Cancelled(Exception):
    pass


class Execution:
    """Journal each transport operation using the worker's transaction and lock."""
    def __init__(self,db,revision,sequence=None):
        self.db=db;self.revision=revision;self.sequence=sequence;self.count=0
        if sequence is not None or not present(db):return
        for row in db.execute("SELECT sequence,request FROM controller_requests WHERE phase='queued' AND mode_revision=? ORDER BY sequence DESC",(revision,)):
            if json.loads(row[1])['command']['kind']=='mode.set':
                self.sequence=row[0];break

    def current(self):
        row=self.db.execute('SELECT receipt,principal,phase FROM controller_requests WHERE sequence=?',(self.sequence,)).fetchone()
        if not row:return False
        receipt=json.loads(row[0]);data=read(self.db)
        active=self.db.execute('SELECT active FROM controller_credentials WHERE principal=?',(row[1],)).fetchone()
        return row[2]!='done' and active==(1,) and not data.get('stopped') and receipt['generation']==ticket(data,data['generation'])

    def call(self,send,*args,**kwargs):
        db=self.db
        revision=db.execute("SELECT value FROM meta WHERE key='mode_revision'").fetchone()
        if held(db,self.revision) or int(revision[0] if revision else '0')!=self.revision:
            raise Cancelled()
        if self.sequence is None:return send(*args,**kwargs)
        if not self.current():raise Cancelled()
        self.count+=1;operation='transport-'+str(self.count)
        receipt=json.loads(db.execute('SELECT receipt FROM controller_requests WHERE sequence=?',(self.sequence,)).fetchone()[0])
        receipt['uncertainOperations'].append(operation)
        db.execute("UPDATE controller_requests SET phase='attempting',receipt=? WHERE sequence=?",(encoded(receipt),self.sequence))
        db.commit()  # A crash after this point cannot be classified as no effect.
        db.execute('BEGIN IMMEDIATE')
        if not self.current():raise Cancelled()
        try:
            result=send(*args,**kwargs)
        except Exception:
            finish(db,self.sequence,'partially-applied' if receipt['completedOperations'] else 'uncertain','uncertain-result')
            revision=db.execute('SELECT mode_revision FROM controller_requests WHERE sequence=?',(self.sequence,)).fetchone()[0]
            db.execute("INSERT OR REPLACE INTO meta VALUES ('controller_hold_revision',?)",(str(revision),))
            db.commit();db.execute('BEGIN IMMEDIATE')
            raise
        receipt['uncertainOperations'].remove(operation);receipt['completedOperations'].append(operation)
        receipt['priorEffects']='confirmed-transmission'
        db.execute('UPDATE controller_requests SET receipt=? WHERE sequence=?',(encoded(receipt),self.sequence))
        data=read(db);data['lastSuccessfulSend']=dict(status='known',requestId=receipt['requestId'],clock=clock(data),operationIds=receipt['completedOperations']);save(db,data)
        db.commit();db.execute('BEGIN IMMEDIATE')
        return result

    def complete(self):
        if self.sequence is not None and self.current():
            finish(self.db,self.sequence,'sent' if self.count else 'cancelled')


def controls(db,revision):
    """Queued one-shot general controls at this mode revision, oldest first."""
    if not present(db):return []
    result=[]
    for sequence,request in db.execute("SELECT sequence,request FROM controller_requests WHERE phase='queued' AND mode_revision=? ORDER BY sequence",(revision,)):
        command=json.loads(request)['command']
        if command['kind'] in CONTROLS:result.append((sequence,command))
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
