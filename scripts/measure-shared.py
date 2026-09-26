"""Measure the isolated Linux shared consumer; no agents, devices or live state."""
import argparse
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
import bridge as b
import database
import shared_input as shared
import shared_source


def run(samples=100):
    corpus=json.loads((shared.PACKAGE/'fixtures/snapshots-v1.json').read_text())
    seed=corpus['cases'][0]['input']['sessions'][0]
    profiles=[]
    with tempfile.TemporaryDirectory(prefix='nanoleaf-shared-measure-') as temporary:
        directory=Path(temporary); token=directory/'token';token.write_text('a'*43);token.chmod(0o600)
        current={}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                if self.path!='/api/monitor/v1/sessions?snapshotVersion=1.1' or self.headers.get('Authorization')!='Bearer '+'a'*43:
                    self.send_error(403);return
                raw=json.dumps(current).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        config={'version':1,'ownerId':'owner','consumerId':'nanoleaf','endpoint':f'http://127.0.0.1:{server.server_port}/api/monitor/v1',
                'tokenFile':str(token),'clearOnNewTurn':True,'qualifiedSources':[{k:seed['identity'][k] for k in shared.SOURCE}],'bindings':[]}
        try:
            for count in (1,10,50):
                # A fresh projection avoids rollback's personal legacy-hook check.
                state=directory/f'profile-{count}';state.mkdir()
                sessions=[]
                for index in range(count):
                    session=json.loads(json.dumps(seed));session['identity']['sessionId']=f'session-{index}';session['activity']='active';session['generation']=0;sessions.append(session)
                snapshot={'apiVersion':'1.1','revision':1,'asOfMs':1000,'collector':'running','lossCount':0,'sessions':sessions}
                current.update(apiVersion='1.0',ownerId='owner',connection='current',snapshot=snapshot,admissionRejected=0,nextRequestId='request-1')
                shared_source.configure(state,config);shared_source.select_source(state,'shared')
                repetitions=[]
                for repetition in range(3):
                    values=[];cpu=time.process_time()
                    for sample in range(samples):
                        snapshot['revision']+=1
                        start=time.perf_counter()
                        value=shared.fetch_snapshot(config)
                        shared_source.accept(state,value)
                        with contextlib.closing(database.connect_state(state)) as db,db:
                            layout={'line_groups':[[100+i*2,101+i*2] for i in range(15)],'line_positions':[[i*10,0] for i in range(15)],'_mode':'work'}
                            projected=b.dashboard(db,layout,time.time());shared.render_config(db,layout)
                            b.effect_payload(layout,projected,time.time(),True)
                        values.append((time.perf_counter()-start)*1000)
                    values.sort()
                    repetitions.append({'samples':len(values),'p50Ms':statistics.median(values),'p95Ms':values[math.ceil(len(values)*.95)-1],
                                        'p99Ms':values[math.ceil(len(values)*.99)-1],'maximumMs':max(values),'processCpuMs':(time.process_time()-cpu)*1000})
                profiles.append({'sessions':count,'visibleCapacity':15,'repetitions':repetitions})
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
    return {'schemaVersion':1,'scope':'synthetic loopback fetch, released validation, SQLite projection, allocation and pure effect construction',
            'limitations':['Not Hub #30 integrated qualification or a full-hook baseline comparison.','No Windows performance, real producer, installed service, device submission or optical measurement.'],
            'python':platform.python_version(),'platform':platform.system(),'samplesPerRepetition':samples,
            'sourceHashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('bridge/shared_input.py','bridge/bridge.py','scripts/measure-shared.py')},
            'profiles':profiles,'bounds':{'pollIntervalSeconds':1,'transportDeadlineSeconds':shared.TIMEOUT,'responseBytes':shared.MAX_RESPONSE,'concurrentRequestsPerWorker':1}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='linux':parser.error('This receipt qualifies the Linux source path only.')
    result=run();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'profiles':len(result['profiles']),'samples':900,'output':str(args.output)}))
