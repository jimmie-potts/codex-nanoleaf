// #193: the wall plug-in through the shared core's supervised lifecycle, against real transient
// systemd user units. Each test uses a unique app name and private runtime and proof roots outside
// every checkout, so it never lists, touches or stops a real `wall` run, and it stops every run it
// starts. Without a user manager the tests skip with the reason printed; APP_VERIFY_REQUIRE_SYSTEMD=1
// turns that into a failure.
import assert from 'node:assert/strict';
import {execFileSync, spawn, spawnSync} from 'node:child_process';
import {createHash, randomBytes} from 'node:crypto';
import {existsSync} from 'node:fs';
import {chmod, mkdir, mkdtemp, readdir, readFile, rm, writeFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {join} from 'node:path';
import {after, before, test} from 'node:test';
import {validateReceipt} from '@jimmie-potts/app-verify';
import plugin from '../scripts/verify/plugin.mjs';

function supervisorSkipReason() {
  const result = spawnSync('systemctl', ['--user', 'is-system-running'], {encoding: 'utf8'});
  const state = (result.stdout ?? '').trim();
  if (['running', 'degraded', 'starting', 'initializing'].includes(state)) return undefined;
  const reason = `no systemd --user manager (is-system-running: ${state || result.error?.message || 'no answer'})`;
  if (process.env.APP_VERIFY_REQUIRE_SYSTEMD === '1') throw new Error(`APP_VERIFY_REQUIRE_SYSTEMD=1 but ${reason}`);
  process.stderr.write(`SKIP wall lifecycle tests: ${reason}. Run them on a Linux host with a user manager.\n`);
  return reason;
}

const skip = supervisorSkipReason();
const core = import.meta.resolve('@jimmie-potts/app-verify');
const pluginModule = import.meta.resolve('../scripts/verify/plugin.mjs');
const app = `wt-${randomBytes(3).toString('hex')}`;
let base, env;
const started = new Set();

before(async () => {
  if (skip) return;
  // Runtime state must be outside every checkout; TMPDIR may point into one, so use the user cache.
  await mkdir(join(homedir(), '.cache/codex-nanoleaf'), {recursive: true});
  base = await mkdtemp(join(homedir(), '.cache/codex-nanoleaf/verify-test-'));
  await mkdir(join(base, 'tmp'));
  env = {...process.env, TMPDIR: join(base, 'tmp'), APP_VERIFY_STATE_ROOT: join(base, 'state'), APP_VERIFY_PROOF_ROOT: join(base, 'proof'), APP_VERIFY_WINDOWS_CHECK: 'off'};
});

after(async () => {
  if (skip) return;
  for (const runId of started) await cli(['stop', runId]);
  const leftover = execFileSync('systemctl', ['--user', 'list-units', '--all', '--no-legend', '--plain', `app-verify-${app}-*`], {encoding: 'utf8'}).trim();
  // Handoff made each verified/ set read-only; restore write permission inside this file's own root first.
  const writable = async path => {
    await chmod(path, 0o700);
    for (const entry of await readdir(path, {withFileTypes: true})) {
      if (entry.isDirectory()) await writable(join(path, entry.name));
      else await chmod(join(path, entry.name), 0o600);
    }
  };
  await writable(base);
  await rm(base, {recursive: true, force: true});
  assert.equal(leftover, '', 'every unit this file started is gone');
});

/**
 * A wrapper for one plug-in variant. `variant` is JavaScript that receives the real plug-in `p`
 * and returns the plug-in to run, so a test can break exactly one part of the real wall.
 */
async function wrapper(name, variant = 'p') {
  const path = join(base, `${name}.mjs`);
  await writeFile(path, `import {runCli} from ${JSON.stringify(core)};
import {createPlugin} from ${JSON.stringify(pluginModule)};
const p = createPlugin({app: ${JSON.stringify(app)}});
process.exitCode = await runCli(${variant}, process.argv.slice(2));
`);
  return path;
}

/** Run one operation in a child process; resolve with its exit code and JSON result. */
function cli(args, {entry, onSpawn} = {}) {
  return new Promise(async (resolve, reject) => {
    const child = spawn(process.execPath, [entry ?? await wrapper('verify'), ...args], {cwd: plugin.root, env, stdio: ['ignore', 'pipe', 'pipe']});
    let stdout = '', stderr = '';
    child.stdout.on('data', data => {stdout += data});
    child.stderr.on('data', data => {stderr += data});
    child.on('error', reject);
    child.on('exit', (code, signal) => {
      const line = stdout.trim().split('\n').filter(Boolean).at(-1);
      let result = null;
      try {
        result = line ? JSON.parse(line) : null;
      } catch {
        result = null;
      }
      if (result?.runId) started.add(result.runId);
      resolve({code, signal, result, stderr});
    });
    onSpawn?.(child);
  });
}

const receiptOf = async runId => JSON.parse(await readFile(join(base, 'proof', runId, 'receipt.json'), 'utf8'));
const unitLoaded = unit => execFileSync('systemctl', ['--user', 'show', unit, '-p', 'LoadState', '--value'], {encoding: 'utf8'}).trim() === 'loaded';
const stateOf = async url => (await fetch(new URL('/api/state', url))).json();
const doctor = async runId => (await cli(['doctor', runId])).result.runs[0];

function expectedDigest() {
  const files = plugin.build.artifact.files;
  const lines = files.map(file => `${createHash('sha256').update(execFileSync('cat', [join(plugin.root, file)])).digest('hex')}  ${file}\n`).join('');
  return 'sha256:' + createHash('sha256').update(lines).digest('hex');
}

test('a run starts leased and identified, captures, freezes its proof, extends and stops cleanly', {skip}, async () => {
  const start = await cli(['start', '--scenario', 'reference', '--lease', '10']);
  assert.equal(start.code, 0, start.stderr);
  const {runId, url, port} = start.result;
  const receipt = await receiptOf(runId);
  assert.deepEqual(validateReceipt(receipt), {ok: true});
  const head = execFileSync('git', ['-C', plugin.root, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
  const dirty = execFileSync('git', ['-C', plugin.root, 'status', '--porcelain', '--untracked-files=no'], {encoding: 'utf8'}).trim() !== '';
  assert.deepEqual([receipt.build.sourceRevision, receipt.build.dirty, receipt.build.artifactDigest], [head, dirty, expectedDigest()]);
  assert.deepEqual(receipt.checks.map(check => [check.id, check.outcome]), [['readiness', 'passed'], ['device-boundary', 'passed'], ['windows-loopback', 'skipped']]);
  assert.deepEqual(receipt.components, plugin.components);
  assert.equal(url, `http://127.0.0.1:${port}/`);
  assert.equal(JSON.stringify(receipt).includes((await (await fetch(url)).text()).split("const token='")[1].slice(0, 64)), false, 'the page token is in no receipt');

  let row = await doctor(runId);
  assert.deepEqual([row.state, row.health.outcome, row.artifact, row.listener.outcome], ['running', 'passed', 'matches', 'matches']);
  assert.deepEqual(row.checks, [{id: 'device-boundary', outcome: 'passed'}], 'doctor re-runs the read-only boundary check');
  assert.equal(existsSync(join(base, 'state', runId, 'home')), true, 'the wall runs with the core\'s private HOME');

  const passed = await cli(['capture', runId, 'task-completes']);
  assert.deepEqual([passed.code, passed.result.outcome, passed.result.set], [0, 'passed', 'verified']);
  const control = await cli(['capture', runId, 'control-stale-red']);
  assert.equal(control.code, 1);
  assert.match(control.result.reason, /^assertion failed: task-1 reads working in the task list/);
  assert.equal((await doctor(runId)).unit.mainPid !== row.unit.mainPid, true, 'fresh steps relaunched the wall');

  const handoff = await cli(['handoff', runId, '--reset', 'reference']);
  assert.equal(handoff.code, 0, handoff.stderr);
  assert.ok(existsSync(join(base, 'proof', runId, 'verified/SHA256SUMS')));
  const later = await cli(['capture', runId, 'wall-ready']);
  assert.deepEqual([later.code, later.result.set], [0, 'after-handoff']);
  const extend = await cli(['extend', runId, '--lease', '20']);
  assert.equal(extend.code, 0, extend.stderr);
  row = await doctor(runId);
  assert.deepEqual([row.state, row.leaseTimer.name.endsWith('-lease-2.timer'), row.proof.sums, row.preview.url], ['running', true, 'ok', url]);

  const stop = await cli(['stop', runId]);
  assert.deepEqual([stop.code, stop.result.state, stop.result.cleanup.result], [0, 'stopped', 'clean']);
  row = await doctor(runId);
  assert.deepEqual([row.state, row.unit, row.leaseTimers, row.runtimeDir, row.proof.sums], ['stopped', null, [], 'missing', 'ok']);
  started.delete(runId);
});

test('two concurrent runs share nothing, and a reseed changes only its own run', {skip}, async () => {
  const [first, second] = await Promise.all([cli(['start', '--lease', '10']), cli(['start', '--lease', '10'])]);
  assert.equal(first.code, 0, first.stderr);
  assert.equal(second.code, 0, second.stderr);
  assert.notEqual(first.result.port, second.result.port);
  assert.notEqual(first.result.runId, second.result.runId);
  const secondBefore = await doctor(second.result.runId);
  const reseed = await cli(['scenario', first.result.runId, 'empty']);
  assert.equal(reseed.code, 0, reseed.stderr);
  assert.equal((await stateOf(first.result.url)).tasks.length, 0);
  assert.equal((await stateOf(second.result.url)).tasks.length, 5);
  assert.equal((await doctor(second.result.runId)).unit.mainPid, secondBefore.unit.mainPid, 'the other run was not relaunched');
  for (const run of [first, second]) assert.equal((await cli(['stop', run.result.runId])).code, 0);
});

test('a wall that attempts a device request during start fails its boundary check and cleans up', {skip}, async () => {
  // The reference scenario served from state without drawing geometry: the server asks the Lines for their layout.
  const entry = await wrapper('attempts-device', `{...p, scenarios: {...p.scenarios, reference: {...p.scenarios.reference,
    seed: context => p.scenarios['layout-unavailable'].seed({...context, scenario: 'layout-unavailable'})}}}`);
  const start = await cli(['start', '--lease', '10'], {entry});
  assert.equal(start.code, 1);
  assert.deepEqual([start.result.state, start.result.cause, start.result.cleanup.result], ['failed', 'check-failed', 'clean']);
  assert.match(start.result.detail, /^device-boundary: 1 device attempt\(s\) recorded since the last seed/);
  assert.equal(unitLoaded(`app-verify-${start.result.runId}.service`), false);
  assert.equal(existsSync(join(base, 'state', start.result.runId)), false);
  assert.equal((await doctor(start.result.runId)).state, 'failed');
  started.delete(start.result.runId);
});

test('a wall that exits before it is ready fails the start and leaves no unit, timer or runtime directory', {skip}, async () => {
  const entry = await wrapper('broken-launch', `{...p, launch: context => p.launch({...context, dataDir: context.dataDir + '/missing'})}`);
  const start = await cli(['start', '--lease', '10'], {entry});
  assert.equal(start.code, 1);
  assert.deepEqual([start.result.state, start.result.cause, start.result.cleanup.result], ['failed', 'unit-exited', 'clean']);
  assert.match(start.result.detail, /; app: wall-start-failed: the state directory was not seeded by demo\.py$/);
  assert.deepEqual(start.result.cleanup.items.map(item => [item.kind, item.outcome]), [['lease-timer', 'removed'], ['unit', 'absent'], ['runtime-dir', 'removed']]);
  const row = await doctor(start.result.runId);
  assert.deepEqual([row.state, row.failure.cause, row.unit, row.leaseTimers, row.runtimeDir], ['failed', 'unit-exited', null, [], 'missing']);
  started.delete(start.result.runId);
});

test('a start killed after seeding is listed by doctor, and stop removes what exists', {skip}, async () => {
  const marker = join(base, 'seeded');
  const entry = await wrapper('slow-seed', `{...p, scenarios: {...p.scenarios, reference: {...p.scenarios.reference, seed: async context => {
    await p.scenarios.reference.seed(context);
    (await import('node:fs')).writeFileSync(${JSON.stringify(marker)}, context.runId);
    await new Promise(resolve => setTimeout(resolve, 60000));
  }}}}`);
  let child;
  const killed = cli(['start', '--lease', '10'], {entry, onSpawn: spawned => {child = spawned}});
  for (let waited = 0; !existsSync(marker) && waited < 30000; waited += 100) await new Promise(resolve => setTimeout(resolve, 100));
  const runId = (await readFile(marker, 'utf8')).trim();
  started.add(runId);
  child.kill('SIGKILL');
  assert.equal((await killed).signal, 'SIGKILL');
  let row = await doctor(runId);
  assert.equal(row.receipt.state, 'starting');
  assert.equal(row.runtimeDir, 'present');
  assert.ok(existsSync(join(base, 'state', runId, 'data/status.sqlite')), 'the seeded state is still there');
  const stop = await cli(['stop', runId]);
  assert.equal(stop.code, 0, stop.stderr);
  row = await doctor(runId);
  assert.deepEqual([row.state, row.runtimeDir, row.unit, row.leaseTimers], ['stopped', 'missing', null, []]);
  started.delete(runId);
});

test('an expired run keeps its frozen proof and restarts as a new run that names it', {skip}, async () => {
  const start = await cli(['start', '--lease', '0.1']);
  assert.equal(start.code, 0, start.stderr);
  const {runId} = start.result;
  assert.equal((await cli(['capture', runId, 'wall-ready'])).code, 0);
  assert.equal((await cli(['handoff', runId])).code, 0);
  const manifest = join(base, 'proof', runId, 'verified/SHA256SUMS');
  const digest = async () => createHash('sha256').update(await readFile(manifest)).digest('hex');
  const frozen = await digest();
  const unit = `app-verify-${runId}.service`;
  for (let waited = 0; unitLoaded(unit) && waited < 30000; waited += 250) await new Promise(resolve => setTimeout(resolve, 250));
  assert.equal(unitLoaded(unit), false, 'the lease timer stopped the unit');
  let row = await doctor(runId);
  assert.deepEqual([row.state, row.reasons, row.proof.sums], ['expired', ['lease-expired', 'runtime-dir-awaits-stop'], 'ok']);
  const refused = await cli(['handoff', runId]);
  assert.deepEqual([refused.code, refused.result.error], [1, 'run-not-running'], 'an expired run cannot hand off again');
  const stop = await cli(['stop', runId]);
  assert.deepEqual([stop.code, stop.result.state, stop.result.cleanup.result], [0, 'expired', 'clean']);
  row = await doctor(runId);
  assert.deepEqual([row.state, row.runtimeDir, row.proof.sums], ['expired', 'missing', 'ok']);
  // A new preview from the expired run: restart names it, and its frozen proof stays as it was.
  const restart = await cli(['restart', runId]);
  assert.equal(restart.code, 0, restart.stderr);
  const dirty = execFileSync('git', ['-C', plugin.root, 'status', '--porcelain', '--untracked-files=no'], {encoding: 'utf8'}).trim() !== '';
  assert.deepEqual([restart.result.restarts, restart.result.continuity], [runId, dirty ? 'different-candidate' : 'same-candidate']);
  assert.equal((await receiptOf(restart.result.runId)).restarts, runId);
  assert.equal(await digest(), frozen, 'the expired run\'s verified SHA256SUMS is unchanged');
  assert.equal((await doctor(runId)).proof.sums, 'ok');
  started.delete(runId);
  assert.equal((await cli(['stop', restart.result.runId])).code, 0);
  started.delete(restart.result.runId);
});

test('restart names its predecessor and says whether the candidate is the same', {skip}, async () => {
  const start = await cli(['start', '--scenario', 'empty', '--lease', '10']);
  assert.equal(start.code, 0, start.stderr);
  const restart = await cli(['restart', start.result.runId]);
  assert.equal(restart.code, 0, restart.stderr);
  const dirty = execFileSync('git', ['-C', plugin.root, 'status', '--porcelain', '--untracked-files=no'], {encoding: 'utf8'}).trim() !== '';
  assert.deepEqual([restart.result.restarts, restart.result.scenario, restart.result.continuity],
    [start.result.runId, 'empty', dirty ? 'different-candidate' : 'same-candidate']);
  assert.equal((await receiptOf(restart.result.runId)).restarts, start.result.runId);
  assert.equal((await doctor(start.result.runId)).state, 'stopped');
  started.delete(start.result.runId);
  assert.equal((await cli(['stop', restart.result.runId])).code, 0);
  started.delete(restart.result.runId);
});
