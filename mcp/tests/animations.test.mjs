import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { invokeDeviceTool } from '@jimmie-potts/device-mcp';
import { bindings } from '../dist/tools.js';
const snapshot=JSON.parse(readFileSync(new URL('./snapshot.json',import.meta.url)));
const config={controllerId:snapshot.identity.controllerId,deviceId:snapshot.identity.deviceId};
const principal={id:'alice',credential:{kind:'machine',status:'active',declared:true,devices:[config.deviceId],scopes:['read','control']}};
const credentials={forDispatch:async()=>({upstreamToken:'a'.repeat(43)})};
const animations=JSON.parse(readFileSync(new URL('./animations.json',import.meta.url)));
const playArgs={requestId:animations.nextRequestId,expectedRevision:animations.revision,pattern:'wave',colors:['#0044aa','#00aa66'],speed:'slow'};
const receipt=(outcome,extra={})=>({apiVersion:'nanoleaf.integration/1.0',requestId:playArgs.requestId,outcome,priorEffects:outcome==='sent'?'confirmed-transmission':outcome==='uncertain'?'possible':'none',physicalOutcome:'unknown',...extra});
const tool=(b,name)=>b.tools.find(t=>t.name===name);

test('lists animation options with the identity values a play request needs',async()=>{
 const calls=[];
 const b=bindings(config,credentials,async(c,operation)=>{calls.push(operation);return {status:200,body:animations};});
 const result=await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animations_list'),{},principal);
 assert.equal(result.isError,false);
 assert.deepEqual(result.structuredContent.data,{kind:'animations',animations});
 assert.deepEqual(calls,['animations']);
});

for(const [name,body] of [['another device',{...animations,identity:{...snapshot.identity,deviceId:'other'}}],['another version',{...animations,apiVersion:'nanoleaf.integration/2.0'}],
 ['an unknown mode',{...animations,mode:'Media'}],['a malformed revision',{...animations,revision:'x'}],['an extra field',{...animations,tasks:[]}], ['malformed presets',{...animations,presets:[{id:'bad',pattern:'breathe',colors:['red'],speed:'slow'}]}], ['spatial direction on a non-spatial preset',{...animations,presets:[{id:'bad',pattern:'breathe',colors:['#ffffff'],speed:'slow',direction:'right'}]}], ['duplicate preset names',{...animations,presets:[animations.presets[0],animations.presets[0]]}]])test(`rejects animation options from ${name}`,async()=>{
 const b=bindings(config,credentials,async()=>({status:200,body}));
 const result=await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animations_list'),{},principal);
 assert.equal(result.isError,true);assert.equal(result.structuredContent.data.code,'transport-failure');
});

test('plays through the extension with the exact ticket, revision and fields',async()=>{
 const calls=[];
 const b=bindings(config,credentials,async(c,operation,token,request)=>{calls.push({operation,request});return {status:202,body:receipt('queued')};});
 const result=await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_play'),{...playArgs,direction:'outward',loop:false},principal);
 assert.equal(result.isError,false);
 assert.deepEqual(result.structuredContent.data,{kind:'receipt',receipt:receipt('queued')});
 assert.deepEqual(calls,[{operation:'extension-command',request:{apiVersion:'nanoleaf.integration/1.0',...config,requestId:playArgs.requestId,expectedRevision:playArgs.expectedRevision,
  command:{kind:'animation.play',pattern:'wave',colors:['#0044aa','#00aa66'],speed:'slow',direction:'outward',loop:false}}}]);
 const minimal=bindings(config,credentials,async(c,operation,token,request)=>{calls.push({operation,request});return {status:202,body:receipt('queued')};});
 await invokeDeviceTool(minimal.registry,tool(minimal,'nanoleaf_animation_play'),{requestId:playArgs.requestId,expectedRevision:playArgs.expectedRevision,pattern:'pulse',colors:['#ffffff']},principal);
 assert.deepEqual(calls.at(-1).request.command,{kind:'animation.play',pattern:'pulse',colors:['#ffffff']});
});

for(const [outcome,extra,error] of [['sent',{},false],['uncertain',{failure:{code:'uncertain-result'}},true],['failed',{failure:{code:'request-expired'}},true],['cancelled',{failure:{code:'stale-generation'}},true]])test(`preserves a replayed ${outcome} animation receipt`,async()=>{
 const b=bindings(config,credentials,async()=>({status:200,body:receipt(outcome,extra)}));
 const result=await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_play'),playArgs,principal);
 assert.equal(result.isError,error);assert.deepEqual(result.structuredContent.data,{kind:'receipt',receipt:receipt(outcome,extra)});
});

