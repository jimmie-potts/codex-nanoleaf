// The Nanoleaf wall plug-in for the shared app verification core (#193, Hub #494).
//
// It supplies only what is specific to the wall: the synthetic scenarios, the `scripts/demo.py
// serve` launch of the actual wall server, readiness, the actual and simulated components, the
// device-boundary and paired-feed checks and the capture steps. The core owns the run lifecycle.
//
// The hub-paired scenario (#194) pairs a run with a Hub run for Hub #495's integrated preview. The
// caller gives the Hub run's origin as the `hub-feed` input and writes the two credential files,
// mode 0600, into the run's runtime directory before the `scenario <run-id> hub-paired` reseed.
// From then on the run also serves the real controller API, announced as the `controller`
// endpoint, and its boundary allows connections to the Hub's feed port only.
import {execFile} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {readFile, stat} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';
import {definePlugin} from '@jimmie-potts/app-verify';
import {boundaryEntries, captureSteps, INSTALLED_PORTS, isLayoutRead, isPairedConnect, layoutReadProblem, PAIRED, pairedPort, readHubFeed, wallState} from './steps.mjs';

export {INSTALLED_PORTS, PAIRED, pairedPort};
const run = promisify(execFile);
export const SCENARIOS = {
  reference: 'Lines and Light Panels in Work with five tasks in all four statuses across three projects',
  empty: 'Lines and Light Panels in Work with no tasks, so the wall rests on its remembered scene',
  'layout-unavailable': 'The reference tasks on Lines saved without drawing geometry, so the map asks the device for its layout and the boundary refuses the request',
  'hub-paired': "Lines and Light Panels with no local tasks, following a paired Hub run's session feed and serving the controller API that Hub calls",
};
/** Non-secret run inputs; the paired Hub's credentials travel only as files in the runtime directory. */
export const INPUTS = {
  'hub-feed': {description: "hub-paired: the paired Hub run's origin, http://127.0.0.1:<port>/. The wall polls <hub-feed>api/monitor/v1."},
};
const TITLE = '<title>Nanoleaf · Wall map</title>';

/** `http://127.0.0.1:<port>/` exactly, or undefined. */
function loopbackOrigin(value, pathAllowed = false) {
  let url;
  try {
    url = new URL(value);
  } catch {
    return undefined;
  }
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.username || url.password || url.search || url.hash) return undefined;
  return url.pathname === '/' || pathAllowed ? url : undefined;
}

/**
 * Parse the demo's ready line, `{"url": "http://127.0.0.1:<port>", …}`, with its optional
 * `endpoints` map, each exactly `http://127.0.0.1:<port>/`; anything else is not a ready line.
 */
export function readyLine(line) {
  let value;
  try {
    value = JSON.parse(line);
  } catch {
    return undefined;
  }
  if (typeof value?.url !== 'string') return undefined;
  const url = loopbackOrigin(value.url);
  if (!url) return undefined;
  if (value.endpoints === undefined) return {url: url.href};
  if (typeof value.endpoints !== 'object' || value.endpoints === null || Array.isArray(value.endpoints)) return undefined;
  const endpoints = {};
  for (const [name, endpoint] of Object.entries(value.endpoints)) {
    const parsed = typeof endpoint === 'string' ? loopbackOrigin(endpoint) : undefined;
    if (name !== 'controller' || !parsed || parsed.href !== endpoint) return undefined;
    endpoints[name] = parsed.href;
  }
  return {url: url.href, endpoints};
}

/**
 * The map's own readiness: its receipt, its health route and its page, all naming this process.
 * A hub-paired run's boundary must allow exactly the paired Hub's port, and an announced
 * controller endpoint must be this run's controller listener, which refuses a request without a
 * credential. The probe never sends a credential.
 */
