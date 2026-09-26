import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { invokeDeviceTool } from '@jimmie-potts/device-mcp';
import { bindings } from '../dist/tools.js';
const snapshot=JSON.parse(readFileSync(new URL('./snapshot.json',import.meta.url)));
export const config={controllerId:snapshot.identity.controllerId,deviceId:snapshot.identity.deviceId};
const principal={id:'alice',credential:{kind:'machine',status:'active',declared:true,devices:[config.deviceId],scopes:['read','control']}};
export const args={requestId:snapshot.nextRequestId,expectedConfigurationRevision:snapshot.configurationRevision,expectedGeneration:snapshot.generation,mode:'Work'};
const sceneId='scene-'+'a'.repeat(64);
const sceneArgs={requestId:snapshot.nextRequestId,expectedConfigurationRevision:snapshot.configurationRevision,expectedGeneration:snapshot.generation,sceneId};
const integrationSnapshot={apiVersion:'nanoleaf.integration/1.0',identity:snapshot.identity,scenes:[{id:sceneId,name:'Aurora'},{id:'scene-'+'b'.repeat(64)}]};
test('fixed tools delegate status and preserve exact mode identity',async()=>{
 const calls=[];
 const receipt={apiVersion:'1.0',...config,requestId:args.requestId,configurationRevision:args.expectedConfigurationRevision,generation:args.expectedGeneration,outcome:'queued',priorEffects:'none',completedOperations:[],uncertainOperations:[]};
 const {registry,tools}=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async(c,operation,token,request)=>{calls.push({operation,request});return {status:operation==='snapshot'?200:202,body:operation==='snapshot'?snapshot:receipt};});
 assert.deepEqual(tools.map(t=>t.name),['nanoleaf_status','nanoleaf_mode_set','nanoleaf_scenes_list','nanoleaf_scene_activate','nanoleaf_animations_list','nanoleaf_animation_play','nanoleaf_scene_restore','nanoleaf_animation_save','nanoleaf_animation_rename','nanoleaf_animation_forget']);
 const read=await invokeDeviceTool(registry,tools[0],{},principal);assert.deepEqual(read.structuredContent.data.snapshot,snapshot);
 const write=await invokeDeviceTool(registry,tools[1],args,principal);assert.deepEqual(write.structuredContent.data.receipt,receipt);
 assert.deepEqual(calls[1].request,{apiVersion:'1.0',...config,requestId:args.requestId,expectedConfigurationRevision:args.expectedConfigurationRevision,expectedGeneration:args.expectedGeneration,command:{kind:'mode.set',mode:'Work'}});
});
for(const outcome of ['queued','sent','failed','partially-applied','uncertain','cancelled'])test(`preserves ${outcome} receipt without interpreting visible output`,async()=>{
 const receipt={apiVersion:'1.0',...config,requestId:args.requestId,configurationRevision:7,generation:args.expectedGeneration,outcome,priorEffects:['sent','partially-applied'].includes(outcome)?'confirmed-transmission':outcome==='uncertain'?'possible':'none',completedOperations:['sent','partially-applied'].includes(outcome)?['op1']:[],uncertainOperations:['uncertain','partially-applied'].includes(outcome)?['op2']:[],...(['failed','partially-applied','uncertain'].includes(outcome)?{failure:{code:'transport-failure'}}:{})};
 const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async()=>({status:200,body:receipt}));
 assert.deepEqual((await invokeDeviceTool(b.registry,b.tools[1],args,principal)).structuredContent.data.receipt,receipt);
});
for(const [name,response] of [['wrong target',{status:200,body:{}}],['malformed',{status:200,body:'bad'}],['redirect',{status:302,body:{}}]])test(`${name} after write preserves uncertainty and does not retry`,async()=>{
 let count=0;const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async()=>{count++;return response;});
 const result=await invokeDeviceTool(b.registry,b.tools[1],args,principal);assert.equal(result.structuredContent.data.code,'uncertain-result');assert.equal(result.structuredContent.data.priorEffects,'possible');assert.deepEqual(result.structuredContent.data.requestId,args.requestId);assert.equal(count,1);
});
for(const mode of ['Quiet','Free','Work'])test(`supports only declared mode ${mode}`,async()=>{
 let received;const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async(c,o,t,r)=>{received=r;return {status:409,body:{failure:{code:'revision-conflict'}}};});
 const result=await invokeDeviceTool(b.registry,b.tools[1],{...args,mode},principal);assert.equal(received.command.mode,mode);assert.equal(result.structuredContent.data.code,'revision-conflict');assert.equal(result.structuredContent.data.priorEffects,'none');
});
test('invalid capabilities, targets and current dispatch revocation prevent upstream effects',async()=>{
 let count=0;const b=bindings(config,{forDispatch:async()=>{throw Error('revoked');}},async()=>{count++;});
 for(const input of [{...args,deviceId:'other'},{...args,mode:'Monitor'},{...args,path:'secret'},args])assert.equal((await invokeDeviceTool(b.registry,b.tools[1],input,principal)).isError,true);
 assert.equal(count,0);
});

