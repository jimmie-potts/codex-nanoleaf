// #193: the wall verification plug-in against real served runs, without the core's systemd supervisor.
//
// Each run is seeded and launched here the way the core's `start` does it, with the demo as a plain
// child process. Capture steps run through the core's own `runCaptureStep`, the same driver and pass
// rule as `npm run verify -- capture`. Reference steps must pass with a screenshot and a finalized
// video; each negative control must fail at its named assertion rather than crash. The supervised
// lifecycle (units, lease, receipt, handoff) needs a systemd user manager and is exercised locally.
//
// #194: hub-paired runs pair with a stand-in Hub feed served here from
// tests/fixtures/paired-hub-feed.json, and a stand-in controller caller presents the Hub's token to
// the wall's real controller API. They run under tests/fixtures/backstop_demo.py, so a boundary
// regression cannot reach an installed service, and each asserts that the backstop saw nothing.
import assert from 'node:assert/strict';
import {execFile, spawn} from 'node:child_process';
import {createHash, randomBytes} from 'node:crypto';
import {existsSync} from 'node:fs';
import {chmod, mkdir, mkdtemp, readdir, readFile, rm, symlink, utimes, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import readline from 'node:readline';
import {describe, test} from 'node:test';
import {promisify} from 'node:util';
import {runCaptureStep} from '@jimmie-potts/app-verify';
import plugin, {createPlugin, deviceBoundary, failureCause, pairedFeed, readyLine} from '../scripts/verify/plugin.mjs';
import {NEGATIVE_CONTROLS, pairedExpectations, readHubFeed, sessionKey, strict, strictSteps} from '../scripts/verify/steps.mjs';
import {callController} from './fixtures/controller-caller.mjs';
import {FEED, standInHub} from './fixtures/stand-in-hub.mjs';

const results = join(plugin.root, 'test-results/verify');
const BACKSTOP = join(plugin.root, 'tests/fixtures/backstop_demo.py');
/** The plug-in hub-paired tests use: every seed, serve and drive runs beneath the test backstop. */
const paired = createPlugin({demo: BACKSTOP});
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const token = () => randomBytes(32).toString('base64url');

/** Write the orchestrator's two credential files: one token each, mode 0600, no trailing newline. */
async function writeCredentials(runtimeDir, tokens = {feed: token(), controller: token()}) {
  await writeFile(join(runtimeDir, 'hub-feed-token'), tokens.feed, {mode: 0o600});
  await writeFile(join(runtimeDir, 'hub-controller-token'), tokens.controller, {mode: 0o600});
  return tokens;
}

const wallState = async url => (await fetch(new URL('verify/state', url))).json();

/** Poll until `condition(value)` holds for `read()`'s value, or fail after `ms`. */
async function until(read, condition, ms = 15000) {
  let value;
  for (let waited = 0; waited <= ms; waited += 200) {
    value = await read();
    if (condition(value)) return value;
    await sleep(200);
  }
  assert.fail(`the condition did not hold within ${ms} ms: ${JSON.stringify(value)}`);
}

/**
 * Seed, launch and wait for readiness the way the core's `start` does, with the process as a plain
 * child. hub-paired writes the credential files and starts a stand-in Hub unless one is given.
 * `runtimeDir` and `endpointPorts` relaunch an existing run after a reseed, as the core does.
 */
async function startRun(scenario, {serve, hub, runtimeDir, port = 0, endpointPorts = {}, tokens} = {}) {
  const pairing = scenario === 'hub-paired';
  const used = pairing || endpointPorts.controller !== undefined ? paired : plugin;
  const reused = runtimeDir !== undefined;
  runtimeDir ??= await mkdtemp(join(tmpdir(), 'wall-verify-'));
  const dataDir = join(runtimeDir, 'data');
  await rm(dataDir, {recursive: true, force: true});
  await mkdir(dataDir);
  await mkdir(join(runtimeDir, 'tmp'), {recursive: true});
  let owned;
  if (pairing) {
    tokens ??= reused ? undefined : await writeCredentials(runtimeDir);
    hub ??= owned = await standInHub(tokens.feed);
  }
  const inputs = pairing ? {'hub-feed': hub.origin} : {};
  const paths = {runId: runtimeDir.split('/').at(-1), root: used.root, runtimeDir, dataDir, scenario, inputs};
  await used.scenarios[scenario].seed(paths);
  const spec = await used.launch({...paths, port, node: process.execPath, endpointPorts});
  // A test can serve through another entry point that takes demo.py's arguments.
  if (serve) spec.argv = spec.argv.map(argument => argument.endsWith('scripts/demo.py') ? serve : argument);
  const child = spawn(spec.argv[0], spec.argv.slice(1), {cwd: spec.cwd ?? used.root, stdio: ['ignore', 'pipe', 'pipe'],
    env: {...process.env, ...spec.env, TMPDIR: join(runtimeDir, 'tmp')}});
  let errors = '';
  child.stderr.on('data', data => {errors += data});
  const ready = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`No ready line: ${errors}`)), used.readiness.timeoutMs);
    child.once('exit', code => {clearTimeout(timer); reject(new Error(`Exited ${code}: ${errors}`))});
    readline.createInterface({input: child.stdout}).on('line', line => {
      const announced = used.readiness.line(line);
      if (announced) {clearTimeout(timer); resolve(announced)}
    });
  });
  const context = {...paths, url: ready.url, port: Number(new URL(ready.url).port), endpoints: ready.endpoints ?? {}, signal: AbortSignal.timeout(60000)};
  const halt = async () => {
    if (child.exitCode === null && child.signalCode === null) {
      const exited = new Promise(resolve => child.once('exit', resolve));
      child.kill('SIGTERM');
      await exited;
    }
  };
  return {
    context, hub, tokens, plugin: used, errors: () => errors,
    probe: () => used.readiness.probe(context),
    checks: () => Promise.all(used.checks.map(async check => ({id: check.id, ...await check.run(context)}))),
    /** Nothing reached the test backstop: the boundary refused everything it had to. */
    backstop: async () => readFile(join(runtimeDir, 'backstop.jsonl'), 'utf8').catch(error => error.code === 'ENOENT' ? '' : Promise.reject(error)),
    /** Stop the process but keep the runtime directory, for a relaunch. */
    halt,
    async stop() {
      await halt();
      await owned?.close();
      await rm(runtimeDir, {recursive: true, force: true});
    },
  };
}

