import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { exchange } from '../dist/transport.js';
test('direct transport preserves controller response and fixed authenticated route',async()=>{
 let seen;
 const server=http.createServer((req,res)=>{seen={url:req.url,host:req.headers.host,auth:req.headers.authorization};res.writeHead(202,{'content-type':'application/json'});res.end('{"queued":true}');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const port=server.address().port;const result=await exchange({transport:'loopback-http',controllerPort:port,deviceId:'wall'},'snapshot','a'.repeat(43));assert.deepEqual(result,{status:202,body:{queued:true}});assert.deepEqual(seen,{url:'/controller/v1/snapshot?deviceId=wall',host:`127.0.0.1:${port}`,auth:`Bearer ${'a'.repeat(43)}`});}finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
for(const [name,status,body] of [['redirect',302,'{}'],['oversized',200,'x'.repeat(524289)],['malformed',200,'{'],['too deep',200,'['.repeat(34)+'0'+']'.repeat(34)]])test(`direct ${name} settles with possible effects after write`,async()=>{
 let count=0;const server=http.createServer((req,res)=>{count++;res.writeHead(status);res.end(body);});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{await assert.rejects(exchange({transport:'loopback-http',controllerPort:server.address().port,deviceId:'wall'},'command','a'.repeat(43),{}),error=>error.possible===true);assert.equal(count,1);}finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
test('total deadline bounds a trickle response without retry',async()=>{
 let count=0;const intervals=[];const server=http.createServer((req,res)=>{count++;res.writeHead(200);res.write('{');const timer=setInterval(()=>res.write(' '),30);intervals.push(timer);res.on('close',()=>clearInterval(timer));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{const start=Date.now();await assert.rejects(exchange({transport:'loopback-http',controllerPort:server.address().port,deviceId:'wall'},'command','a'.repeat(43),{}),error=>error.possible===true);assert.ok(Date.now()-start<9000);assert.equal(count,1);}finally{intervals.forEach(clearInterval);server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { loadConfig } from '../dist/config.js';
test('an installed configuration naming windows-http reaches the controller as loopback-http',async()=>{
 const server=http.createServer((req,res)=>{res.writeHead(200,{'content-type':'application/json'});res.end('{"ok":true}');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const dir=await mkdtemp(join(tmpdir(),'nano-alias-'));
 try{const credentialsFile=join(dir,'credentials.json');await writeFile(credentialsFile,'{"principals":[]}');
  const file=join(dir,'config.json');await writeFile(file,JSON.stringify({enabled:true,port:41230,controllerPort:server.address().port,controllerId:'controller',deviceId:'wall',transport:'windows-http',credentialsFile}));
  const config=await loadConfig(file);assert.equal(config.transport,'loopback-http');
  assert.deepEqual(await exchange(config,'snapshot','a'.repeat(43)),{status:200,body:{ok:true}});
 }finally{await rm(dir,{recursive:true,force:true});server.close();}
});