for(const [name,body] of [['another ticket',{...receipt('queued'),requestId:{...playArgs.requestId,sequence:4}}],['a configuration outcome',{...receipt('queued'),outcome:'applied',priorEffects:'configuration'}],
 ['a claimed physical outcome',{...receipt('sent'),physicalOutcome:'visible'}],['a v1 receipt',{apiVersion:'1.0',...config,requestId:playArgs.requestId,outcome:'queued'}]])test(`treats ${name} as an uncertain result`,async()=>{
 let count=0;const b=bindings(config,credentials,async()=>{count++;return {status:202,body};});
 const result=await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_play'),playArgs,principal);
 assert.equal(result.structuredContent.data.code,'uncertain-result');assert.equal(result.structuredContent.data.priorEffects,'possible');
 assert.deepEqual(result.structuredContent.data.requestId,playArgs.requestId);assert.equal(count,1);
});

test('a Work or Quiet rejection says to switch to Free first and switches nothing',async()=>{
 const calls=[];
 const b=bindings(config,credentials,async(c,operation,token,request)=>{calls.push(operation);return {status:422,body:{failure:{code:'unsupported-capability'}}};});
 const result=await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_play'),playArgs,principal);
 assert.equal(result.isError,true);
 const data=result.structuredContent.data;
 assert.equal(data.code,'unsupported-capability');assert.equal(data.priorEffects,'none');
 assert.match(data.message,/Free/);assert.match(data.message,/nanoleaf_mode_set/);assert.match(data.message,/Work or Quiet/);assert.match(data.message,/non-spatial/);assert.match(data.message,/nanoleaf_animations_list/);
 assert.match(result.content[0].text,/nanoleaf_mode_set/);
 assert.deepEqual(calls,['extension-command']);
});