describe('plug-in surface', () => {
  test('the ready line must name a loopback origin', () => {
    assert.deepEqual(readyLine('{"url": "http://127.0.0.1:41705", "instance": "ab12"}'), {url: 'http://127.0.0.1:41705/'});
    for (const line of ['', 'Serving', '{}', '{"url": "http://localhost:41705"}', '{"url": "http://0.0.0.0:41705"}',
      '{"url": "https://127.0.0.1:41705"}', '{"url": "http://127.0.0.1"}', '{"url": "http://127.0.0.1:41705/x"}',
      '{"url": "http://u:p@127.0.0.1:41705"}', '{"url": "http://127.0.0.1:41705/?q=1"}']) {
      assert.equal(readyLine(line), undefined, line);
    }
  });

  test('the ready line may announce only the controller endpoint, exactly as a loopback origin', () => {
    assert.deepEqual(readyLine('{"url": "http://127.0.0.1:41705", "endpoints": {"controller": "http://127.0.0.1:41706/"}}'),
      {url: 'http://127.0.0.1:41705/', endpoints: {controller: 'http://127.0.0.1:41706/'}});
    for (const endpoints of ['[]', 'null', '"x"', '{"hub": "http://127.0.0.1:41706/"}', '{"controller": "http://127.0.0.1:41706"}',
      '{"controller": "http://127.0.0.1:41706/controller/v1"}', '{"controller": "http://localhost:41706/"}', '{"controller": 41706}']) {
      assert.equal(readyLine(`{"url": "http://127.0.0.1:41705", "endpoints": ${endpoints}}`), undefined, endpoints);
    }
  });

  test('hub-paired needs the hub-feed input, and no input is secret-like', () => {
    assert.deepEqual(Object.keys(plugin.inputs), ['hub-feed']);
    assert.equal(plugin.inputs['hub-feed'].required, undefined, 'the standalone scenarios run without it');
    assert.deepEqual(plugin.scenarios['hub-paired'].requiredInputs, ['hub-feed']);
    for (const name of ['reference', 'empty', 'layout-unavailable']) assert.equal(plugin.scenarios[name].requiredInputs, undefined, name);
    for (const name of Object.keys(plugin.inputs)) assert.doesNotMatch(name, /token|secret|password|credential|key/i);
  });

  test('the scenarios are the ones demo.py seeds', async () => {
    const {stdout} = await promisify(execFile)(process.env.PYTHON || 'python3', [join(plugin.root, 'scripts/demo.py'), 'scenarios']);
    assert.deepEqual(Object.fromEntries(Object.entries(plugin.scenarios).map(([name, scenario]) => [name, scenario.description])), JSON.parse(stdout));
    assert.ok(plugin.scenarios[plugin.defaultScenario]);
  });

  test('every capture step is fresh and names a seeded scenario, and every control names a step', () => {
    for (const [name, step] of Object.entries(plugin.captureSteps)) {
      assert.ok(plugin.scenarios[step.scenario], name);
      assert.equal(step.fresh, true, `${name} asserts absolute observations, so it must start from a fresh seed`);
    }
    for (const name of Object.keys(NEGATIVE_CONTROLS)) assert.ok(plugin.captureSteps[name], name);
  });

  test('the artifact names the served page and its assets', () => {
    assert.deepEqual(plugin.build.artifact, {files: ['bridge/wall.html', 'bridge/prism.js', 'bridge/prism-adapters.js', 'bridge/prism-labels.js']});
    for (const file of plugin.build.artifact.files) assert.ok(existsSync(join(plugin.root, file)), file);
  });

  test('a failed start is named by a fixed line or the exception type, never its message', () => {
    const traceback = last => `Traceback (most recent call last):\n  File "/x/scripts/demo.py", line 1, in <module>\n${last}\n`;
    const cases = [
      [traceback('OSError: [Errno 98] Address already in use'), 'wall-start-failed: port already in use'],
      [traceback("FileNotFoundError: [Errno 2] No such file or directory: '/home/u/.local/state/app-verify/wall-x/data/config.json'"),
        'wall-start-failed: the state directory is not seeded (config.json missing)'],
      [traceback("ModuleNotFoundError: No module named 'wall_server'"), 'wall-start-failed: Python module wall_server is missing'],
      ['usage: demo.py [-h] [--port PORT]\ndemo.py: error: unrecognized arguments: --bogus\n', 'wall-start-failed: demo.py rejected its arguments'],
      ["usage: demo.py [-h]\ndemo.py: error: Refusing the state directory: it is the installation's own state.\n", 'wall-start-failed: refused the installation state directory'],
      ['usage: demo.py [-h]\ndemo.py: error: Refusing the state directory: it has no demo-run.json from demo.py seed.\n', 'wall-start-failed: the state directory was not seeded by demo.py'],
      [traceback("ValueError: The token must contain only letters and numbers: FakeDemoToken"), 'wall-start-failed: ValueError'],
      [traceback("FileNotFoundError: [Errno 2] No such file or directory: '/home/u/secret-name.json'"), 'wall-start-failed: FileNotFoundError'],
      [traceback('KeyboardInterrupt'), 'wall-start-failed: KeyboardInterrupt'],
      [traceback('controller_server.ListenerUnavailable: Port 41706 is already in use. Stop its owner or choose another controller port.'),
        'wall-start-failed: controller port already in use'],
      [traceback('controller_server.ListenerUnavailable: Cannot bind the controller to 127.0.0.1:41706.'), 'wall-start-failed: controller listener unavailable'],
      ['usage: demo.py [-h]\ndemo.py: error: hub-paired needs a private hub-feed-token file in the run directory.\n',
        'wall-start-failed: hub-paired needs a private hub-feed-token file in the run directory'],
      ['usage: demo.py [-h]\ndemo.py: error: hub-paired needs a private hub-controller-token file in the run directory.\n',
        'wall-start-failed: hub-paired needs a private hub-controller-token file in the run directory'],
      ["usage: demo.py [-h]\ndemo.py: error: hub-feed must be the paired Hub run's origin, http://127.0.0.1:<port>/.\n",
        "wall-start-failed: hub-feed is not the paired Hub run's origin"],
      ["usage: demo.py [-h]\ndemo.py: error: hub-feed names an installed service's port.\n", "wall-start-failed: hub-feed names an installed service's port"],
      ['controller listener stopped\n', 'wall-start-failed: controller listener stopped'],
      ['controller listener stopped (OperationalError)\n', 'wall-start-failed: controller listener stopped'],
      ['listening\n', undefined],
      ['', undefined],
    ];
    for (const [tail, expected] of cases) {
      const cause = failureCause(tail);
      assert.equal(cause, expected, tail);
      if (cause) assert.ok(cause.length <= 200 && /^[\x20-\x7e]+$/.test(cause), cause);
    }
  });

  test("the boundary check allows only the map's layout read, and only in layout-unavailable", async () => {
    const read = seconds => ({at: new Date(Date.UTC(2026, 8, 27, 12, 0, 0) + seconds * 1000).toISOString(),
      kind: 'light-request', target: '192.0.2.1', method: 'GET', endpoint: '', outcome: 'refused'});
    const layoutRead = read(0);
    const cases = [
      ['reference', [], {outcome: 'passed'}],
      ['reference', [layoutRead], {outcome: 'failed', reason: '1 device attempt(s) recorded since the last seed'}],
      ['layout-unavailable', [read(0), read(10.1), read(20.2)], {outcome: 'passed'}],
      ['layout-unavailable', [read(0), read(10.1), read(20.2), read(30.3)], {outcome: 'failed', reason: "4 layout reads, more than the map's 3"}],
      ['layout-unavailable', [read(0), read(3)], {outcome: 'failed', reason: 'layout read 2 came 3000 ms after the previous one'}],
      // The map decides its reads 10 s apart; a read recorded 500 ms late still passes (#196).
      ['layout-unavailable', [read(0.5), read(10), read(20)], {outcome: 'passed'}],
      // A map that reads on every 1 s poll, and one that keeps the 10 s spacing without the three-read limit.
      ['layout-unavailable', [read(0), read(1)], {outcome: 'failed', reason: 'layout read 2 came 1000 ms after the previous one'}],
      ['layout-unavailable', [read(0), read(10), read(20), read(30)], {outcome: 'failed', reason: "4 layout reads, more than the map's 3"}],
      ['layout-unavailable', [layoutRead, {...layoutRead, endpoint: '/state'}],
        {outcome: 'failed', reason: "1 device attempt(s) other than the map's layout read recorded since the last seed"}],
      ['layout-unavailable', [], {outcome: 'failed', reason: 'the startup layout read was not attempted and refused'}],
      ['layout-unavailable', [layoutRead, {kind: 'process', target: 'python3', outcome: 'refused'}],
        {outcome: 'failed', reason: "1 device attempt(s) other than the map's layout read recorded since the last seed"}],
      ['layout-unavailable', [{...layoutRead, method: 'PUT', endpoint: '/effects'}],
        {outcome: 'failed', reason: "1 device attempt(s) other than the map's layout read recorded since the last seed"}],
      ['layout-unavailable', [{...layoutRead, target: '192.0.2.2'}],
        {outcome: 'failed', reason: "1 device attempt(s) other than the map's layout read recorded since the last seed"}],
    ];
    for (const [scenario, entries, expected] of cases) {
      const dataDir = await mkdtemp(join(tmpdir(), 'wall-boundary-'));
      try {
        if (entries.length) await writeFile(join(dataDir, 'device-boundary.jsonl'), entries.map(entry => JSON.stringify(entry)).join('\n') + '\n');
        assert.deepEqual(await deviceBoundary({dataDir, scenario}), expected, JSON.stringify([scenario, entries]));
      } finally {
        await rm(dataDir, {recursive: true, force: true});
      }
    }
  });

  test('in hub-paired the boundary check allows only connections to the paired Hub port', async () => {
    const at = '2026-09-27T12:00:00.000Z';
    const allowed = port => ({at, kind: 'socket.connect', target: `127.0.0.1:${port}`, outcome: 'allowed'});
    const other = "device attempt(s) or connection(s) other than the paired Hub feed recorded since the last seed";
    const inputs = {'hub-feed': 'http://127.0.0.1:45001/'};
    const cases = [
      [inputs, [], {outcome: 'passed'}],
      [inputs, [allowed(45001), allowed(45001)], {outcome: 'passed'}],
      [inputs, [allowed(45001), allowed(45002)], {outcome: 'failed', reason: `1 ${other}`}],
      [inputs, [allowed(45001), {...allowed(45001), outcome: 'refused'}], {outcome: 'failed', reason: `1 ${other}`}],
      [inputs, [{at, kind: 'socket.connect', target: '127.0.0.1:8788', outcome: 'refused'}], {outcome: 'failed', reason: `1 ${other}`}],
      [inputs, [{at, kind: 'light-request', target: '192.0.2.1', method: 'PUT', endpoint: '/effects', outcome: 'refused'}], {outcome: 'failed', reason: `1 ${other}`}],
      [inputs, [{at, kind: 'socket.sendto', target: '127.0.0.1:45001', outcome: 'refused'}], {outcome: 'failed', reason: `1 ${other}`}],
      [{'hub-feed': 'http://127.0.0.1:8788/'}, [allowed(8788)], {outcome: 'failed', reason: 'hub-paired has no paired Hub port'}],
      [{}, [], {outcome: 'failed', reason: 'hub-paired has no paired Hub port'}],
    ];
    for (const [given, entries, expected] of cases) {
      const dataDir = await mkdtemp(join(tmpdir(), 'wall-boundary-'));
      try {
        if (entries.length) await writeFile(join(dataDir, 'device-boundary.jsonl'), entries.map(entry => JSON.stringify(entry)).join('\n') + '\n');
        assert.deepEqual(await deviceBoundary({dataDir, scenario: 'hub-paired', inputs: given}), expected, JSON.stringify([given, entries]));
      } finally {
        await rm(dataDir, {recursive: true, force: true});
      }
    }
    // A connection allowed in hub-paired is still an attempt in every standalone scenario.
    const dataDir = await mkdtemp(join(tmpdir(), 'wall-boundary-'));
    try {
      await writeFile(join(dataDir, 'device-boundary.jsonl'), JSON.stringify(allowed(45001)) + '\n');
      assert.equal((await deviceBoundary({dataDir, scenario: 'reference', inputs})).outcome, 'failed');
    } finally {
      await rm(dataDir, {recursive: true, force: true});
    }
  });

  test('a hub-paired seed without its credential files or a usable Hub origin fails with a fixed line and no path', async () => {
    const runtimeDir = await mkdtemp(join(tmpdir(), 'wall-seed-'));
    try {
      const dataDir = join(runtimeDir, 'data');
      await mkdir(dataDir);
      const seed = hubFeed => plugin.scenarios['hub-paired'].seed({runtimeDir, dataDir, scenario: 'hub-paired', inputs: {'hub-feed': hubFeed}});
      const refused = async (hubFeed, message) => {
        await assert.rejects(seed(hubFeed), error => error.message === `demo.py seed failed: ${message}` && !error.message.includes(runtimeDir));
        assert.deepEqual(await readdir(dataDir), [], 'a refused seed writes nothing');
      };
      await refused('http://127.0.0.1:45001/', 'hub-paired needs a private hub-feed-token file in the run directory');
      await writeFile(join(runtimeDir, 'hub-feed-token'), token(), {mode: 0o600});
      await refused('http://127.0.0.1:45001/', 'hub-paired needs a private hub-controller-token file in the run directory');
      await writeFile(join(runtimeDir, 'hub-controller-token'), token(), {mode: 0o644});
      await refused('http://127.0.0.1:45001/', 'hub-paired needs a private hub-controller-token file in the run directory');
      await chmod(join(runtimeDir, 'hub-controller-token'), 0o600);
      await writeFile(join(runtimeDir, 'hub-feed-token'), 'short', {mode: 0o600});
      await refused('http://127.0.0.1:45001/', 'hub-paired needs a private hub-feed-token file in the run directory');
      await rm(join(runtimeDir, 'hub-feed-token'));
      await writeFile(join(runtimeDir, 'elsewhere'), token(), {mode: 0o600});
      await symlink(join(runtimeDir, 'elsewhere'), join(runtimeDir, 'hub-feed-token'));
      await refused('http://127.0.0.1:45001/', 'hub-paired needs a private hub-feed-token file in the run directory');
      await rm(join(runtimeDir, 'hub-feed-token'));
      await writeFile(join(runtimeDir, 'hub-feed-token'), token(), {mode: 0o600});
      for (const origin of ['http://127.0.0.1:45001', 'http://localhost:45001/', 'http://127.0.0.1:45001/api/monitor/v1', 'https://127.0.0.1:45001/']) {
        await refused(origin, "hub-feed is not the paired Hub run's origin");
      }
      await refused('http://127.0.0.1:8788/', "hub-feed names an installed service's port");
    } finally {
      await rm(runtimeDir, {recursive: true, force: true});
    }
  });

  test('a failed seed is named by a fixed line, without the command or any path', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'wall-seed-'));
    try {
      const fake = join(directory, 'python3');
      await writeFile(fake, `#!/bin/sh\nprintf 'Traceback (most recent call last):\\n  File "%s", line 1\\n' "$0" >&2\nprintf "ModuleNotFoundError: No module named 'wall_server'\\n" >&2\nexit 1\n`, {mode: 0o755});
      const context = {dataDir: join(directory, 'data'), scenario: 'reference'};
      await assert.rejects(createPlugin({python: fake}).scenarios.reference.seed(context),
        error => error.message === 'demo.py seed failed: Python module wall_server is missing');
      await assert.rejects(createPlugin({python: join(directory, 'missing', 'python3')}).scenarios.reference.seed(context),
        error => error.message === 'demo.py seed failed: the Python interpreter was not found');
    } finally {
      await rm(directory, {recursive: true, force: true});
    }
  });

  test('the launch binds the requested port and carries no credential', async () => {
    const spec = await plugin.launch({dataDir: '/run/data', port: 41705, scenario: 'reference', endpointPorts: {}});
    assert.deepEqual(spec.argv.slice(-4), ['--state-dir', '/run/data', '--port', '41705']);
    assert.ok(Object.keys(spec.env).every(key => key.startsWith('PYTHON')), JSON.stringify(spec.env));
  });

  test('hub-paired launches the controller listener, and every later scenario keeps it on its recorded port', async () => {
    const launch = (scenario, endpointPorts) => plugin.launch({dataDir: '/run/data', runtimeDir: '/run', runId: 'run', port: 41705, scenario, endpointPorts, inputs: {'hub-feed': 'http://127.0.0.1:45001/'}});
    assert.deepEqual((await launch('hub-paired', {})).argv.slice(-6), ['--feed-pause-runtime', '/run', '--feed-pause-run', 'run', '--controller-port', '0']);
    assert.deepEqual((await launch('hub-paired', {controller: 41706})).argv.slice(-2), ['--controller-port', '41706']);
    assert.deepEqual((await launch('reference', {controller: 41706})).argv.slice(-2), ['--controller-port', '41706']);
    const spec = await launch('hub-paired', {});
    assert.equal(spec.argv.some(argument => argument.includes('hub-feed') || argument.includes('token')), false, 'no Hub origin or credential in the unit');
  });

  test('the installed core is the vendored app-verify 1.1.0, file for file', async () => {
    const installed = join(plugin.root, 'node_modules/@jimmie-potts/app-verify');
    const manifest = JSON.parse(await readFile(join(installed, 'manifest.json'), 'utf8'));
    assert.equal(manifest.version, '1.1.0');
    assert.equal(JSON.parse(await readFile(join(installed, 'package.json'), 'utf8')).version, '1.1.0');
    assert.ok(Object.keys(manifest.files).length > 0);
    for (const [name, digest] of Object.entries(manifest.files)) {
      assert.equal(createHash('sha256').update(await readFile(join(installed, name))).digest('hex'), digest, name);
    }
  });

  test('the step reads the paired credential only from a private regular file, and never sends another', async () => {
    const runtimeDir = await mkdtemp(join(tmpdir(), 'wall-token-'));
    const value = token();
    const hub = await standInHub(value);
    try {
      const read = () => readHubFeed({inputs: {'hub-feed': hub.origin}, runtimeDir, signal: AbortSignal.timeout(5000)});
      const refused = async () => {
        await assert.rejects(read(), error => error.message === 'hub-paired needs a private hub-feed-token file in the run directory' && !error.message.includes(runtimeDir));
      };
      const file = join(runtimeDir, 'hub-feed-token');
      await refused();
      await writeFile(file, value, {mode: 0o640});
      await refused();
      await chmod(file, 0o600);
      assert.equal((await read()).ownerId, 'verify-owner');
      await rm(file);
      await writeFile(join(runtimeDir, 'elsewhere'), value, {mode: 0o600});
      await symlink(join(runtimeDir, 'elsewhere'), file);
      await refused();
      await rm(file);
      await mkdir(file);
      await refused();
      await rm(file, {recursive: true});
      await writeFile(file, 'x'.repeat(200), {mode: 0o600});
      await refused();
      assert.equal(hub.requests, 1, "only the private file's token reached the Hub");
    } finally {
      await hub.close();
      await rm(runtimeDir, {recursive: true, force: true});
    }
  });

  test('the Hub expectations come from the snapshot: statuses, titles, keys and the undeclared source left out', () => {
    const expected = pairedExpectations(FEED.envelope.snapshot);
    const bySession = Object.fromEntries(FEED.envelope.snapshot.sessions.map(session => [sessionKey(session.identity), session.identity.sessionId]));
    assert.deepEqual(Object.fromEntries(Object.entries(expected).map(([key, task]) => [bySession[key], [task.status, task.title]])), FEED.expected);
    assert.ok(Object.values(expected).every(task => task.evidence === 'current'));
    // bridge/shared_input.py keys the same identity the same way.
    assert.equal(sessionKey({provider: 'codex', client: 'cli', hostId: 'verify-host', sourceId: 'verify-source', sessionId: 'hub-working'}),
      Object.keys(expected)[0]);
  });
});

