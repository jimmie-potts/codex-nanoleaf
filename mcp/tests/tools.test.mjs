import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { invokeDeviceTool } from '@jimmie-potts/device-mcp';
import { bindings } from '../dist/tools.js';
const snapshot=JSON.parse(readFileSync(new URL('./snapshot.json',import.meta.url)));
export const config={controllerId:snapshot.identity.controllerId,deviceId:snapshot.identity.deviceId};
const principal={id:'alice',credential:{kind:'machine',status:'active',declared:true,devices:[config.deviceId],scopes:['read','control']}};
export const args={requestId:snapshot.nextRequestId,expectedConfigurationRevision:snapshot.configurationRevision,expectedGeneration:snapshot.generation,mode:'Work'};
test('fixed tools delegate status and preserve exact mode identity',async()=>{
 const calls=[];
 const receipt={apiVersion:'1.0',...config,requestId:args.requestId,configurationRevision:args.expectedConfigurationRevision,generation:args.expectedGeneration,outcome:'queued',priorEffects:'none',completedOperations:[],uncertainOperations:[]};
 const {registry,tools}=bindings(config,{forDispatch:async()=>({upstreamToken:'a'.repeat(43)})},async(c,operation,token,request)=>{calls.push({operation,request});return {status:operation==='snapshot'?200:202,body:operation==='snapshot'?snapshot:receipt};});
 assert.deepEqual(tools.map(t=>t.name),['nanoleaf_status','nanoleaf_mode_set']);
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
