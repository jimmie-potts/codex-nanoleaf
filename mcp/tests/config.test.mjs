import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { loadConfig, CredentialStore, boundedFile } from '../dist/config.js';
const token = 'x'.repeat(43), upstreamToken = 'y'.repeat(43);
const row = {id:'alice', tokenSha256:createHash('sha256').update(token).digest('hex'), scopes:['read','control'], upstreamToken};
test('private credential replacement revokes new authentication and dispatch', async () => {
 const dir=await mkdtemp(join(tmpdir(),'nano-mcp-'));
 try {
  const credentialsFile=join(dir,'credentials.json');
  await writeFile(credentialsFile,JSON.stringify({principals:[row]}));
  const configFile=join(dir,'config.json');
  await writeFile(configFile,JSON.stringify({enabled:true,port:41230,controllerPort:41231,controllerId:'controller',deviceId:'wall',transport:'windows-http',credentialsFile}));
  const config=await loadConfig(configFile), store=new CredentialStore(config);
  assert.equal((await store.authenticate(token)).id,'alice');
  assert.equal((await store.forDispatch('alice','control')).upstreamToken,upstreamToken);
  await writeFile(credentialsFile,JSON.stringify({principals:[{...row,scopes:['read']}]}));
  await assert.rejects(store.forDispatch('alice','control'));
  await writeFile(credentialsFile,JSON.stringify({principals:[]}));
  assert.equal(await store.authenticate(token),null);
  await assert.rejects(store.forDispatch('alice','read'));
 } finally {await rm(dir,{recursive:true,force:true});}
});
test('configuration fails closed on unknown keys and duplicate credentials', async()=>{
 const dir=await mkdtemp(join(tmpdir(),'nano-mcp-'));try{
 const file=join(dir,'credentials.json');const store=new CredentialStore({deviceId:'wall',credentialsFile:file});
 for(const value of [{principals:[row,row]},{principals:[{...row,scopes:['admin']}]},{principals:[{...row,extra:true}]}, {principals:[{...row,upstreamToken:'short'}]}]){await writeFile(file,JSON.stringify(value));assert.equal(await store.authenticate(token),null);}
 await writeFile(file,' '.repeat(65537));assert.equal(await store.authenticate(token),null);
 await writeFile(file,'{');assert.equal(await store.authenticate(token),null);
 await rm(file);assert.equal(await store.authenticate(token),null);
 await writeFile(file,JSON.stringify({enabled:true,port:41230,controllerPort:41231,controllerId:'c',deviceId:'d',transport:'windows-http',credentialsFile:file,url:'http://example.com'}));await assert.rejects(loadConfig(file));
 }finally{await rm(dir,{recursive:true,force:true});}
});

test('non-regular credential path rejects before reading',async()=>{await assert.rejects(boundedFile(tmpdir()));});
test('FIFO configuration is rejected without waiting for a writer',{skip:process.platform==='win32'},async()=>{
 const {execFileSync}=await import('node:child_process');const dir=await mkdtemp(join(tmpdir(),'nano-fifo-'));
 try{const file=join(dir,'config');execFileSync('mkfifo',[file]);await assert.rejects(Promise.race([boundedFile(file),new Promise((_,reject)=>setTimeout(()=>reject(new Error('FIFO wait')),300))]),error=>!error.message.includes('FIFO wait'));}finally{await rm(dir,{recursive:true,force:true});}
});
