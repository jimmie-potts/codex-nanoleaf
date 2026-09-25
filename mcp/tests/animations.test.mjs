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
 ['an unknown mode',{...animations,mode:'Media'}],['a malformed revision',{...animations,revision:'x'}],['an extra field',{...animations,tasks:[]}]])test(`rejects animation options from ${name}`,async()=>{
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
