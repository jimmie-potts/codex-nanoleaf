import test from 'node:test';
import assert from 'node:assert/strict';
import { startHost } from '../dist/server.js';
import http from 'node:http';
import { once } from 'node:events';
import { spawn } from 'node:child_process';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
test('disabled source configuration refuses to start a listener',async()=>{await assert.rejects(startHost({enabled:false}),/disabled/);});

test('occupied MCP port exits with an actionable error', async t => {
    const directory = await mkdtemp(join(tmpdir(), 'nano-port-'));
    t.after(() => rm(directory, { recursive: true, force: true }));
    const occupied = http.createServer();
    occupied.listen(0, '127.0.0.1');
    await once(occupied, 'listening');
    t.after(() => occupied.close());
    const config = join(directory, 'host.json');
    const credentialsFile = join(directory, 'credentials.json');
    await writeFile(credentialsFile, JSON.stringify({ principals: [] }));
    await writeFile(config, JSON.stringify({ enabled: true, port: occupied.address().port,
        controllerPort: 41231, controllerId: 'local-controller', deviceId: 'wall',
        transport: 'windows-http', credentialsFile }));
    const child = spawn(process.execPath, [fileURLToPath(new URL('../dist/main.js', import.meta.url)), '--config', config],
        { stdio: ['ignore', 'pipe', 'pipe'] });
    t.after(() => child.kill());
    let error = '';
    child.stderr.on('data', data => { error += data; });
    const [code] = await once(child, 'close');
    assert.equal(code, 1);
    assert.match(error, /port is already in use/);
    assert.match(error, /private configuration/);
});