for(const [status,code] of [[400,'invalid-request'],[409,'revision-conflict'],[409,'request-conflict'],[410,'request-expired'],[429,'capacity']])test(`preserves ${code} on HTTP ${status} without a switch message`,async()=>{
 const b=bindings(config,credentials,async()=>({status,body:{failure:{code}}}));
 const data=(await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_play'),playArgs,principal)).structuredContent.data;
 assert.equal(data.code,code);assert.equal(data.priorEffects,'none');assert.equal('message' in data,false);
});

test('invalid animation fields and revoked credentials never reach the controller',async()=>{
 let count=0;const b=bindings(config,credentials,async()=>{count++;return {status:202,body:receipt('queued')};});
 for(const input of [{...playArgs,pattern:'strobe'},{...playArgs,colors:[]},{...playArgs,colors:Array(9).fill('#ffffff')},{...playArgs,colors:['red']},
  {...playArgs,speed:'ludicrous'},{...playArgs,pattern:'pulse',direction:'left'},{...playArgs,direction:'north'},{...playArgs,loop:'yes'},{...playArgs,frames:[]},
  {...playArgs,deviceId:'other'},{...playArgs,expectedRevision:'x'}])
  assert.equal((await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_play'),input,principal)).isError,true,JSON.stringify(input));
 const revoked=bindings(config,{forDispatch:async()=>{throw Error('revoked');}},async()=>{count++;});
 assert.equal((await invokeDeviceTool(revoked.registry,tool(revoked,'nanoleaf_animations_list'),{},principal)).isError,true);
 assert.equal((await invokeDeviceTool(revoked.registry,tool(revoked,'nanoleaf_animation_play'),playArgs,principal)).isError,true);
 assert.equal(count,0);
});

test('a lost response after possible admission keeps the ticket and never retries',async()=>{
 const {TransportFailure}=await import('../dist/transport.js');
 let count=0;const b=bindings(config,credentials,async()=>{count++;throw new TransportFailure(true);});
 const data=(await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_play'),playArgs,principal)).structuredContent.data;
 assert.deepEqual([data.code,data.priorEffects,data.requestId,count],['uncertain-result','possible',playArgs.requestId,1]);
});

for (const direction of ['clockwise', 'counterclockwise']) test(`advertises and forwards ${direction} at faster speed`, async () => {
 const calls = [];
 const b = bindings(config, credentials, async (c, operation, token, request) => {
  calls.push(request); return {status: 202, body: receipt('queued')};
 });
 const play = tool(b, 'nanoleaf_animation_play');
 assert.ok(play.inputSchema.properties.direction.enum.includes(direction));
 assert.ok(play.inputSchema.properties.speed.enum.includes('faster'));
 for (const pattern of ['wave', 'gradient']) {
  const result = await invokeDeviceTool(b.registry, play, {...playArgs, pattern, direction, speed: 'faster'}, principal);
  assert.equal(result.isError, false);
  assert.deepEqual(calls.at(-1).command, {kind: 'animation.play', pattern, colors: playArgs.colors, direction, speed: 'faster'});
 }
 for (const pattern of ['pulse', 'breathe', 'sparkle']) {
  const result = await invokeDeviceTool(b.registry, play, {...playArgs, pattern, direction, speed: 'faster'}, principal);
  assert.equal(result.isError, true);
 }
 assert.equal(calls.length, 2);
});

test('preset play forwards only the name and refuses every explicit override', async () => {
 const calls = [];
 const b = bindings(config, credentials, async(c, operation, token, request) => {
  calls.push(request); return {status:202, body:receipt('queued')};
 });
 const args = {requestId:playArgs.requestId, expectedRevision:playArgs.expectedRevision, preset:'ocean'};
 const result = await invokeDeviceTool(b.registry, tool(b,'nanoleaf_animation_play'), args, principal);
 assert.equal(result.isError, false);
 assert.deepEqual(calls[0].command, {kind:'animation.play', preset:'ocean'});
 for (const [key,value] of Object.entries({pattern:'wave',colors:['#ffffff'],speed:'fast',direction:'right',loop:false})) {
  assert.equal((await invokeDeviceTool(b.registry, tool(b,'nanoleaf_animation_play'), {...args,[key]:value},principal)).isError,true);
 }
 assert.equal(calls.length,1);
});

test('saves, renames, forgets and replays favorites without changing mode', async () => {
 const calls=[];
 const b=bindings(config,credentials,async(c,operation,token,request)=>{
  calls.push({operation,request});
  return {status:200,body:receipt(request.command.kind==='animation.play'?'sent':'applied',
   {priorEffects:request.command.kind==='animation.play'?'confirmed-transmission':'configuration'})};
 });
 const common={requestId:playArgs.requestId,expectedRevision:playArgs.expectedRevision};
 for(const [name,input,command] of [
  ['nanoleaf_animation_save',{name:'my ripple',animation:{preset:'ocean'}},{kind:'animation.save',name:'my ripple',animation:{preset:'ocean'}}],
  ['nanoleaf_animation_rename',{name:'my ripple',newName:'favorite'},{kind:'animation.rename',name:'my ripple',newName:'favorite'}],
  ['nanoleaf_animation_forget',{name:'favorite'},{kind:'animation.forget',name:'favorite'}],
  ['nanoleaf_animation_play',{favorite:'favorite'},{kind:'animation.play',favorite:'favorite'}],
 ]){
  const binding=tool(b,name);assert.ok(binding,name);
  const result=await invokeDeviceTool(b.registry,binding,{...common,...input},principal);
  assert.equal(result.isError,false,JSON.stringify(result));
  assert.deepEqual(calls.at(-1),{operation:'extension-command',request:{apiVersion:'nanoleaf.integration/1.0',...config,...common,command}});
 }
 assert.equal(calls.length,4);
});

for (const [label, favorites] of [
 ['duplicate names',[animations.favorites[0],animations.favorites[0]]],
 ['blank name',[{...animations.favorites[0],name:' '}]],
 ['control in name',[{...animations.favorites[0],name:'a\n'}]],
 ['too many',Array(33).fill(animations.favorites[0])],
 ['unresolved recipe',[{name:'bad',animation:{preset:'cozy'}}]],
 ['missing defaults',[{name:'bad',animation:{pattern:'wave',colors:['#ffffff']}}]],
 ['bad direction',[{name:'bad',animation:{pattern:'pulse',colors:['#ffffff'],speed:'fast',loop:true,direction:'clockwise'}}]],
]) test(`rejects favorite listing with ${label}`,async()=>{
 const b=bindings(config,credentials,async()=>({status:200,body:{...animations,favorites}}));
 const result=await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animations_list'),{},principal);
 assert.equal(result.structuredContent.data.code,'transport-failure');
});

test('favorite edits reject malformed names and recipes before dispatch',async()=>{
 let count=0;const b=bindings(config,credentials,async()=>{count++;return {status:202,body:receipt('queued')};});
 const common={requestId:playArgs.requestId,expectedRevision:playArgs.expectedRevision};
 for(const name of ['', ' ', 'x'.repeat(81), 'a\n', 'a\u200bb']){
  for(const [toolName,args] of [
   ['nanoleaf_animation_save',{name,animation:{preset:'cozy'}}],
   ['nanoleaf_animation_rename',{name:'old',newName:name}],
   ['nanoleaf_animation_forget',{name}],
   ['nanoleaf_animation_play',{favorite:name}],
  ])assert.equal((await invokeDeviceTool(b.registry,tool(b,toolName),{...common,...args},principal)).isError,true);
 }
 for(const animation of [{},{favorite:'old'},{preset:'cozy',loop:false},{pattern:'pulse',colors:['#ffffff'],direction:'right'},
  {kind:'animation.play',preset:'cozy'},{pattern:'wave',colors:['red']},{pattern:'wave',colors:['#ffffff'],extra:42}])
  assert.equal((await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_save'),{...common,name:'safe',animation},principal)).isError,true);
 for(const args of [{favorite:'name',preset:'cozy'},{favorite:'name',loop:false},{favorite:'name',pattern:'wave',colors:['#ffffff']}])
  assert.equal((await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_play'),{...common,...args},principal)).isError,true);
 assert.equal(count,0);
});

for(const [label,body] of [
 ['a transport receipt',receipt('sent')],
 ['another ticket',receipt('applied',{priorEffects:'configuration',requestId:{...playArgs.requestId,sequence:99}})],
 ['inconsistent prior effects',receipt('applied')],
 ['configuration on failure',receipt('failed',{priorEffects:'configuration',failure:{code:'capacity'}})],
 ['claimed physical output',receipt('applied',{priorEffects:'configuration',physicalOutcome:'visible'})],
])test(`favorite save treats ${label} as uncertain and never retries`,async()=>{
 let count=0;const b=bindings(config,credentials,async()=>{count++;return {status:200,body};});
 const args={requestId:playArgs.requestId,expectedRevision:playArgs.expectedRevision,name:'new',animation:{preset:'cozy'}};
 const data=(await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_save'),args,principal)).structuredContent.data;
 assert.equal(data.code,'uncertain-result');assert.equal(data.priorEffects,'possible');assert.deepEqual(data.requestId,args.requestId);assert.equal(count,1);
});

test('favorite edits preserve collision and missing-name failures without Free guidance',async()=>{
 for(const [status,code] of [[409,'revision-conflict'],[422,'unsupported-capability'],[429,'capacity']]){
  const b=bindings(config,credentials,async()=>({status,body:{failure:{code}}}));
  const args={requestId:playArgs.requestId,expectedRevision:playArgs.expectedRevision,name:'old',newName:'occupied'};
  const result=await invokeDeviceTool(b.registry,tool(b,'nanoleaf_animation_rename'),args,principal);
  assert.equal(result.structuredContent.data.code,code);assert.equal(result.structuredContent.data.priorEffects,'none');assert.equal('message' in result.structuredContent.data,false);
 }
});

test('favorite tools honor read-only scope and current credential revocation',async()=>{
 let count=0;const transport=async()=>{count++;return {status:202,body:receipt('queued')};};
 const b=bindings(config,credentials,transport), revoked=bindings(config,{forDispatch:async()=>{throw Error('revoked');}},transport);
 for(const [name,fields] of [
  ['nanoleaf_animation_save',{name:'one',animation:{preset:'cozy'}}],
  ['nanoleaf_animation_rename',{name:'one',newName:'two'}],
  ['nanoleaf_animation_forget',{name:'one'}],
 ]){
  const args={requestId:playArgs.requestId,expectedRevision:playArgs.expectedRevision,...fields};
  assert.equal((await invokeDeviceTool(b.registry,tool(b,name),args,{...principal,credential:{...principal.credential,scopes:['read']}})).isError,true);
  assert.equal((await invokeDeviceTool(revoked.registry,tool(revoked,name),args,principal)).isError,true);
 }
 assert.equal(count,0);
});
