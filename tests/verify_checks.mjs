// #193: the wall verification plug-in against real served runs, without the core's systemd supervisor.
//
// Each run is seeded and launched here the way the core's `start` does it, with the demo as a plain
// child process. Capture steps run through the core's own `runCaptureStep`, the same driver and pass
// rule as `npm run verify -- capture`. Reference steps must pass with a screenshot and a finalized
// video; each negative control must fail at its named assertion rather than crash. The supervised
// lifecycle (units, lease, receipt, handoff) needs a systemd user manager and is exercised locally.
import assert from 'node:assert/strict';
import {execFile, spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {existsSync} from 'node:fs';
import {mkdir, mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import readline from 'node:readline';
import {describe, test} from 'node:test';
import {promisify} from 'node:util';
import {runCaptureStep} from '@jimmie-potts/app-verify';
import plugin, {createPlugin, deviceBoundary, failureCause, readyLine} from '../scripts/verify/plugin.mjs';
import {NEGATIVE_CONTROLS, strict, strictSteps} from '../scripts/verify/steps.mjs';

const results = join(plugin.root, 'test-results/verify');

/** Seed, launch and wait for readiness the way the core's `start` does, with the process as a plain child. */
async function startRun(scenario, {serve} = {}) {
  const runtimeDir = await mkdtemp(join(tmpdir(), 'wall-verify-'));
  const dataDir = join(runtimeDir, 'data');
  await mkdir(dataDir);
  await mkdir(join(runtimeDir, 'tmp'));
  const paths = {runId: `wall-test-${randomBytes(3).toString('hex')}`, root: plugin.root, runtimeDir, dataDir, scenario};
  await plugin.scenarios[scenario].seed(paths);
  const spec = await plugin.launch({...paths, port: 0, node: process.execPath});
  // A test can serve through another entry point that takes demo.py's arguments.
  if (serve) spec.argv = spec.argv.map(argument => argument.endsWith('scripts/demo.py') ? serve : argument);
  const child = spawn(spec.argv[0], spec.argv.slice(1), {cwd: spec.cwd ?? plugin.root, stdio: ['ignore', 'pipe', 'pipe'],
    env: {...process.env, ...spec.env, TMPDIR: join(runtimeDir, 'tmp')}});
  let errors = '';
  child.stderr.on('data', data => {errors += data});
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`No ready line: ${errors}`)), plugin.readiness.timeoutMs);
    child.once('exit', code => {clearTimeout(timer); reject(new Error(`Exited ${code}: ${errors}`))});
    readline.createInterface({input: child.stdout}).on('line', line => {
      const ready = plugin.readiness.line(line);
      if (ready) {clearTimeout(timer); resolve(ready.url)}
    });
  });
  const context = {...paths, url, port: Number(new URL(url).port), signal: AbortSignal.timeout(60000)};
  return {
    context,
    probe: () => plugin.readiness.probe(context),
    checks: () => Promise.all(plugin.checks.map(async check => ({id: check.id, ...await check.run(context)}))),
    async stop() {
      if (child.exitCode === null && child.signalCode === null) {
        const exited = new Promise(resolve => child.once('exit', resolve));
        child.kill('SIGTERM');
        await exited;
      }
      await rm(runtimeDir, {recursive: true, force: true});
    },
  };
}

describe('plug-in surface', () => {
  test('the ready line must name a loopback origin', () => {
    assert.deepEqual(readyLine('{"url": "http://127.0.0.1:41705", "instance": "ab12"}'), {url: 'http://127.0.0.1:41705/'});
    for (const line of ['', 'Serving', '{}', '{"url": "http://localhost:41705"}', '{"url": "http://0.0.0.0:41705"}',
      '{"url": "https://127.0.0.1:41705"}', '{"url": "http://127.0.0.1"}', '{"url": "http://127.0.0.1:41705/x"}']) {
      assert.equal(readyLine(line), undefined, line);
    }
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
    const spec = await plugin.launch({dataDir: '/run/data', port: 41705});
    assert.deepEqual(spec.argv.slice(-4), ['--state-dir', '/run/data', '--port', '41705']);
    assert.ok(Object.keys(spec.env).every(key => key.startsWith('PYTHON')), JSON.stringify(spec.env));
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
  for (const scenario of Object.keys(plugin.scenarios)) {
    test(`${scenario}: the map is ready and the device-boundary check passes`, async () => {
      const run = await startRun(scenario);
      try {
        assert.deepEqual(await run.probe(), {ok: true});
        assert.deepEqual(await run.checks(), [{id: 'device-boundary', outcome: 'passed'}]);
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
        const {runId, runtimeDir, dataDir, url, scenario} = run.context;
        const result = await runCaptureStep(plugin, name, {url, outputDir, scenario, dataDir, runtimeDir, runId});
        const failed = result.assertions.filter(assertion => assertion.outcome === 'failed').map(assertion => assertion.name);
        const record = result.attachments.find(path => path.endsWith('/device-boundary.json'));
        assert.ok(record, 'the boundary record is attached, also to a failed capture');
        const during = JSON.parse(await readFile(record, 'utf8')).duringStep;
        if (control) {
          if (name === 'control-device-attempt') {
            assert.deepEqual(during.map(entry => [entry.kind, entry.method, entry.endpoint, entry.target]).sort(),
              [['light-request', 'PUT', '/effects', '192.0.2.1'], ['light-request', 'PUT', '/effects', '192.0.2.2']]);
          }
          assert.equal(result.outcome, 'failed');
          assert.deepEqual(failed, [control], JSON.stringify(result, null, 2));
          assert.ok(result.reason.startsWith(`assertion failed: ${control}`), result.reason);
        } else {
          assert.equal(result.outcome, 'passed', JSON.stringify(result, null, 2));
          assert.ok(result.screenshot && result.video, 'a screenshot and a finalized video exist');
          assert.deepEqual(during.filter(entry => !(name === 'device-read-refused' && entry.kind === 'light-request' && entry.method === 'GET')), []);
        }
      } finally {
        await run.stop();
      }
    });
  }
});
