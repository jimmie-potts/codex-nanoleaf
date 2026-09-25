import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { once } from 'node:events';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
import { invokeDeviceTool } from '@jimmie-potts/device-mcp';
import { bindings } from '../dist/tools.js';
import { loadConfig, CredentialStore } from '../dist/config.js';
import { startHost } from '../dist/server.js';

// #113: the NL22 Panels as a second fixed target beside the Lines.
const snapshot = JSON.parse(readFileSync(new URL('./snapshot.json', import.meta.url)));
const lines = { controllerId: snapshot.identity.controllerId, deviceId: snapshot.identity.deviceId };
const config = { ...lines, panelsDeviceId: 'panels' };
const panelsSnapshot = { ...snapshot, identity: { ...snapshot.identity, deviceId: 'panels' } };
const LINES_TOOLS = ['nanoleaf_status', 'nanoleaf_mode_set', 'nanoleaf_scenes_list', 'nanoleaf_scene_activate', 'nanoleaf_animations_list', 'nanoleaf_animation_play'];
const PANELS_TOOLS = ['nanoleaf_panels_status', 'nanoleaf_panels_mode_set', 'nanoleaf_panels_scenes_list', 'nanoleaf_panels_scene_activate'];
const principal = { id: 'alice', credential: { kind: 'machine', status: 'active', declared: true, devices: [lines.deviceId, 'panels'], scopes: ['read', 'control'] } };
const modeArgs = { requestId: snapshot.nextRequestId, expectedConfigurationRevision: snapshot.configurationRevision, expectedGeneration: snapshot.generation, mode: 'Free' };
const store = { forDispatch: async () => ({ upstreamToken: 'a'.repeat(43) }) };
const receiptFor = request => ({ apiVersion: '1.0', controllerId: request.controllerId, deviceId: request.deviceId, requestId: request.requestId, configurationRevision: request.expectedConfigurationRevision, generation: request.expectedGeneration, outcome: 'queued', priorEffects: 'none', completedOperations: [], uncertainOperations: [] });

test('a configured Panels target adds four fixed tools and no animation tool', () => {
    assert.deepEqual(bindings(config, store).tools.map(tool => tool.name), [...LINES_TOOLS, ...PANELS_TOOLS]);
    assert.deepEqual(bindings(lines, store).tools.map(tool => tool.name), LINES_TOOLS);
});

test('each tool addresses only its own fixed device', async () => {
    const calls = [];
    const { registry, tools } = bindings(config, store, async (target, operation, token, request) => {
        calls.push({ deviceId: target.deviceId, operation, request });
        if (operation === 'snapshot') return { status: 200, body: target.deviceId === 'panels' ? panelsSnapshot : snapshot };
        return { status: 202, body: receiptFor(request) };
    });
    const tool = name => tools.find(candidate => candidate.name === name);
    const status = await invokeDeviceTool(registry, tool('nanoleaf_panels_status'), {}, principal);
    assert.equal(status.structuredContent.data.snapshot.identity.deviceId, 'panels');
    const written = await invokeDeviceTool(registry, tool('nanoleaf_panels_mode_set'), modeArgs, principal);
    assert.equal(written.structuredContent.data.receipt.deviceId, 'panels');
    await invokeDeviceTool(registry, tool('nanoleaf_mode_set'), modeArgs, principal);
    assert.deepEqual(calls.map(call => [call.deviceId, call.operation, call.request?.deviceId]),
        [['panels', 'snapshot', undefined], ['panels', 'command', 'panels'], [lines.deviceId, 'command', lines.deviceId]]);
    // A Lines snapshot returned to a Panels tool is not accepted as the Panels' status.
    const crossed = bindings(config, store, async () => ({ status: 200, body: snapshot }));
    const refused = await invokeDeviceTool(crossed.registry, crossed.tools.find(t => t.name === 'nanoleaf_panels_status'), {}, principal);
    assert.equal(refused.isError, true);
});

test('a device argument is rejected before dispatch', async () => {
    let count = 0;
    const { registry, tools } = bindings(config, store, async () => { count++; return { status: 500, body: {} }; });
    for (const name of PANELS_TOOLS.concat(['nanoleaf_mode_set'])) {
        const tool = tools.find(candidate => candidate.name === name);
        const input = name.endsWith('mode_set') ? { ...modeArgs, deviceId: 'wall' } : { deviceId: 'wall' };
        assert.equal((await invokeDeviceTool(registry, tool, input, principal)).isError, true, name);
    }
    assert.equal(count, 0);
});

test('configuration accepts an optional distinct Panels device and credentials cover both', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'nano-panels-'));
    try {
        const token = 'x'.repeat(43);
        const credentialsFile = join(dir, 'credentials.json');
        await writeFile(credentialsFile, JSON.stringify({ principals: [{ id: 'alice', tokenSha256: createHash('sha256').update(token).digest('hex'), scopes: ['read'], upstreamToken: 'y'.repeat(43) }] }));
        const file = join(dir, 'config.json');
        const base = { enabled: true, port: 41230, controllerPort: 41231, controllerId: 'controller', deviceId: 'wall', transport: 'loopback-http', credentialsFile };
        await writeFile(file, JSON.stringify({ ...base, panelsDeviceId: 'panels' }));
        const loaded = await loadConfig(file);
        assert.equal(loaded.panelsDeviceId, 'panels');
        assert.deepEqual((await new CredentialStore(loaded).authenticate(token)).credential.devices, ['wall', 'panels']);
        await writeFile(file, JSON.stringify(base));
        assert.deepEqual((await new CredentialStore(await loadConfig(file)).authenticate(token)).credential.devices, ['wall']);
        for (const panelsDeviceId of ['wall', 'bad id', 7, '']) {
            await writeFile(file, JSON.stringify({ ...base, panelsDeviceId }));
            await assert.rejects(loadConfig(file), String(panelsDeviceId));
        }
    } finally { await rm(dir, { recursive: true, force: true }); }
});

