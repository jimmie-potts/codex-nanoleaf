import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { invokeDeviceTool } from '@jimmie-potts/device-mcp';
import { bindings } from '../dist/tools.js';
import { TransportFailure } from '../dist/transport.js';
const snapshot = JSON.parse(readFileSync(new URL('./snapshot.json', import.meta.url)));
const options = JSON.parse(readFileSync(new URL('./animations.json', import.meta.url)));
const config = {controllerId: snapshot.identity.controllerId, deviceId: snapshot.identity.deviceId};
const principal = {id: 'alice', credential: {kind: 'machine', status: 'active', declared: true, devices: [config.deviceId], scopes: ['read', 'control']}};
const args = {requestId: snapshot.nextRequestId, expectedConfigurationRevision: snapshot.configurationRevision, expectedGeneration: snapshot.generation};
const sceneId = 'scene-' + 'c'.repeat(64);
const credentials = {forDispatch: async () => ({upstreamToken: 'a'.repeat(43)})};
const receipt = {apiVersion: '1.0', ...config, requestId: args.requestId, configurationRevision: args.expectedConfigurationRevision, generation: args.expectedGeneration, outcome: 'queued', priorEffects: 'none', completedOperations: [], uncertainOperations: []};
const invoke = b => { const tool = b.tools.find(t => t.name === 'nanoleaf_scene_restore'); assert.ok(tool, 'restore is advertised'); return invokeDeviceTool(b.registry, tool, args, principal); };

test('restore sends exactly one existing scene activation with the caller identity', async () => {
 const calls = [];
 const b = bindings(config, credentials, async (c, operation, token, request) => {
  calls.push({operation, request});
  return operation === 'animations' ? {status: 200, body: {...options, rememberedSceneId: sceneId}} : {status: 202, body: receipt};
 });
 const result = await invoke(b);
 assert.deepEqual(result.structuredContent.data, {kind: 'receipt', receipt});
 assert.deepEqual(calls, [{operation: 'animations', request: undefined}, {operation: 'command', request: {apiVersion: '1.0', ...config, ...args, command: {kind: 'scene.activate', sceneId}}}]);
});

for (const mode of ['Work', 'Quiet', 'Free']) test(`restore in ${mode} with no available target dispatches nothing`, async () => {
 const calls = [];
 const b = bindings(config, credentials, async (c, operation) => {calls.push(operation); return {status: 200, body: {...options, mode, rememberedSceneId: mode === 'Free' ? null : sceneId}};});
 const result = await invoke(b), data = result.structuredContent.data;
 assert.equal(result.isError, true); assert.equal(data.code, 'unsupported-capability'); assert.equal(data.priorEffects, 'none');
 assert.deepEqual(data.requestId, args.requestId); assert.deepEqual(calls, ['animations']);
 assert.match(data.message, mode === 'Free' ? /remembered scene/i : /switch to Free.*nanoleaf_mode_set/);
});

test('restore rechecks revoked authority after discovery before command dispatch', async () => {
 const calls = []; let checks = 0;
 const b = bindings(config, {forDispatch: async () => {if (++checks > 1) throw Error('revoked'); return {upstreamToken: 'a'.repeat(43)};}}, async (c, operation) => {calls.push(operation); return {status: 200, body: {...options, rememberedSceneId: sceneId}};});
 assert.equal((await invoke(b)).structuredContent.data.code, 'forbidden');
 assert.deepEqual(calls, ['animations']);
});

test('restore preserves uncertainty without retry and a raced mode rejection receipt', async () => {
 for (const uncertain of [true, false]) {
  const calls = [];
  const failed = {...receipt, outcome: 'failed', failure: {code: 'unsupported-capability'}};
  const b = bindings(config, credentials, async (c, operation) => {
   calls.push(operation);
   if (operation === 'animations') return {status: 200, body: {...options, rememberedSceneId: sceneId}};
   if (uncertain) throw new TransportFailure(true);
   return {status: 422, body: failed};
  });
  const data = (await invoke(b)).structuredContent.data;
  if (uncertain) {assert.equal(data.code, 'uncertain-result'); assert.equal(data.priorEffects, 'possible'); assert.deepEqual(data.requestId, args.requestId);}
  else {assert.deepEqual(data.receipt, failed); assert.match(data.message, /switch to Free.*nanoleaf_mode_set/);}
  assert.deepEqual(calls, ['animations', 'command']);
 }
});

for (const rememberedSceneId of [undefined, 'private-name', 123]) test(`invalid remembered ID ${rememberedSceneId} fails without command dispatch`, async () => {
 const calls = [];
 const b = bindings(config, credentials, async (c, operation) => {calls.push(operation); return {status: 200, body: {...options, rememberedSceneId}};});
 assert.equal((await invoke(b)).structuredContent.data.code, 'transport-failure'); assert.deepEqual(calls, ['animations']);
});