export async function probe({url, port, dataDir, scenario, inputs, endpoints = {}, signal}) {
  if (INSTALLED_PORTS.has(port)) return {ok: false, reason: `port ${port} belongs to an installed service`};
  let receipt;
  try {
    receipt = JSON.parse(await readFile(join(dataDir, 'map-server.json'), 'utf8'));
  } catch {
    return {ok: false, reason: 'map-server.json is missing or unreadable'};
  }
  if (receipt.port !== port) return {ok: false, reason: `map-server.json names port ${receipt.port}, not ${port}`};
  if (scenario === PAIRED.scenario) {
    const paired = pairedPort(inputs?.['hub-feed']);
    if (receipt.boundary !== 'paired' || paired === undefined || receipt.pairedPort !== paired) return {ok: false, reason: 'the served process did not install the paired device boundary'};
  } else if (receipt.boundary !== 'refusing') {
    return {ok: false, reason: 'the served process did not install the device boundary'};
  }
  const health = await fetch(new URL('/health', url), {signal});
  const body = health.ok ? await health.json() : null;
  if (body?.service !== 'codex-nanoleaf-map') return {ok: false, reason: `health answered ${health.status}`};
  if (body.instance !== receipt.instance) return {ok: false, reason: 'health names another map instance'};
  const page = await fetch(url, {signal});
  // The page embeds the per-process edit token; only its title is inspected, and nothing is printed.
  if (!page.ok || !(await page.text()).includes(TITLE)) return {ok: false, reason: `map page answered ${page.status}`};
  if (scenario === PAIRED.scenario && !endpoints.controller) return {ok: false, reason: 'hub-paired announced no controller endpoint'};
  if (endpoints.controller) {
    let listener;
    try {
      listener = JSON.parse(await readFile(join(dataDir, 'controller-server.json'), 'utf8'));
    } catch {
      return {ok: false, reason: 'controller-server.json is missing or unreadable'};
    }
    if (listener.port !== Number(new URL(endpoints.controller).port)) return {ok: false, reason: `controller-server.json names port ${listener.port}, not the announced controller endpoint`};
    const answer = await fetch(new URL('controller/v1/devices', endpoints.controller), {signal});
    const body = await answer.json().catch(() => null);
    if (answer.status !== 401 || body?.failure?.code !== 'unauthenticated') return {ok: false, reason: `the controller endpoint answered ${answer.status} without a credential`};
  }
  return {ok: true};
}

/**
 * The boundary check, at start and in `doctor`. The log starts empty at each seed and holds every
 * refusal, because the boundary records an attempt as it refuses it, and every connection it
 * allowed. A run records no attempt, except that layout-unavailable must record the map's layout
 * reads of the Lines, only those, and no more or more often than the map makes them, and a
 * hub-paired run records only allowed connections to its paired Hub's port.
 */
export async function deviceBoundary({dataDir, scenario, inputs}) {
  const entries = await boundaryEntries(dataDir);
  if (scenario === PAIRED.scenario) {
    const port = pairedPort(inputs?.['hub-feed']);
    if (port === undefined) return {outcome: 'failed', reason: 'hub-paired has no paired Hub port'};
    const other = entries.filter(entry => !isPairedConnect(entry, port));
    return other.length ? {outcome: 'failed', reason: `${other.length} device attempt(s) or connection(s) other than the paired Hub feed recorded since the last seed`} : {outcome: 'passed'};
  }
  if (scenario === 'layout-unavailable') {
    const other = entries.filter(entry => !isLayoutRead(entry));
    if (other.length) return {outcome: 'failed', reason: `${other.length} device attempt(s) other than the map's layout read recorded since the last seed`};
    if (!entries.length) return {outcome: 'failed', reason: 'the startup layout read was not attempted and refused'};
    const problem = layoutReadProblem(entries);
    return problem ? {outcome: 'failed', reason: problem} : {outcome: 'passed'};
  }
  return entries.length ? {outcome: 'failed', reason: `${entries.length} device attempt(s) recorded since the last seed`} : {outcome: 'passed'};
}

const delay = (ms, signal) => new Promise((resolve, reject) => {
  const timer = setTimeout(resolve, ms);
  signal?.addEventListener('abort', () => {clearTimeout(timer); reject(signal.reason)}, {once: true});
});

/** How long after its seed a paired run may have no snapshot yet: the orchestrator configures the Hub after the reseed. */
export const PAIRING_WINDOW_MS = 30000;

/**
 * The paired-feed check, at start and in `doctor`: a hub-paired run's feed is current and the wall
 * applied the revision the Hub serves. It is `skipped` for other scenarios. Until the wall has
 * accepted its first snapshot since the seed it is `skipped` for 30 s after the seed, because the
 * orchestrator configures the Hub to accept the wall's feed credential only after the reseed, and
 * `failed` after that, naming the feed's error: a pairing that never came up. Once the wall has a
 * snapshot, a stale feed or a revision that stays behind the Hub's for about 3 s fails it.
 */