test('real MCP discovery and a Panels mode call reach the Panels routes', async t => {
    const dir = await mkdtemp(join(tmpdir(), 'nano-panels-protocol-')); t.after(() => rm(dir, { recursive: true, force: true }));
    const token = 'a'.repeat(43), upstream = 'b'.repeat(43);
    const credentialsFile = join(dir, 'credentials.json');
    await writeFile(credentialsFile, JSON.stringify({ principals: [{ id: 'client', tokenSha256: createHash('sha256').update(token).digest('hex'), upstreamToken: upstream, scopes: ['read', 'control'] }] }));
    const seen = [];
    const controller = http.createServer(async (req, res) => {
        let body = ''; for await (const chunk of req) body += chunk;
        seen.push([req.method, req.url, body ? JSON.parse(body).deviceId : undefined]);
        res.setHeader('Content-Type', 'application/json');
        if (req.method === 'GET') { res.end(JSON.stringify(req.url.endsWith('deviceId=panels') ? panelsSnapshot : snapshot)); return; }
        res.writeHead(202); res.end(JSON.stringify(receiptFor(JSON.parse(body))));
    });
    controller.listen(0, '127.0.0.1'); await once(controller, 'listening');
    t.after(() => { controller.closeAllConnections(); controller.close(); });
    const host = await startHost({ enabled: true, port: 0, controllerPort: controller.address().port, ...config, transport: 'loopback-http', credentialsFile });
    t.after(() => host.close());
    let session, id = 0;
    const rpc = async (method, params) => {
        const response = await fetch(host.url, { method: 'POST', headers: { Authorization: `Bearer ${token}`, Accept: 'application/json, text/event-stream', 'Content-Type': 'application/json', ...(session ? { 'Mcp-Session-Id': session, 'MCP-Protocol-Version': '2025-11-25' } : {}) }, body: JSON.stringify({ jsonrpc: '2.0', ...(method.startsWith('notifications/') ? {} : { id: ++id }), method, params }) });
        const text = await response.text(); return { response, body: text ? JSON.parse(text) : null };
    };
    const init = await rpc('initialize', { protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'panels-fixture', version: '1' } });
    session = init.response.headers.get('mcp-session-id'); await rpc('notifications/initialized');
    const listed = await rpc('tools/list', {});
    assert.deepEqual(listed.body.result.tools.map(tool => tool.name).sort(), [...LINES_TOOLS, ...PANELS_TOOLS].sort());
    const status = await rpc('tools/call', { name: 'nanoleaf_panels_status', arguments: {} });
    assert.equal(status.body.result.structuredContent.data.snapshot.identity.deviceId, 'panels');
    const written = await rpc('tools/call', { name: 'nanoleaf_panels_mode_set', arguments: modeArgs });
    assert.equal(written.body.result.structuredContent.data.receipt.deviceId, 'panels');
    assert.deepEqual(seen, [['GET', '/controller/v1/snapshot?deviceId=panels', undefined], ['POST', '/controller/v1/commands', 'panels']]);
});

test('without a Panels target the Lines tool descriptions are unchanged', () => {
    const descriptions = bindings(lines, store).tools.map(tool => tool.description).join('\n');
    for (const text of ['Read the Nanoleaf controller snapshot', 'Request Work, Quiet or Free through the Nanoleaf controller.', 'Activate a saved Nanoleaf scene through the controller.', "List the Nanoleaf controller's advertised saved scenes"])
        assert.ok(descriptions.includes(text), text);
    assert.ok(!descriptions.includes('Nanoleaf Lines'));
    assert.ok(bindings(config, store).tools.find(tool => tool.name === 'nanoleaf_panels_status').description.includes('Nanoleaf Light Panels'));
});

test('the Panels scene tools list and activate on the Panels only', async () => {
    const sceneId = 'scene-' + 'e'.repeat(64);
    const calls = [];
    const { registry, tools } = bindings(config, store, async (target, operation, token, request) => {
        calls.push([target.deviceId, operation, request?.deviceId]);
        if (operation === 'scenes') return { status: 200, body: { apiVersion: 'nanoleaf.integration/1.0', identity: { ...snapshot.identity, deviceId: target.deviceId }, scenes: [{ id: sceneId, name: 'Forest' }] } };
        return { status: 202, body: receiptFor(request) };
    });
    const tool = name => tools.find(candidate => candidate.name === name);
    const listed = await invokeDeviceTool(registry, tool('nanoleaf_panels_scenes_list'), {}, principal);
    assert.deepEqual(listed.structuredContent.data.scenes, [{ id: sceneId, name: 'Forest' }]);
    const { mode, ...ticket } = modeArgs;
    const activated = await invokeDeviceTool(registry, tool('nanoleaf_panels_scene_activate'), { ...ticket, sceneId }, principal);
    assert.equal(activated.structuredContent.data.receipt.deviceId, 'panels');
    assert.deepEqual(calls, [['panels', 'scenes', undefined], ['panels', 'command', 'panels']]);
});
