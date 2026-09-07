// Arguments are explicit fixture runtime paths, never personal credentials.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { exchange } from '../dist/transport.js';
const [port,windowsPython,windowsHelper]=process.argv.slice(2);
const snapshot=JSON.parse(readFileSync(new URL('./snapshot.json',import.meta.url)));
const config={transport:'wsl-helper',controllerPort:Number(port),deviceId:snapshot.identity.deviceId,windowsPython,windowsHelper};
const status=await exchange(config,'snapshot','b'.repeat(43));assert.equal(status.status,200);assert.deepEqual(status.body,snapshot);
const request={apiVersion:'1.0',controllerId:snapshot.identity.controllerId,deviceId:snapshot.identity.deviceId,requestId:snapshot.nextRequestId,expectedConfigurationRevision:snapshot.configurationRevision,expectedGeneration:snapshot.generation,command:{kind:'mode.set',mode:'Quiet'}};
const result=await exchange(config,'command','b'.repeat(43),request);assert.equal(result.status,202);assert.deepEqual(result.body.requestId,request.requestId);assert.equal(result.body.outcome,'queued');
console.log('Actual Windows helper preserved fixed status and mode exchange from this Node host.');