for(const [status,code] of [[409,'revision-conflict'],[409,'stale-generation'],[422,'unsupported-capability'],[503,'transport-failure']])test(`preserves reserved ${code} receipt on HTTP ${status}`,async()=>{
 const receipt={apiVersion:'1.0',...config,requestId:args.requestId,configurationRevision:7,generation:args.expectedGeneration,outcome:'failed',priorEffects:'none',completedOperations:[],uncertainOperations:[],failure:{code}};
 const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async()=>({status,body:receipt}));
 const result=await invokeDeviceTool(b.registry,b.tools[1],args,principal);
 assert.equal(result.isError,true);assert.deepEqual(result.structuredContent.data,{kind:'receipt',receipt});
 for(const body of [{...receipt,deviceId:'other'},{...receipt,requestId:{...args.requestId,sequence:args.requestId.sequence+1}},{...receipt,priorEffects:'invalid'}]){
  const invalid=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async()=>({status,body}));
  const rejected=await invokeDeviceTool(invalid.registry,invalid.tools[1],args,principal);
  assert.equal(rejected.structuredContent.data.code,'uncertain-result');assert.equal(rejected.structuredContent.data.priorEffects,'possible');
 }
});

test('lists advertised scenes with their IDs and names',async()=>{
 const calls=[];
 const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async(c,operation,token)=>{calls.push(operation);return {status:200,body:integrationSnapshot};});
 const result=await invokeDeviceTool(b.registry,b.tools[2],{},principal);
 assert.deepEqual(result.structuredContent.data,{kind:'scenes',scenes:integrationSnapshot.scenes});
 assert.deepEqual(calls,['scenes']);
});

test('rejects a scene list from the wrong controller or device',async()=>{
 const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async()=>({status:200,body:{...integrationSnapshot,identity:{...snapshot.identity,deviceId:'other'}}}));
 const result=await invokeDeviceTool(b.registry,b.tools[2],{},principal);
 assert.equal(result.isError,true);assert.equal(result.structuredContent.data.code,'transport-failure');
});

test('activates a scene through the controller, preserving the exact request identity',async()=>{
 const calls=[];
 const receipt={apiVersion:'1.0',...config,requestId:sceneArgs.requestId,configurationRevision:sceneArgs.expectedConfigurationRevision,generation:sceneArgs.expectedGeneration,outcome:'sent',priorEffects:'confirmed-transmission',completedOperations:['op1'],uncertainOperations:[]};
 const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async(c,operation,token,request)=>{calls.push({operation,request});return {status:200,body:receipt};});
 const result=await invokeDeviceTool(b.registry,b.tools[3],sceneArgs,principal);
 assert.deepEqual(result.structuredContent.data,{kind:'receipt',receipt});
 assert.deepEqual(calls[0].request,{apiVersion:'1.0',...config,requestId:sceneArgs.requestId,expectedConfigurationRevision:sceneArgs.expectedConfigurationRevision,expectedGeneration:sceneArgs.expectedGeneration,command:{kind:'scene.activate',sceneId}});
});

for(const [status,code] of [[422,'unsupported-capability']])test(`preserves a Work/Quiet rejection receipt on HTTP ${status}`,async()=>{
 const receipt={apiVersion:'1.0',...config,requestId:sceneArgs.requestId,configurationRevision:7,generation:sceneArgs.expectedGeneration,outcome:'failed',priorEffects:'none',completedOperations:[],uncertainOperations:[],failure:{code}};
 const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async()=>({status,body:receipt}));
 const result=await invokeDeviceTool(b.registry,b.tools[3],sceneArgs,principal);
 assert.equal(result.isError,true);assert.deepEqual(result.structuredContent.data,{kind:'receipt',receipt});
});

test('rejects an unknown scene as unsupported-capability, with no receipt',async()=>{
 const b=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async()=>({status:422,body:{failure:{code:'unsupported-capability'}}}));
 const result=await invokeDeviceTool(b.registry,b.tools[3],sceneArgs,principal);
 assert.equal(result.isError,true);assert.equal(result.structuredContent.data.code,'unsupported-capability');assert.equal(result.structuredContent.data.priorEffects,'none');
});

test('scene tools require their matching scope and never dispatch when revoked',async()=>{
 let count=0;
 const b=bindings(config,{forDispatch:async()=>{throw Error('revoked');}},async()=>{count++;});
 assert.equal((await invokeDeviceTool(b.registry,b.tools[2],{},principal)).isError,true);
 assert.equal((await invokeDeviceTool(b.registry,b.tools[3],sceneArgs,principal)).isError,true);
 assert.equal(count,0);
});