export async function pairedFeed({scenario, url, dataDir, inputs, runtimeDir, signal}) {
  if (scenario !== PAIRED.scenario) return {outcome: 'skipped', reason: `${scenario} is not paired with a Hub`};
  const initial = (await wallState(url, signal)).feed;
  if (initial.revision === null) {
    const cause = initial.error ?? initial.connection;
    // The seed writes demo-run.json last, into a data directory each reseed recreates.
    const seeded = (await stat(join(dataDir, 'demo-run.json'))).mtimeMs;
    return Date.now() - seeded < PAIRING_WINDOW_MS
      ? {outcome: 'skipped', reason: `no snapshot from the paired Hub yet (${cause})`}
      : {outcome: 'failed', reason: `no snapshot from the paired Hub within ${PAIRING_WINDOW_MS / 1000} s of the seed (${cause})`};
  }
  let problem;
  for (let attempt = 0; attempt < 7; attempt++) {
    if (attempt) await delay(500, signal);
    const wall = attempt ? (await wallState(url, signal)).feed : initial;
    if (wall.connection !== 'current') {
      problem = `the wall's paired feed is ${wall.connection}${wall.error ? ` (${wall.error})` : ''}`;
      continue;
    }
    let hub;
    try {
      hub = await readHubFeed({inputs, runtimeDir, signal});
    } catch (error) {
      problem = error.message;
      continue;
    }
    if (hub.ownerId !== PAIRED.owner) problem = `the paired Hub names owner ${JSON.stringify(hub.ownerId)}, not ${PAIRED.owner}`;
    else if (hub.snapshot?.revision !== wall.revision) problem = `the wall applied revision ${wall.revision}; the Hub serves ${hub.snapshot?.revision}`;
    else return {outcome: 'passed'};
  }
  return {outcome: 'failed', reason: problem};
}

/**
 * The cause of a failed demo.py command, read from its stderr: a fixed phrase for its known failures,
 * or the Python exception type alone. It never returns an exception message, which can hold a path.
 */
