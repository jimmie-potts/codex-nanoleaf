// #193: the wall verification plug-in against real served runs, without the shared core's supervisor.
//
// Each capture step runs on its own freshly seeded run of the actual wall server, in a fresh
// Chromium context that records video, as the core's capture harness will. Reference steps must
// pass; each negative control must fail at its named assertion, never by crashing.
import assert from 'node:assert/strict';
import {execFile, spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {mkdir, mkdtemp, readFile, rm, stat, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import readline from 'node:readline';
import {after, before, describe, test} from 'node:test';
import {promisify} from 'node:util';
import {chromium} from 'playwright';
import plugin, {readyLine} from '../scripts/verify/plugin.mjs';
import {NEGATIVE_CONTROLS} from '../scripts/verify/steps.mjs';

const results = join(plugin.root, 'test-results/verify');
class StepEnded extends Error {}

/** Seed, launch and wait for readiness the way the core's `start` does, with the process as a plain child. */
async function startRun(scenario) {
  const runtimeDir = await mkdtemp(join(tmpdir(), 'wall-verify-'));
  const dataDir = join(runtimeDir, 'data');
  await mkdir(dataDir);
  await mkdir(join(runtimeDir, 'tmp'));
  const paths = {runId: `wall-test-${randomBytes(3).toString('hex')}`, root: plugin.root, runtimeDir, dataDir, scenario};
  await plugin.scenarios[scenario].seed(paths);
  const spec = await plugin.launch({...paths, port: 0, node: process.execPath});
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

/** One capture: the step's assertions, an after screenshot and a finalized video. */
async function capture(browser, run, name) {
  const step = plugin.captureSteps[name];
  const directory = join(results, name);
  await rm(directory, {recursive: true, force: true});
  await mkdir(directory, {recursive: true});
  const viewport = step.viewport ?? {width: 1280, height: 800};
  const context = await browser.newContext({viewport, recordVideo: {dir: directory, size: viewport}});
  const page = await context.newPage();
  const log = [];
  let failure = null, crash = null;
  const t = {
    ...run.context, page, context,
    async expect(assertion, check) {
      try {
        await check();
        log.push({assertion, outcome: 'passed'});
      } catch (error) {
        log.push({assertion, outcome: 'failed', error: error.message});
        failure = assertion;
        throw new StepEnded(assertion);
      }
    },
    note: message => log.push({note: message}),
    screenshot: label => page.screenshot({path: join(directory, `${label}.png`), fullPage: true}),
  };
  try {
    await step.run(t);
  } catch (error) {
    if (!(error instanceof StepEnded)) crash = error;
  }
  await page.screenshot({path: join(directory, 'after.png'), fullPage: true});
  const video = page.video();
  await context.close();
  const videoBytes = (await stat(await video.path())).size;
  await writeFile(join(directory, 'assertions.json'), `${JSON.stringify({step: name, failure, crash: crash?.message ?? null, log}, null, 2)}\n`);
  const passed = !crash && !failure && log.some(entry => entry.outcome === 'passed') && videoBytes > 0;
  return {outcome: passed ? 'passed' : 'failed', failure, crash, log, videoBytes};
}

let browser;
before(async () => {
  browser = await chromium.launch({headless: true, ...(process.env.NANOLEAF_BROWSER_EXECUTABLE ? {executablePath: process.env.NANOLEAF_BROWSER_EXECUTABLE} : {})});
});
after(async () => browser?.close());

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

  test('every capture step names a seeded scenario, and every control names a step', () => {
    for (const [name, step] of Object.entries(plugin.captureSteps)) assert.ok(plugin.scenarios[step.scenario], name);
    for (const name of Object.keys(NEGATIVE_CONTROLS)) assert.ok(plugin.captureSteps[name], name);
  });

  test('the launch binds the requested port and carries no credential', async () => {
    const spec = await plugin.launch({dataDir: '/run/data', port: 41705});
    assert.deepEqual(spec.argv.slice(-4), ['--state-dir', '/run/data', '--port', '41705']);
    assert.ok(Object.keys(spec.env).every(key => key.startsWith('PYTHON')), JSON.stringify(spec.env));
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

describe('capture steps', () => {
  for (const [name, step] of Object.entries(plugin.captureSteps)) {
    const control = NEGATIVE_CONTROLS[name];
    test(control ? `${name} fails at "${control}"` : `${name} passes`, async () => {
      const run = await startRun(step.scenario);
      try {
        const result = await capture(browser, run, name);
        assert.equal(result.crash, null, result.crash?.stack);
        assert.ok(result.videoBytes > 0, 'the video was finalized');
        if (control) {
          assert.equal(result.outcome, 'failed');
          assert.equal(result.failure, control, JSON.stringify(result.log, null, 2));
        } else {
          assert.equal(result.outcome, 'passed', JSON.stringify(result.log, null, 2));
        }
      } finally {
        await run.stop();
      }
    });
  }
});
