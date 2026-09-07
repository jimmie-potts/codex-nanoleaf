// Synthetic Windows loopback owner for the separately run WSL helper probe.
import http from 'node:http';
import { readFileSync } from 'node:fs';
const snapshot=JSON.parse(readFileSync(new URL('./snapshot.json',import.meta.url)));
let reads=0,writes=0,pending;const ledger=new Map();
const server=http.createServer(async(req,res)=>{
 if(req.headers.authorization!==`Bearer ${'b'.repeat(43)}`||req.headers.host!==`127.0.0.1:${server.address().port}`){res.writeHead(403);res.end('{}');return;}
 if(req.method==='GET'&&req.url===`/controller/v1/snapshot?deviceId=${snapshot.identity.deviceId}`){reads++;res.end(JSON.stringify(pending?{...snapshot,state:{...snapshot.state,pending:[pending]}}:snapshot));return;}
 if(req.method==='POST'&&req.url==='/controller/v1/commands'){
  let input='';for await(const chunk of req){input+=chunk;if(input.length>65536){req.destroy();return;}}
  const request=JSON.parse(input);writes++;
  const key=JSON.stringify(request.requestId),fingerprint=JSON.stringify(request);
  const fail=code=>{res.writeHead(409);res.end(JSON.stringify({failure:{code}}));};
  if(request.expectedConfigurationRevision!==snapshot.configurationRevision){fail('revision-conflict');return;}
  if(ledger.has(key)&&ledger.get(key)!==fingerprint){fail('request-conflict');return;}
  if(request.requestId.sequence===401){res.destroy();return;}
  ledger.set(key,fingerprint);
  if(request.command.mode==='Free'){pending={requestId:request.requestId,command:request.command,generation:request.expectedGeneration};await new Promise(resolve=>setTimeout(resolve,2000));}else pending=undefined;res.writeHead(202);res.end(JSON.stringify({apiVersion:'1.0',controllerId:snapshot.identity.controllerId,deviceId:snapshot.identity.deviceId,requestId:request.requestId,configurationRevision:request.expectedConfigurationRevision,generation:request.expectedGeneration,outcome:'queued',priorEffects:'none',completedOperations:[],uncertainOperations:[]}));return;
 }
 res.writeHead(404);res.end('{}');
});
const timer=setTimeout(stop,120000);
function stop(){clearTimeout(timer);server.closeAllConnections();server.close(()=>{console.log(JSON.stringify({reads,writes}));process.exit(0);});}
process.stdin.on('data',chunk=>{if(String(chunk).trim()==='stop')stop();});
server.listen(0,'127.0.0.1',()=>console.log(JSON.stringify({port:server.address().port})));