export function demoCause(stderrTail) {
  const lines = String(stderrTail ?? '').split('\n').map(line => line.trim()).filter(Boolean);
  const last = lines.at(-1) ?? '';
  if (/^OSError: \[Errno 98\] Address already in use$/.test(last)) return 'port already in use';
  if (/^controller_server\.ListenerUnavailable: Port \d{1,5} is already in use\./.test(last)) return 'controller port already in use';
  if (/^controller_server\.ListenerUnavailable: /.test(last)) return 'controller listener unavailable';
  if (/^controller listener stopped(?: \([A-Za-z_][A-Za-z0-9_.]{0,80}\))?$/.test(last)) return 'controller listener stopped';
  const credential = /^demo\.py: error: hub-paired needs a private (hub-feed-token|hub-controller-token) file in the run directory\.$/.exec(last);
  if (credential) return `hub-paired needs a private ${credential[1]} file in the run directory`;
  if (/^demo\.py: error: hub-feed must be the paired Hub run's origin, http:\/\/127\.0\.0\.1:<port>\/\.$/.test(last)) return "hub-feed is not the paired Hub run's origin";
  if (/^demo\.py: error: hub-feed names an installed service's port\.$/.test(last)) return "hub-feed names an installed service's port";
  if (/^FileNotFoundError: \[Errno 2\] No such file or directory: '[^']*\/config\.json'$/.test(last)) return 'the state directory is not seeded (config.json missing)';
  const module = /^ModuleNotFoundError: No module named '([A-Za-z0-9_.]{1,60})'$/.exec(last);
  if (module) return `Python module ${module[1]} is missing`;
  if (/^demo\.py: error: Refusing the state directory: it is the installation's own state\.$/.test(last)) return 'refused the installation state directory';
  if (/^demo\.py: error: Refusing the state directory: it has no demo-run\.json from demo\.py seed\.$/.test(last)) return 'the state directory was not seeded by demo.py';
  if (/^demo\.py(?: [a-z]+)?: error: /.test(last)) return 'demo.py rejected its arguments';
  const type = /^([A-Za-z_][A-Za-z0-9_.]{0,80}(?:Error|Exception|Exit|Interrupt))(?::|$)/.exec(last);
  return type ? type[1] : undefined;
}

/** Name a failed start from the wall server's stderr, for the core's `failure.detail`. */
export function failureCause(stderrTail) {
  const cause = demoCause(stderrTail);
  return cause ? `wall-start-failed: ${cause}` : undefined;
}

/**
 * Run `demo.py seed`. A failure becomes one fixed line, never execFile's message, which names the
 * interpreter, the checkout and the state directory. hub-paired also passes the Hub origin and the
 * runtime directory that holds the credential files; no credential is ever an argument.
 */
export async function seedWith(python, root, {dataDir, scenario, inputs = {}, runtimeDir}, demo = join(root, 'scripts/demo.py')) {
  const paired = scenario === PAIRED.scenario ? ['--hub-feed', inputs['hub-feed'] ?? '', '--credentials', runtimeDir] : [];
  try {
    await run(python, [demo, 'seed', '--state-dir', dataDir, '--scenario', scenario, ...paired], {cwd: root});
  } catch (error) {
    if (error.code === 'ENOENT') throw new Error('demo.py seed failed: the Python interpreter was not found');
    throw new Error(`demo.py seed failed: ${demoCause(error.stderr) ?? `exit status ${Number.isInteger(error.code) ? error.code : 'unknown'}`}`);
  }
}

/**
 * The plug-in for one checkout. `python` must be Python 3.12 or later; a bare name is resolved on
 * the adapter's PATH, because the unit does not inherit the caller's shell. Tests pass their own
 * `app` so their units and run ids never mix with real `wall` runs, and may pass `demo`, another
 * entry point that takes demo.py's arguments, such as the test backstop.
 */
export function createPlugin({root = fileURLToPath(new URL('../..', import.meta.url)), python = process.env.PYTHON || 'python3', app = 'wall', demo = join(root, 'scripts/demo.py')} = {}) {
  const seed = context => seedWith(python, root, context, demo);
  return definePlugin({
    app,
    repository: 'jimmie-potts/codex-nanoleaf',
    command: 'npm run verify --',
    root,
    defaultScenario: 'reference',
    inputs: INPUTS,
    scenarios: Object.fromEntries(Object.entries(SCENARIOS).map(([name, description]) =>
      [name, {description, seed, ...(name === PAIRED.scenario ? {requiredInputs: ['hub-feed']} : {})}])),
    build: {
      version: JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')).version,
      // The page and the three Prism assets it loads; the page is read from disk on every request.
      artifact: {files: ['bridge/wall.html', 'bridge/prism.js', 'bridge/prism-adapters.js', 'bridge/prism-labels.js']},
    },
    // The controller listener starts with hub-paired. Once its endpoint is recorded, every later
    // scenario serves it again on the same port, as the core requires of a relaunch.
    launch: ({dataDir, port, scenario, endpointPorts = {}}) => ({
      argv: [python, '-u', demo, 'serve', '--state-dir', dataDir, '--port', String(port),
        ...(scenario === PAIRED.scenario || endpointPorts.controller !== undefined ? ['--controller-port', String(endpointPorts.controller ?? 0)] : [])],
      env: {PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1'},
      cwd: root,
    }),
    readiness: {line: readyLine, probe, failureCause, timeoutMs: 20000},
    components: [
      {id: 'wall-server', kind: 'actual', note: 'bridge/wall_server.py, started as the installed map starts'},
      {id: 'wall-page', kind: 'actual', note: 'bridge/wall.html with the Prism assets'},
      {id: 'state-store', kind: 'actual', note: 'private SQLite in the run data directory'},
      {id: 'hook-handler', kind: 'actual', note: 'bridge.handle_event applies driven task transitions'},
      {id: 'allocation', kind: 'actual', note: 'bridge.dashboard and project_map allocation, run by the worker stand-in'},
      {id: 'controller-api', kind: 'actual', note: 'bridge/controller_server.py listener, the controller endpoint from hub-paired on'},
      {id: 'shared-input', kind: 'actual', note: 'bridge/shared_source.py Poller and bridge/shared_input.py projection of the paired Hub feed in hub-paired'},
      {id: 'integration-settings', kind: 'actual', note: 'bridge/integration_api.py admission and processing of the Hub\'s integration settings in hub-paired'},
      {id: 'light-worker', kind: 'simulated', note: 'scripts/demo.py worker stand-in applies edits and allocation, and in hub-paired polls the feed and applies integration settings; it never renders or sends'},
      {id: 'lines-device', kind: 'simulated', note: 'tests/fixtures/lines-layout.json at 192.0.2.1; every request is refused by the process boundary'},
      {id: 'panels-device', kind: 'simulated', note: 'tests/fixtures/nl22-panels-fixture.json at 192.0.2.2; every request is refused by the process boundary'},
      {id: 'codex-metadata', kind: 'simulated', note: 'synthetic projects and tasks, or in hub-paired the paired Hub run\'s sessions; no Codex state is read'},
    ],
    // Read-only, so doctor re-runs them against an active run. The core's private HOME is kept: the demo needs no home files.
    checks: [{id: 'device-boundary', run: deviceBoundary, doctor: true}, {id: 'paired-feed', run: pairedFeed, doctor: true}],
    captureSteps: captureSteps({root, python, demo}),
  });
}

export default createPlugin();