describe('check rule', () => {
  test('a check passes only by returning nothing or true', async () => {
    await strict(() => undefined)();
    await strict(async () => true)();
    await assert.rejects(strict(async () => false)(), /the observation did not match/);
    await assert.rejects(strict(() => 0)(), /returned 0 instead of throwing/);
    await assert.rejects(strict(async () => 'Line 1')(), /returned "Line 1" instead of throwing/);
    await assert.rejects(strict(() => {throw new Error('mismatch')})(), /mismatch/);
  });

  test('predicate-style checks fail the capture when the observation is wrong', async () => {
    // Probe steps wrapped exactly as the plug-in wraps its own, driven by the core's capture driver.
    const probes = strictSteps({
      'predicate-wrong': {description: 'A predicate on an absent Line', scenario: 'reference', run: async t => {
        await t.page.goto(t.url);
        await t.page.locator('#taskList .task').first().waitFor();
        await t.expect('the task list names a Line 99', () => t.page.locator('#taskList').getByText('Line 99', {exact: true}).isVisible());
      }},
      'predicate-right': {description: 'A predicate on a present Line', scenario: 'reference', run: async t => {
        await t.page.goto(t.url);
        await t.page.locator('#taskList .task').first().waitFor();
        await t.expect('the task list names Line 1', () => t.page.locator('#taskList').getByText('Line 1', {exact: true}).first().isVisible());
      }},
      'count-of-zero': {description: 'A check that returns a count', scenario: 'reference', run: async t => {
        await t.page.goto(t.url);
        await t.page.locator('#taskList .task').first().waitFor();
        await t.expect('no task waits for a Line', () => t.page.evaluate(() => state.tasks.filter(task => !task.line).length));
      }},
    });
    const probe = {...plugin, captureSteps: probes};
    const run = await startRun('reference');
    try {
      const capture = async name => {
        const outputDir = join(results, `check-rule-${name}`);
        await rm(outputDir, {recursive: true, force: true});
        return runCaptureStep(probe, name, {url: run.context.url, outputDir, scenario: 'reference', dataDir: run.context.dataDir});
      };
      const wrong = await capture('predicate-wrong');
      assert.equal(wrong.outcome, 'failed');
      assert.equal(wrong.reason, 'assertion failed: the task list names a Line 99: the observation did not match');
      assert.equal((await capture('predicate-right')).outcome, 'passed');
      const count = await capture('count-of-zero');
      assert.equal(count.outcome, 'failed');
      assert.match(count.reason, /^assertion failed: no task waits for a Line: the check returned 0 instead of throwing/);
    } finally {
      await run.stop();
    }
  });
});

