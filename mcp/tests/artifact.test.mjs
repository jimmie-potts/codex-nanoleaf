import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile,writeFile,mkdir,mkdtemp,rm } from 'node:fs/promises';
import { dirname,resolve,join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { verifyArchiveChecksum,verifyInstalledMcpPackage } from '@jimmie-potts/device-mcp';
test('immutable archive and installed manifest reject corrupted bytes',async()=>{
 const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
 await assert.rejects(verifyArchiveChecksum(resolve(root,'vendor/jimmie-potts-device-mcp-1.0.0.tgz'),'0'.repeat(64)));
 const installed=resolve(dirname(fileURLToPath(import.meta.resolve('@jimmie-potts/device-mcp'))),'..');
 const dir=await mkdtemp(join(tmpdir(),'nano-artifact-'));
 try{
  async function copyManifest(source,destination){const raw=await readFile(join(source,'manifest.json'));const manifest=JSON.parse(raw);await mkdir(destination,{recursive:true});await writeFile(join(destination,'manifest.json'),raw);for(const name of Object.keys(manifest.files)){await mkdir(dirname(join(destination,name)),{recursive:true});await writeFile(join(destination,name),await readFile(join(source,name)));}}
  await copyManifest(installed,dir);await copyManifest(join(installed,'node_modules/@jimmie-potts/device-contracts'),join(dir,'node_modules/@jimmie-potts/device-contracts'));
  await verifyInstalledMcpPackage(dir);await writeFile(join(dir,'dist/index.js'),'// corrupted\n');await assert.rejects(verifyInstalledMcpPackage(dir));
 }finally{await rm(dir,{recursive:true,force:true});}
});
