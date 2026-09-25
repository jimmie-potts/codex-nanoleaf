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
# Each configured device has its own ledger rows; the original Lines ledger keeps id 1 and its meta keys.
TABLES = {
    'controller_meta': "(id INTEGER PRIMARY KEY, payload TEXT NOT NULL, device TEXT NOT NULL DEFAULT 'wall')",
    'controller_requests': "(sequence INTEGER NOT NULL, request TEXT NOT NULL, receipt TEXT NOT NULL, principal TEXT NOT NULL, "
                           "phase TEXT NOT NULL, created REAL NOT NULL, mode_revision INTEGER NOT NULL, "
                           "device TEXT NOT NULL DEFAULT 'wall', PRIMARY KEY (device, sequence))",
    'controller_events': "(sequence INTEGER NOT NULL, payload TEXT NOT NULL, device TEXT NOT NULL DEFAULT 'wall', "
                         "PRIMARY KEY (device, sequence))",
}
LEGACY_COLUMNS = {'controller_requests': 'sequence, request, receipt, principal, phase, created, mode_revision',
                  'controller_events': 'sequence, payload'}


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def present(db, device=None):
    """Whether the controller is configured, or with a device, whether that device has a ledger."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='controller_meta'").fetchone():return False
    return device is None or bool(db.execute('SELECT 1 FROM controller_meta WHERE device=?',(device,)).fetchone())


def columns(db,table):
    return [row[1] for row in db.execute('PRAGMA table_info('+table+')')]


def migrate(db):
    """Guarded, idempotent upgrade of a single-device ledger inside the caller's initialization transaction."""
    if not present(db):return
    if 'device' not in columns(db,'controller_meta'):
        db.execute("ALTER TABLE controller_meta ADD COLUMN device TEXT NOT NULL DEFAULT 'wall'")
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS controller_meta_device ON controller_meta (device)')
    for table,legacy in LEGACY_COLUMNS.items():
        if 'device' in columns(db,table):continue
        # Sequences restart per device, so the key must include it; rows keep every value.
        db.execute('ALTER TABLE '+table+' RENAME TO '+table+'_legacy')
        db.execute('CREATE TABLE '+table+' '+TABLES[table])
        db.execute('INSERT INTO '+table+' ('+legacy+') SELECT '+legacy+' FROM '+table+'_legacy')
        db.execute('DROP TABLE '+table+'_legacy')


def init(db, identity, device=devices.DEFAULT):
    for table,schema in TABLES.items():
        db.execute('CREATE TABLE IF NOT EXISTS '+table+' '+schema)
    db.execute('CREATE TABLE IF NOT EXISTS controller_credentials (principal TEXT PRIMARY KEY, digest TEXT NOT NULL, scopes TEXT NOT NULL, active INTEGER NOT NULL)')
    migrate(db)
    if not present(db,device):
        epoch=secrets.token_hex(16)
        data=dict(identity=dict(identity,controllerEpoch=epoch),epoch=epoch,nextSequence=0,
                  revision=0,generation=0,cursor=0,clockEpoch=secrets.token_hex(16),sceneKey=secrets.token_hex(32),
                  lastSuccessfulSend=UNKNOWN,lastOutcome=UNKNOWN)
        if device!=devices.DEFAULT:
            # Listener-wide flags are kept in every ledger; a new ledger starts from the original's.
            original=read(db)
            data.update(clockEpoch=original['clockEpoch'],**({'stopped':original['stopped']} if 'stopped' in original else {}))
        db.execute('INSERT INTO controller_meta (payload,device) VALUES (?,?)',(encoded(data),device))


def ledgers(db):
    """Devices with a ledger, the original Lines device first."""
    if not present(db):return []
    return [device for device, in db.execute('SELECT device FROM controller_meta ORDER BY id')]


def device_for(db, device_id):
    """The ledger whose public identity is device_id, or None."""
    for device in ledgers(db):
        if read(db,device)['identity']['deviceId']==device_id:return device
    return None


def read(db, device=devices.DEFAULT):
    return json.loads(db.execute('SELECT payload FROM controller_meta WHERE device=?',(device,)).fetchone()[0])


def save(db,data,device=devices.DEFAULT):
    db.execute('UPDATE controller_meta SET payload=? WHERE device=?',(encoded(data),device))


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
    for request,receipt in db.execute("SELECT request,receipt FROM controller_requests WHERE device=? AND phase IN ('queued','attempting') ORDER BY sequence LIMIT 32",(device,)):
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
    db.execute('INSERT INTO controller_events (sequence,payload,device) VALUES (?,?,?)',(data['cursor'],encoded(dict(apiVersion='1.0',kind='change',cursor=snap['cursor'],snapshot=snap)),device))
    db.execute('DELETE FROM controller_events WHERE device=? AND sequence NOT IN (SELECT sequence FROM controller_events WHERE device=? ORDER BY sequence DESC LIMIT 32)',(device,device))


