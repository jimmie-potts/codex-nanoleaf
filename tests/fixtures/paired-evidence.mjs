// #194: the delivery evidence procedure for a hub-paired change, on the default roots.
//
//   node tests/fixtures/paired-evidence.mjs <record directory>
//
// It starts one wall run and captures the standalone reference steps. It then writes the two
// credential files as Hub #495's orchestrator does, pairs the run with a stand-in Hub feed
// (tests/fixtures/stand-in-hub.mjs), makes the Hub's controller calls
// (tests/fixtures/controller-caller.mjs) and captures hub-lifecycle-painted. It hands off with a
// reset, then captures every control after handoff. control-paired-installed-port runs through
// tests/fixtures/backstop-verify.mjs, beneath the test backstop. Finally it reseeds reference,
// scans every record for the tokens and stops the run. The record directory receives each JSON
// result and `summary.txt`, whose exit codes are the operations' own. It never holds a token.
import {spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {existsSync} from 'node:fs';
import {mkdir, readdir, readFile, stat, writeFile, appendFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {exercise} from './controller-caller.mjs';
import {standInHub} from './stand-in-hub.mjs';

const ROOT = fileURLToPath(new URL('../..', import.meta.url));
const REFERENCE = ['wall-ready', 'task-completes', 'approval-clears-red', 'approval-requested', 'task-resumes', 'project-layout', 'lighting-modes', 'panels-view', 'device-read-refused'];
const CONTROLS = ['control-stale-completion', 'control-unread-painted-working', 'control-device-attempt', 'control-stale-red', 'control-paired-light-request'];
const out = process.argv[2];
if (!out) throw new Error('usage: node tests/fixtures/paired-evidence.mjs <record directory>');
await mkdir(out, {recursive: true});
const summary = async line => {
  console.log(line);
  await appendFile(join(out, 'summary.txt'), line + '\n');
};

/** One adapter operation; resolves with its exit code and JSON result line. */
function verify(args, entry = 'scripts/verify.mjs') {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [join(ROOT, entry), ...args], {cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe']});
    let stdout = '';
    child.stdout.on('data', data => {stdout += data});
    child.stderr.on('data', data => appendFile(join(out, 'progress.log'), data));
    child.on('error', reject);
    child.on('exit', code => {
      const line = stdout.trim().split('\n').filter(Boolean).at(-1);
      resolve({code, result: line ? JSON.parse(line) : null});
    });
  });
}

const record = async (name, value) => writeFile(join(out, name), JSON.stringify(value, null, 2) + '\n');
async function capture(runId, step, entry) {
  const {code, result} = await verify(['capture', runId, step], entry);
  await appendFile(join(out, 'captures.jsonl'), JSON.stringify({code, ...result}) + '\n');
  await summary(`capture ${step}${entry ? ` (${entry})` : ''}: exit ${code}, ${result?.outcome} in ${result?.set}${result?.reason ? ` :: ${result.reason.slice(0, 110)}` : ''}`);
  return {code, result};
}

const start = await verify(['start', '--scenario', 'reference', '--lease', '60']);
await record('start.json', start);
if (start.code !== 0) throw new Error(`start exited ${start.code}`);
const {runId, url, proofDir} = start.result;
await summary(`run ${runId} at ${url}: start exit ${start.code}, revision ${start.result.build.sourceRevision}, dirty ${start.result.build.dirty}`);
// The core's runtime root; the run's directory is `<root>/<run id>/`.
const runtimeDir = join(process.env.APP_VERIFY_STATE_ROOT ?? join(homedir(), '.local/state/app-verify'), runId);
let hub;
try {
  for (const step of REFERENCE) await capture(runId, step);
  const tokens = {feed: randomBytes(32).toString('base64url'), controller: randomBytes(32).toString('base64url')};
  await writeFile(join(runtimeDir, 'hub-feed-token'), tokens.feed, {mode: 0o600, flag: 'wx'});
  await writeFile(join(runtimeDir, 'hub-controller-token'), tokens.controller, {mode: 0o600, flag: 'wx'});
  hub = await standInHub(tokens.feed, {log: join(out, 'stand-in-hub.jsonl')});
  const paired = await verify(['scenario', runId, 'hub-paired', '--input', `hub-feed=${hub.origin}`]);
  await record('scenario-hub-paired.json', paired);
  const controller = paired.result?.endpoints?.controller;
  await summary(`scenario hub-paired: exit ${paired.code}, stand-in Hub ${hub.origin}, controller ${controller}`);
  let doctor;
  for (let waited = 0; waited < 15000; waited += 500) {
    doctor = await verify(['doctor', runId]);
    if (doctor.result.runs[0].checks.find(check => check.id === 'paired-feed')?.outcome === 'passed') break;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  await record('doctor-paired.json', doctor);
  await summary(`doctor while paired: exit ${doctor.code}, checks ${JSON.stringify(doctor.result.runs[0].checks)}, listener ${JSON.stringify(doctor.result.runs[0].listener)}`);
  const calls = await exercise(controller, tokens.controller, url);
  await record('controller-caller.json', calls);
  await summary(`controller caller: ${JSON.stringify({without: calls.withoutCredential, devices: calls.devices, command: calls.command, receipt: calls.receipt, integration: calls.verifyState.integration, feed: calls.verifyState.feed})}`);
  await capture(runId, 'hub-lifecycle-painted');

  const handoff = await verify(['handoff', runId, '--reset', 'reference']);
  await record('handoff.json', handoff);
  await summary(`handoff: exit ${handoff.code}, frozen at ${handoff.result?.frozenAt}`);
  for (const step of CONTROLS) await capture(runId, step);
  await capture(runId, 'control-paired-installed-port', 'tests/fixtures/backstop-verify.mjs');
  const backstop = join(runtimeDir, 'backstop.jsonl');
  await summary(`backstop log lines: ${existsSync(backstop) ? (await readFile(backstop, 'utf8')).trim().split('\n').filter(Boolean).length : 0}`);
  const after = await verify(['doctor', runId]);
  await record('doctor-after-controls.json', after);
  await summary(`doctor after the controls: exit ${after.code}, checks ${JSON.stringify(after.result.runs[0].checks)}`);
  const reference = await verify(['scenario', runId, 'reference']);
  await record('scenario-reference.json', reference);
  const final = await verify(['doctor', runId]);
  await record('doctor-final.json', final);
  await summary(`scenario reference: exit ${reference.code}, endpoints ${JSON.stringify(reference.result?.endpoints)}; doctor: exit ${final.code}, checks ${JSON.stringify(final.result.runs[0].checks)}, proof sums ${final.result.runs[0].proof.sums}`);

  // Every file the run and this procedure wrote, before stop deletes the runtime directory.
  const files = async directory => (await readdir(directory, {recursive: true})).map(name => join(directory, name));
  let holding = 0;
  for (const file of [...await files(out), ...await files(proofDir), ...await files(join(runtimeDir, 'data')), join(runtimeDir, 'stdout.log'), join(runtimeDir, 'stderr.log')]) {
    if (!(await stat(file).catch(() => null))?.isFile()) continue;
    const text = await readFile(file, 'latin1');
    if (text.includes(tokens.feed) || text.includes(tokens.controller)) holding++;
  }
  await summary(`files holding a token (records, proof, state, app logs): ${holding}`);
} finally {
  const stop = await verify(['stop', runId]);
  await record('stop.json', stop);
  await summary(`stop: exit ${stop.code}, ${stop.result?.state}, cleanup ${stop.result?.cleanup?.result}`);
  await hub?.close();
}
