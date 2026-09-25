import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { mkdtemp,writeFile,rm } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { startHost } from '../dist/server.js';

const snapshot=JSON.parse(readFileSync(new URL('./snapshot.json',import.meta.url)));
const animations=JSON.parse(readFileSync(new URL('./animations.json',import.meta.url)));
const token='a'.repeat(43),upstream='b'.repeat(43);
const sceneId='scene-'+'c'.repeat(64);
const integrationSnapshot={apiVersion:'nanoleaf.integration/1.0',identity:snapshot.identity,scenes:[{id:sceneId,name:'Aurora'}]};
for(const version of ['2025-11-25','2025-06-18'])test(`real MCP ${version} initialize, discovery, pure status and exact mode`,async t=>{
 const dir=await mkdtemp(join(tmpdir(),'nano-protocol-'));t.after(()=>rm(dir,{recursive:true,force:true}));
 const rows={principals:[{id:'client',tokenSha256:createHash('sha256').update(token).digest('hex'),upstreamToken:upstream,scopes:['read','control']}]};
 const credentialsFile=join(dir,'credentials.json');await writeFile(credentialsFile,JSON.stringify(rows));
 const commands=[];let reads=0,pending;const ledger=new Map();
 const external=process.env.NANO_MCP_TEST_CONTROLLER_PORT;
 const controller=http.createServer(async(req,res)=>{
  assert.equal(req.headers.authorization,`Bearer ${upstream}`);
  if(req.method==='GET'){
   reads++;res.setHeader('Content-Type','application/json');
   if(req.url.startsWith('/controller/integration/v1/snapshot')){res.end(JSON.stringify(integrationSnapshot));return;}
   if(req.url.startsWith('/controller/integration/v1/animations')){res.end(JSON.stringify(animations));return;}
   res.end(JSON.stringify(pending?{...snapshot,state:{...snapshot.state,pending:[pending]}}:snapshot));return;
  }
  let body='';for await(const chunk of req)body+=chunk;const request=JSON.parse(body);commands.push(request);
  if(req.url==='/controller/integration/v1/commands'){
   const free=request.command.pattern!=='breathe';
   res.writeHead(free?202:422,{'Content-Type':'application/json'});
   res.end(JSON.stringify(free?{apiVersion:'nanoleaf.integration/1.0',requestId:request.requestId,outcome:'queued',priorEffects:'none',physicalOutcome:'unknown'}:{failure:{code:'unsupported-capability'}}));return;
  }
  const key=JSON.stringify(request.requestId),fingerprint=JSON.stringify(request);
  const fail=code=>{res.writeHead(409);res.end(JSON.stringify({failure:{code}}));};
  if(request.command.kind==='scene.activate'&&request.command.sceneId!==sceneId){res.writeHead(422);res.end(JSON.stringify({failure:{code:'unsupported-capability'}}));return;}
  if(request.expectedConfigurationRevision!==snapshot.configurationRevision){fail('revision-conflict');return;}
  if(ledger.has(key)&&ledger.get(key)!==fingerprint){fail('request-conflict');return;}
  if(request.requestId.sequence===401){res.destroy();return;}
  ledger.set(key,fingerprint);
  if(request.command.mode==='Free'){pending={requestId:request.requestId,command:request.command,generation:request.expectedGeneration};await new Promise(resolve=>setTimeout(resolve,2000));}
  res.writeHead(202,{'Content-Type':'application/json'});res.end(JSON.stringify({apiVersion:'1.0',controllerId:snapshot.identity.controllerId,deviceId:snapshot.identity.deviceId,requestId:request.requestId,configurationRevision:request.expectedConfigurationRevision,generation:request.expectedGeneration,outcome:'queued',priorEffects:'none',completedOperations:[],uncertainOperations:[]}));
 });if(!external){controller.listen(0,'127.0.0.1');await once(controller,'listening');t.after(()=>{controller.closeAllConnections();controller.close();});}
 const host=await startHost({enabled:true,port:0,controllerPort:external?Number(external):controller.address().port,controllerId:snapshot.identity.controllerId,deviceId:snapshot.identity.deviceId,transport:'loopback-http',credentialsFile});t.after(()=>host.close());
 assert.equal((await fetch(host.url+'/other',{method:'POST',body:'{}'})).status,404);
 let session,id=0;
 async function rpc(method,params,extra={}){const response=await fetch(host.url,{method:'POST',headers:{Authorization:`Bearer ${token}`,Accept:'application/json, text/event-stream','Content-Type':'application/json',...(session?{'Mcp-Session-Id':session,'MCP-Protocol-Version':version}:{}),...extra},body:JSON.stringify({jsonrpc:'2.0',...(method.startsWith('notifications/')?{}:{id:++id}),method,params})});const text=await response.text();return {response,body:text?JSON.parse(text):null};}
 const init=await rpc('initialize',{protocolVersion:version,capabilities:{},clientInfo:{name:'Codex-source-fixture',version:'0.153.4'}});assert.equal(init.response.status,200);session=init.response.headers.get('mcp-session-id');await rpc('notifications/initialized');
 const listed=await rpc('tools/list',{});assert.deepEqual(listed.body.result.tools.map(t=>t.name).sort(),['nanoleaf_animation_play','nanoleaf_animations_list','nanoleaf_mode_set','nanoleaf_scene_activate','nanoleaf_scenes_list','nanoleaf_status']);assert.equal(reads,0);assert.equal(commands.length,0);
 const status=await rpc('tools/call',{name:'nanoleaf_status',arguments:{}});if(!external)assert.deepEqual(status.body.result.structuredContent.data.snapshot,snapshot);else assert.deepEqual(status.body.result.structuredContent.data.snapshot.identity,snapshot.identity);assert.equal(commands.length,0);
 const args={requestId:snapshot.nextRequestId,expectedConfigurationRevision:snapshot.configurationRevision,expectedGeneration:snapshot.generation,mode:'Quiet'};
 const write=await rpc('tools/call',{name:'nanoleaf_mode_set',arguments:args});assert.equal(write.body.result.structuredContent.data.receipt.outcome,'queued');if(!external)assert.deepEqual(commands[0].requestId,args.requestId);
 const invalid=await rpc('tools/call',{name:'nanoleaf_mode_set',arguments:{...args,url:'http://unconfigured'}});assert.equal(invalid.body.result.isError,true);if(!external)assert.equal(commands.length,1);

 if(!external){
  const scenes=await rpc('tools/call',{name:'nanoleaf_scenes_list',arguments:{}});assert.deepEqual(scenes.body.result.structuredContent.data.scenes,integrationSnapshot.scenes);
  const sceneArgs={requestId:{...snapshot.nextRequestId,sequence:snapshot.nextRequestId.sequence+1000},expectedConfigurationRevision:snapshot.configurationRevision,expectedGeneration:snapshot.generation,sceneId};
  const activated=await rpc('tools/call',{name:'nanoleaf_scene_activate',arguments:sceneArgs});assert.equal(activated.body.result.structuredContent.data.receipt.outcome,'queued');assert.deepEqual(commands.at(-1).command,{kind:'scene.activate',sceneId});
  const options=await rpc('tools/call',{name:'nanoleaf_animations_list',arguments:{}});assert.deepEqual(options.body.result.structuredContent.data.animations,animations);
  const playArgs={requestId:animations.nextRequestId,expectedRevision:animations.revision,pattern:'wave',colors:['#0044aa','#00aa66'],speed:'slow'};
  const played=await rpc('tools/call',{name:'nanoleaf_animation_play',arguments:playArgs});assert.equal(played.body.result.structuredContent.data.receipt.outcome,'queued');
  assert.deepEqual(commands.at(-1),{apiVersion:'nanoleaf.integration/1.0',controllerId:snapshot.identity.controllerId,deviceId:snapshot.identity.deviceId,requestId:playArgs.requestId,expectedRevision:playArgs.expectedRevision,command:{kind:'animation.play',pattern:'wave',colors:['#0044aa','#00aa66'],speed:'slow'}});
  const refused=await rpc('tools/call',{name:'nanoleaf_animation_play',arguments:{...playArgs,pattern:'breathe',speed:'fast'}});assert.equal(refused.body.result.isError,true);assert.match(refused.body.result.structuredContent.data.message,/nanoleaf_mode_set/);
  const beforeInvalid=commands.length;const invalidAnimation=await rpc('tools/call',{name:'nanoleaf_animation_play',arguments:{...playArgs,pattern:'pulse',direction:'left'}});assert.equal(invalidAnimation.body.result.isError,true);assert.equal(commands.length,beforeInvalid);
  const unknownScene=await rpc('tools/call',{name:'nanoleaf_scene_activate',arguments:{...sceneArgs,requestId:{...sceneArgs.requestId,sequence:sceneArgs.requestId.sequence+1},sceneId:'scene-'+'d'.repeat(64)}});assert.equal(unknownScene.body.result.isError,true);assert.equal(unknownScene.body.result.structuredContent.data.code,'unsupported-capability');assert.equal(unknownScene.body.result.structuredContent.data.priorEffects,'none');
 }

 const wrongHost=await new Promise((resolve,reject)=>{const req=http.request(host.url,{method:'POST',headers:{Host:'localhost:1',Authorization:`Bearer ${token}`,'Content-Type':'application/json',Accept:'application/json, text/event-stream'}},res=>{res.resume();res.on('end',()=>resolve(res.statusCode));});req.on('error',reject);req.end(JSON.stringify({jsonrpc:'2.0',id:99,method:'tools/list',params:{}}));});assert.equal(wrongHost,403);
 assert.equal((await rpc('tools/list',{}, {Origin:'http://unconfigured.invalid'})).response.status,403);
 const replay=await rpc('tools/call',{name:'nanoleaf_mode_set',arguments:args});assert.deepEqual(replay.body.result.structuredContent.data.receipt,write.body.result.structuredContent.data.receipt);
 const concurrent=await Promise.all([rpc('tools/call',{name:'nanoleaf_mode_set',arguments:args}),rpc('tools/call',{name:'nanoleaf_mode_set',arguments:args})]);for(const result of concurrent)assert.deepEqual(result.body.result.structuredContent.data.receipt,write.body.result.structuredContent.data.receipt);
 const conflict=await rpc('tools/call',{name:'nanoleaf_mode_set',arguments:{...args,mode:'Work'}});assert.equal(conflict.body.result.structuredContent.data.code,'request-conflict');
 const stale=await rpc('tools/call',{name:'nanoleaf_mode_set',arguments:{...args,expectedConfigurationRevision:999}});assert.equal(stale.body.result.structuredContent.data.code,'revision-conflict');
 const outageTicket={...args.requestId,sequence:401};const outage=await rpc('tools/call',{name:'nanoleaf_mode_set',arguments:{...args,requestId:outageTicket}});assert.equal(outage.body.result.structuredContent.data.code,'uncertain-result');assert.equal(outage.body.result.structuredContent.data.priorEffects,'possible');assert.deepEqual(outage.body.result.structuredContent.data.requestId,outageTicket);
 const beforeCancellation=commands.length;
 const cancellationId=id+1,cancelTicket={...args.requestId,sequence:version==='2025-11-25'?101:201};
 const cancelled=rpc('tools/call',{name:'nanoleaf_mode_set',arguments:{...args,requestId:cancelTicket,mode:'Free'}});
 let admitted=false;
 for(let attempt=0;attempt<30;attempt++){
  const current=await rpc('tools/call',{name:'nanoleaf_status',arguments:{}});
  if(current.body.result.structuredContent.data.snapshot.state.pending.some(p=>p.command.mode==='Free'&&p.requestId.sequence===cancelTicket.sequence)){admitted=true;break;}
  await new Promise(resolve=>setTimeout(resolve,25));
 }
 assert.equal(admitted,true,'fake owner received the write before cancellation');
 await rpc('notifications/cancelled',{requestId:cancellationId,reason:'fixture cancellation'});
 assert.equal((await cancelled).response.status,204);
 if(!external)assert.equal(commands.length,beforeCancellation+1,'cancellation never resubmits');
 assert.equal((await rpc('tools/list',{}, {Authorization:'Bearer invalid'})).response.status,401);
 await writeFile(credentialsFile,JSON.stringify({principals:[{...rows.principals[0],scopes:['read']}]}));const readOnly=await rpc('tools/list',{});assert.deepEqual(readOnly.body.result.tools.map(t=>t.name).sort(),['nanoleaf_animations_list','nanoleaf_scenes_list','nanoleaf_status']);
 await writeFile(credentialsFile,JSON.stringify({principals:[]}));assert.equal((await rpc('tools/list',{})).response.status,401);
});