describe('served runs', () => {
  for (const scenario of Object.keys(plugin.scenarios).filter(name => name !== 'hub-paired')) {
    test(`${scenario}: the map is ready, the device-boundary check passes and the paired-feed check is skipped`, async () => {
      const run = await startRun(scenario);
      try {
        assert.deepEqual(await run.probe(), {ok: true});
        assert.deepEqual(await run.checks(), [{id: 'device-boundary', outcome: 'passed'},
          {id: 'paired-feed', outcome: 'skipped', reason: `${scenario} is not paired with a Hub`}]);
        assert.deepEqual((await wallState(run.context.url)).feed.source, 'legacy');
      } finally {
        await run.stop();
      }
    });
  }

  test('the probe rejects a map that is not this run\'s process', async () => {
    const run = await startRun('reference');
    try {
      const receipt = join(run.context.dataDir, 'map-server.json');
      const saved = JSON.parse(await readFile(receipt, 'utf8'));
      await writeFile(receipt, JSON.stringify({...saved, instance: 'another'}));
      assert.deepEqual(await run.probe(), {ok: false, reason: 'health names another map instance'});
    } finally {
      await run.stop();
    }
  });
});

describe('hub-paired runs', () => {
  test('paired diagnostics skip a pause and reject malformed controls without probing the Hub', async () => {
    const run = await startRun('hub-paired');
    try {
      await until(() => wallState(run.context.url), value => value.feed.connection === 'current');
      const request = {version: 1, runId: run.context.runId, nonce: 'a'.repeat(32)};
      const path = join(run.context.runtimeDir, 'feed-pause.request');
      await writeFile(path, JSON.stringify(request), {mode: 0o600});
      await until(async () => JSON.parse(await readFile(join(run.context.runtimeDir, 'feed-pause.ack'), 'utf8').catch(() => '{}')),
        ack => ack.nonce === request.nonce);
      const calls = run.hub.requests;
      assert.equal(typeof calls, 'number');
      assert.deepEqual(await pairedFeed(run.context), {outcome: 'skipped', reason: 'the Hub feed is paused for aggregate reset'});
      const release = join(run.context.runtimeDir, 'feed-pause.release');
      await writeFile(release, '{', {mode: 0o600});
      assert.deepEqual(await pairedFeed(run.context), {outcome: 'failed', reason: 'feed-pause.release is invalid for this run'});
      await rm(release);
      await writeFile(path, '{', {mode: 0o600});
      assert.deepEqual(await pairedFeed(run.context), {outcome: 'failed', reason: 'feed-pause.request is invalid for this run'});
      assert.equal(run.hub.requests, calls);
      // A deliberate direct probe demonstrates that the counter detects the forbidden effect.
      await fetch(new URL('api/monitor/v1/sessions?snapshotVersion=1.2', run.hub.origin));
      assert.equal(run.hub.requests, calls + 1);
    } finally { await run.stop(); }
  });

  test('the wall follows the stand-in Hub feed and both checks pass, with only the paired port contacted', async () => {
    const run = await startRun('hub-paired');
    try {
      assert.deepEqual(await run.probe(), {ok: true});
      const state = await until(() => wallState(run.context.url), value => value.feed.connection === 'current');
      assert.deepEqual(state, {apiVersion: 'wall-verify/1', scenario: 'hub-paired',
        feed: {source: 'shared', connection: 'current', revision: 7, receivedAt: state.feed.receivedAt, ownerId: 'verify-owner', error: null},
        integration: {applied: 0, queued: 0, failed: 0}});
      assert.deepEqual(await run.checks(), [{id: 'device-boundary', outcome: 'passed'}, {id: 'paired-feed', outcome: 'passed'}]);
      const entries = (await readFile(join(run.context.dataDir, 'device-boundary.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
      assert.ok(entries.length >= 1);
      assert.deepEqual([...new Set(entries.map(entry => `${entry.kind} ${entry.target} ${entry.outcome}`))], [`socket.connect ${new URL(run.hub.origin).host} allowed`]);
      assert.equal(await run.backstop(), '');
      for (const secret of Object.values(run.tokens)) {
        assert.equal(JSON.stringify(state).includes(secret), false);
        assert.equal(run.errors().includes(secret), false, 'no credential on stderr');
      }
    } finally {
      await run.stop();
    }
  });

  test("the Hub's controller calls reach the wall's real controller API, and the writer applies its settings", async () => {
    const run = await startRun('hub-paired');
    try {
      const endpoint = run.context.endpoints.controller;
      const credential = run.tokens.controller;
      assert.match(endpoint, /^http:\/\/127\.0\.0\.1:\d+\/$/);
      assert.deepEqual((await callController(endpoint, 'controller/v1/devices')).status, 401);
      assert.deepEqual((await callController(endpoint, 'controller/v1/devices', {credential: run.tokens.feed})).status, 401, 'the feed token is not a controller credential');
      const devices = await callController(endpoint, 'controller/v1/devices', {credential});
      assert.equal(devices.status, 200);
      assert.deepEqual(devices.body.devices.map(({identity}) => [identity.controllerId, identity.deviceId, identity.sourceId]), [['wall-controller', 'wall', 'wall']]);
      assert.equal((await callController(endpoint, 'controller/v1/snapshot?deviceId=wall', {credential})).status, 200);
      const snapshot = await callController(endpoint, 'controller/integration/v1/snapshot?deviceId=wall', {credential});
      assert.equal(snapshot.status, 200);
      assert.equal(snapshot.body.settings.style, 'classic');
      const command = {apiVersion: snapshot.body.apiVersion, controllerId: 'wall-controller', deviceId: 'wall', requestId: snapshot.body.nextRequestId,
        expectedRevision: snapshot.body.revision, command: {kind: 'settings.set', style: 'project'}};
      const admitted = await callController(endpoint, 'controller/integration/v1/commands', {credential, body: command});
      assert.deepEqual([admitted.status, admitted.body.outcome], [202, 'queued']);
      const state = await until(() => wallState(run.context.url), value => value.integration.applied === 1);
      assert.deepEqual(state.integration, {applied: 1, queued: 0, failed: 0});
      assert.equal((await (await fetch(new URL('api/state', run.context.url))).json()).settings.style, 'project', 'the wall shows the applied setting');
      const receipt = await callController(endpoint, `controller/integration/v1/receipt?deviceId=wall&epoch=${command.requestId.epoch}&sequence=${command.requestId.sequence}`, {credential});
      assert.deepEqual([receipt.status, receipt.body.outcome], [200, 'applied']);
      assert.equal(await run.backstop(), '');
    } finally {
      await run.stop();
    }
  });

  test('a Hub that refuses the feed credential at first leaves the wall serving and the check skipped until it accepts', async () => {
    const tokens = {feed: token(), controller: token()};
    const hub = await standInHub(tokens.feed);
    hub.status = 401;
    const runtimeDir = await mkdtemp(join(tmpdir(), 'wall-verify-'));
    await writeCredentials(runtimeDir, tokens);
    const run = await startRun('hub-paired', {hub, runtimeDir, tokens});
    try {
      assert.deepEqual(await run.probe(), {ok: true});
      const refused = await until(() => wallState(run.context.url), value => value.feed.error === 'feed-rejected');
      assert.deepEqual([refused.feed.connection, refused.feed.revision, refused.feed.ownerId], ['unavailable', null, null],
        'no owner is reported before an envelope is accepted');
      assert.deepEqual(await run.checks(), [{id: 'device-boundary', outcome: 'passed'},
        {id: 'paired-feed', outcome: 'skipped', reason: 'no snapshot from the paired Hub yet (feed-rejected)'}]);
      // 30 s after the seed, a pairing that never came up fails instead of staying skipped.
      const marker = join(run.context.dataDir, 'demo-run.json'), past = new Date(Date.now() - 31000);
      await utimes(marker, past, past);
      assert.deepEqual((await run.checks())[1], {id: 'paired-feed', outcome: 'failed', reason: 'no snapshot from the paired Hub within 30 s of the seed (feed-rejected)'});
      hub.status = 200;
      await until(() => wallState(run.context.url), value => value.feed.connection === 'current' && value.feed.revision === 7);
      assert.deepEqual((await run.checks())[1], {id: 'paired-feed', outcome: 'passed'});
    } finally {
      await run.stop();
      await hub.close();
    }
  });

  test('a paired feed that goes stale or falls behind the Hub fails the paired-feed check', async () => {
    const run = await startRun('hub-paired');
    try {
      await until(() => wallState(run.context.url), value => value.feed.connection === 'current');
      // The Hub moves on with a snapshot the wall must reject: another owner.
      run.hub.envelope = {...structuredClone(FEED.envelope), ownerId: 'another-owner'};
      const check = await pairedFeed({...run.context, signal: AbortSignal.timeout(20000)});
      assert.equal(check.outcome, 'failed');
      assert.match(check.reason, /^(the wall's paired feed is (stale|unavailable) \(invalid-feed\)|the paired Hub names owner "another-owner", not verify-owner)$/);
      run.hub.envelope = structuredClone(FEED.envelope);
      run.hub.envelope.snapshot.revision = 8;
      await until(() => wallState(run.context.url), value => value.feed.connection === 'current' && value.feed.revision === 8);
      await run.hub.close();
      const stale = await until(() => wallState(run.context.url), value => value.feed.connection === 'stale', 10000);
      assert.equal(stale.feed.error, 'feed-unavailable');
      assert.deepEqual(await pairedFeed({...run.context, signal: AbortSignal.timeout(20000)}),
        {outcome: 'failed', reason: "the wall's paired feed is stale (feed-unavailable)"});
      const tasks = (await (await fetch(new URL('api/state', run.context.url))).json()).tasks;
      assert.ok(tasks.length > 0 && tasks.every(task => task.statusEvidence === 'uncertain'), 'the wall keeps its tasks steady as uncertain');
    } finally {
      await run.stop();
    }
  });

  test('a relaunch keeps the controller on its recorded port, and a standalone scenario then accepts no Hub credential', async () => {
    const run = await startRun('hub-paired');
    const {runtimeDir} = run.context;
    const controller = Number(new URL(run.context.endpoints.controller).port);
    const port = run.context.port;
    let again;
    try {
      await run.halt();
      again = await startRun('reference', {runtimeDir, port, endpointPorts: {controller}});
      assert.equal(again.context.endpoints.controller, `http://127.0.0.1:${controller}/`);
      assert.deepEqual(await again.probe(), {ok: true});
      assert.equal((await callController(again.context.endpoints.controller, 'controller/v1/devices', {credential: run.tokens.controller})).status, 401);
      assert.deepEqual(await again.checks(), [{id: 'device-boundary', outcome: 'passed'}, {id: 'paired-feed', outcome: 'skipped', reason: 'reference is not paired with a Hub'}]);
      await again.halt();
      again = await startRun('hub-paired', {runtimeDir, port, endpointPorts: {controller}, hub: run.hub, tokens: run.tokens});
      assert.equal(again.context.endpoints.controller, `http://127.0.0.1:${controller}/`);
      assert.equal((await callController(again.context.endpoints.controller, 'controller/v1/devices', {credential: run.tokens.controller})).status, 200);
      assert.equal(await again.backstop(), '');
    } finally {
      await again?.halt();
      await run.stop();
    }
  });
});

describe('hub-lifecycle-painted against a changing Hub', () => {
  const capture = async (run, name, outputName) => {
    const outputDir = join(results, outputName);
    await rm(outputDir, {recursive: true, force: true});
    const {runId, runtimeDir, dataDir, url, scenario, inputs, endpoints} = run.context;
    return runCaptureStep(run.plugin, name, {url, outputDir, scenario, dataDir, runtimeDir, runId, inputs, endpoints});
  };

  test('passes through a brief Hub outage at the start of the step', async () => {
    const run = await startRun('hub-paired');
    try {
      await until(() => wallState(run.context.url), value => value.feed.connection === 'current');
      run.hub.status = 503;
      setTimeout(() => {run.hub.status = 200}, 1500);
      const result = await capture(run, 'hub-lifecycle-painted', 'hub-lifecycle-painted-after-outage');
      assert.equal(result.outcome, 'passed', JSON.stringify(result, null, 2));
    } finally {
      await run.stop();
    }
  });

  test('fails when a Hub session gets no Line', async () => {
    const run = await startRun('hub-paired');
    try {
      // Sixteen working sessions for fifteen Lines: one waits for a Line.
      const template = FEED.envelope.snapshot.sessions[0];
      run.hub.envelope = structuredClone(FEED.envelope);
      run.hub.envelope.snapshot.sessions = Array.from({length: 16}, (_, index) =>
        ({...structuredClone(template), identity: {...template.identity, sessionId: `hub-busy-${index}`}, label: `Busy ${index}`}));
      const result = await capture(run, 'hub-lifecycle-painted', 'hub-lifecycle-painted-unplaced');
      assert.equal(result.outcome, 'failed');
      assert.deepEqual(result.assertions.filter(item => item.outcome === 'failed').map(item => item.name), ['each Hub-fed task is placed on a Line'],
        JSON.stringify(result, null, 2));
    } finally {
      await run.stop();
    }
  });
});

describe("the map's own layout retry", () => {
  test('device-read-refused passes when the map retries its layout read during the step', async () => {
    const run = await startRun('layout-unavailable');
    const outputDir = join(results, 'device-read-refused-after-retry');
    await rm(outputDir, {recursive: true, force: true});
    try {
      // The map retries its layout read on the first poll at least 10 s after it started.
      await new Promise(resolve => setTimeout(resolve, 10500));
      const {runId, runtimeDir, dataDir, url, scenario} = run.context;
      const result = await runCaptureStep(plugin, 'device-read-refused', {url, outputDir, scenario, dataDir, runtimeDir, runId});
      assert.equal(result.outcome, 'passed', JSON.stringify(result, null, 2));
      const record = JSON.parse(await readFile(result.attachments.find(path => path.endsWith('/device-boundary.json')), 'utf8'));
      assert.ok(record.duringStep.length >= 1, 'the retry happened during the step');
      assert.ok(record.duringStep.every(entry => entry.kind === 'light-request' && entry.method === 'GET' && entry.target === '192.0.2.1'));
    } finally {
      await run.stop();
    }
  });
});

describe('a map that reads its layout on every poll', () => {
  test('fails device-read-refused and the boundary check', async () => {
    const run = await startRun('layout-unavailable', {serve: join(plugin.root, 'tests/fixtures/eager_layout_map.py')});
    const outputDir = join(results, 'device-read-refused-eager-map');
    await rm(outputDir, {recursive: true, force: true});
    try {
      await new Promise(resolve => setTimeout(resolve, 1500));
      const {runId, runtimeDir, dataDir, url, scenario} = run.context;
      const result = await runCaptureStep(plugin, 'device-read-refused', {url, outputDir, scenario, dataDir, runtimeDir, runId});
      assert.equal(result.outcome, 'failed');
      assert.deepEqual(result.assertions.filter(item => item.outcome === 'failed').map(item => item.name),
        ["the only device attempts during the step are the map's bounded layout reads"], JSON.stringify(result, null, 2));
      assert.match(result.reason, /Layout reads since the seed: expected null, saw "(layout read 2 came \d+ ms after the previous one|\d+ layout reads, more than the map's 3)"/);
      assert.equal((await deviceBoundary({dataDir, scenario})).outcome, 'failed');
    } finally {
      await run.stop();
    }
  });
});

describe('capture steps through the core driver', () => {
  for (const [name, step] of Object.entries(plugin.captureSteps)) {
    const control = NEGATIVE_CONTROLS[name];
    test(control ? `${name} fails at "${control}"` : `${name} passes`, async () => {
      const run = await startRun(step.scenario);
      const outputDir = join(results, name);
      await rm(outputDir, {recursive: true, force: true});
      try {
        const {runId, runtimeDir, dataDir, url, scenario, inputs, endpoints} = run.context;
        const result = await runCaptureStep(run.plugin, name, {url, outputDir, scenario, dataDir, runtimeDir, runId, inputs, endpoints});
        const failed = result.assertions.filter(assertion => assertion.outcome === 'failed').map(assertion => assertion.name);
        const record = result.attachments.find(path => path.endsWith('/device-boundary.json'));
        assert.ok(record, 'the boundary record is attached, also to a failed capture');
        const during = JSON.parse(await readFile(record, 'utf8')).duringStep;
        const refused = during.filter(entry => entry.outcome !== 'allowed').map(entry => [entry.kind, entry.method, entry.endpoint, entry.target]).sort();
        const effects = [['light-request', 'PUT', '/effects', '192.0.2.1'], ['light-request', 'PUT', '/effects', '192.0.2.2']];
        if (control) {
          if (name === 'control-device-attempt' || name === 'control-paired-light-request') assert.deepEqual(refused, effects);
          if (name === 'control-paired-installed-port') assert.deepEqual(refused, [['socket.connect', undefined, undefined, '127.0.0.1:8788']]);
          assert.equal(result.outcome, 'failed');
          assert.deepEqual(failed, [control], JSON.stringify(result, null, 2));
          assert.ok(result.reason.startsWith(`assertion failed: ${control}`), result.reason);
        } else {
          assert.equal(result.outcome, 'passed', JSON.stringify(result, null, 2));
          assert.ok(result.screenshot && result.video, 'a screenshot and a finalized video exist');
          assert.deepEqual(during.filter(entry => !(name === 'device-read-refused' && entry.kind === 'light-request' && entry.method === 'GET')
            && !(step.scenario === 'hub-paired' && entry.outcome === 'allowed' && entry.target === new URL(inputs['hub-feed']).host)), []);
        }
        const entry = step.scenario === 'hub-paired' ? 'tests/fixtures/backstop_demo.py' : 'scripts/demo.py';
        assert.ok((await readFile(result.log, 'utf8')).includes(`demo entry: ${entry}`), 'the capture log names the demo entry that served it');
        if (step.scenario === 'hub-paired') {
          assert.equal(await run.backstop(), '', 'nothing reached the test backstop');
          const log = await readFile(result.log, 'utf8');
          for (const secret of Object.values(run.tokens)) assert.equal(log.includes(secret), false, 'no credential in the capture log');
        }
      } finally {
        await run.stop();
      }
    });
  }
});
