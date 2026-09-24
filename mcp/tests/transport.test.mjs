import test from 'node:test';
import assert from 'node:assert/strict';
import { exchange } from '../dist/transport.js';
test('invalid controller destinations reject before transport',async()=>{
 await assert.rejects(exchange({transport:'loopback-http',controllerPort:0,deviceId:'../bad'},'snapshot','x'.repeat(43)));
});
test('an unknown transport identifier fails before any dispatch',async()=>{
 await assert.rejects(exchange({transport:'wsl-helper',controllerPort:41231,deviceId:'wall'},'command','a'.repeat(43),{}),error=>error.possible===false);
});
