import test from 'node:test';
import assert from 'node:assert/strict';
import { exchange } from '../dist/transport.js';
test('invalid controller destinations reject before transport',async()=>{
 await assert.rejects(exchange({transport:'windows-http',controllerPort:0,deviceId:'../bad'},'snapshot','x'.repeat(43)));
});
import { mkdtemp,writeFile,rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
for(const [name,script] of [['stdout limit',"process.stdout.write('x'.repeat(524500));setTimeout(()=>{},20000);"],['stderr limit',"process.stderr.write('x'.repeat(4097));setTimeout(()=>{},20000);"],['malformed output',"process.stdout.write('bad');"],['timeout',"setTimeout(()=>{},20000);"]])test(`helper ${name} settles with bounded uncertainty`,async()=>{
 const dir=await mkdtemp(join(tmpdir(),'nano helper space '));try{const file=join(dir,'fixture.cjs');await writeFile(file,script);const start=Date.now();await assert.rejects(exchange({transport:'wsl-helper',controllerPort:41231,deviceId:'wall',windowsPython:process.execPath,windowsHelper:file},'command','a'.repeat(43),{}),error=>error.possible===true);assert.ok(Date.now()-start<9000);}finally{await rm(dir,{recursive:true,force:true});}
});
test('missing helper runtime fails before possible dispatch',async()=>{
 await assert.rejects(exchange({transport:'wsl-helper',controllerPort:41231,deviceId:'wall',windowsPython:join(tmpdir(),'nano-no-such-runtime'),windowsHelper:'unused'},'command','a'.repeat(43),{}),error=>error.possible===false);
});