def finish(db,sequence,outcome,failure=None,device=devices.DEFAULT):
    row=db.execute('SELECT receipt FROM controller_requests WHERE device=? AND sequence=?',(device,sequence)).fetchone()
    if not row:return
    receipt=json.loads(row[0]);receipt['outcome']=outcome
    if failure:receipt['failure']={'code':failure}
    else:receipt.pop('failure',None)
    receipt['priorEffects']='confirmed-transmission' if receipt['completedOperations'] else ('possible' if receipt['uncertainOperations'] else 'none')
    db.execute("UPDATE controller_requests SET receipt=?,phase='done' WHERE device=? AND sequence=?",(encoded(receipt),device,sequence))
    data=read(db,device);data['lastOutcome']={'status':'known','receipt':receipt};save(db,data,device)
    db.execute("DELETE FROM controller_requests WHERE device=? AND phase='done' AND sequence NOT IN (SELECT sequence FROM controller_requests WHERE device=? AND phase='done' ORDER BY sequence DESC LIMIT 256)",(device,device))
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
        for sequence, in list(db.execute("SELECT sequence FROM controller_requests WHERE device=? AND phase IN ('queued','attempting')",(device,))):
            finish(db,sequence,'cancelled','stale-generation',device)
        if device==devices.DEFAULT:
            import integration_api
            integration_api.retire(db)  # Requested animations play only on the Lines.
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
    targets=ledgers(db) if device is None else [device]
    for sequence,phase,created,revision,owner in list(db.execute("SELECT sequence,phase,created,mode_revision,device FROM controller_requests WHERE phase!='done'")):
        if owner not in targets:continue
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
        for row in db.execute("SELECT sequence,request FROM controller_requests WHERE device=? AND phase='queued' AND mode_revision=? ORDER BY sequence DESC",(device,revision)):
            if json.loads(row[1])['command']['kind']=='mode.set':
                self.sequence=row[0];break

    def current(self):
        row=self.db.execute('SELECT receipt,principal,phase FROM controller_requests WHERE device=? AND sequence=?',(self.device,self.sequence)).fetchone()
        if not row:return False
        receipt=json.loads(row[0]);data=read(self.db,self.device)
        active=self.db.execute('SELECT active FROM controller_credentials WHERE principal=?',(row[1],)).fetchone()
        return row[2]!='done' and active==(1,) and not data.get('stopped') and receipt['generation']==ticket(data,data['generation'])

    def call(self,send,*args,**kwargs):
        db=self.db;device=self.device
        revision=db.execute('SELECT value FROM meta WHERE key=?',(devices.meta_key('mode_revision',device),)).fetchone()
        if held(db,self.revision,device) or int(revision[0] if revision else '0')!=self.revision:
            raise Cancelled()
        if self.sequence is None:return send(*args,**kwargs)
        if not self.current():raise Cancelled()
        self.count+=1;operation='transport-'+str(self.count)
        receipt=json.loads(db.execute('SELECT receipt FROM controller_requests WHERE device=? AND sequence=?',(device,self.sequence)).fetchone()[0])
        receipt['uncertainOperations'].append(operation)
        db.execute("UPDATE controller_requests SET phase='attempting',receipt=? WHERE device=? AND sequence=?",(encoded(receipt),device,self.sequence))
        db.commit()  # A crash after this point cannot be classified as no effect.
        db.execute('BEGIN IMMEDIATE')
        if not self.current():raise Cancelled()
        try:
            result=send(*args,**kwargs)
        except Exception:
            finish(db,self.sequence,'partially-applied' if receipt['completedOperations'] else 'uncertain','uncertain-result',device)
            revision=db.execute('SELECT mode_revision FROM controller_requests WHERE device=? AND sequence=?',(device,self.sequence)).fetchone()[0]
            hold(db,device,revision)
            db.commit();db.execute('BEGIN IMMEDIATE')
            raise
        receipt['uncertainOperations'].remove(operation);receipt['completedOperations'].append(operation)
        receipt['priorEffects']='confirmed-transmission'
        db.execute('UPDATE controller_requests SET receipt=? WHERE device=? AND sequence=?',(encoded(receipt),device,self.sequence))
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
    for sequence,request,created in db.execute("SELECT sequence,request,created FROM controller_requests WHERE device=? AND phase='queued' AND mode_revision=? ORDER BY sequence",(device,revision)):
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
