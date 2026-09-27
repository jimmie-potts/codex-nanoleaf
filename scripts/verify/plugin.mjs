// The Nanoleaf wall plug-in for the shared app verification core (#193, Hub #494).
//
// It supplies only what is specific to the wall: the synthetic scenarios, the `scripts/demo.py
// serve` launch of the actual wall server, readiness, the actual and simulated components, the
// device-boundary check and the capture steps. The core owns the run lifecycle.
import {execFile} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';
import {boundaryEntries, captureSteps} from './steps.mjs';

const run = promisify(execFile);
/** Ports of the installed services; a run never answers on one. */
export const INSTALLED_PORTS = new Set([8788, 8765, 8787, 8791, 41230, 41231]);
export const SCENARIOS = {
  reference: 'Lines and Light Panels in Work with five tasks in all four statuses across three projects',
  empty: 'Lines and Light Panels in Work with no tasks, so the wall rests on its remembered scene',
  'layout-unavailable': 'The reference tasks on Lines saved without drawing geometry, so the map asks the device for its layout and the boundary refuses the request',
};
const TITLE = '<title>Nanoleaf · Wall map</title>';

/** Parse the demo's ready line, `{"url": "http://127.0.0.1:<port>", …}`; anything else is not a ready line. */
export function readyLine(line) {
  let value;
  try {
    value = JSON.parse(line);
  } catch {
    return undefined;
  }
  if (typeof value?.url !== 'string') return undefined;
  let url;
  try {
    url = new URL(value.url);
  } catch {
    return undefined;
  }
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.pathname !== '/' || url.search || url.hash) return undefined;
  return {url: url.href};
}

/** The map's own readiness: its receipt, its health route and its page, all naming this process. */
export async function probe({url, port, dataDir, signal}) {
  if (INSTALLED_PORTS.has(port)) return {ok: false, reason: `port ${port} belongs to an installed service`};
  let receipt;
  try {
    receipt = JSON.parse(await readFile(join(dataDir, 'map-server.json'), 'utf8'));
  } catch {
    return {ok: false, reason: 'map-server.json is missing or unreadable'};
  }
  if (receipt.port !== port) return {ok: false, reason: `map-server.json names port ${receipt.port}, not ${port}`};
  if (receipt.boundary !== 'refusing') return {ok: false, reason: 'the served process did not install the device boundary'};
  const health = await fetch(new URL('/health', url), {signal});
  const body = health.ok ? await health.json() : null;
  if (body?.service !== 'codex-nanoleaf-map') return {ok: false, reason: `health answered ${health.status}`};
  if (body.instance !== receipt.instance) return {ok: false, reason: 'health names another map instance'};
  const page = await fetch(url, {signal});
  // The page embeds the per-process edit token; only its title is inspected, and nothing is printed.
  if (!page.ok || !(await page.text()).includes(TITLE)) return {ok: false, reason: `map page answered ${page.status}`};
  return {ok: true};
}

/** The start-time boundary check: every attempt is refused, and only the layout-unavailable scenario makes one. */
export async function deviceBoundary({dataDir, scenario}) {
  const entries = await boundaryEntries(dataDir);
  if (entries.some(entry => entry.outcome !== 'refused')) return {outcome: 'failed', reason: 'a device attempt was not refused'};
  if (scenario === 'layout-unavailable') {
    return entries.some(entry => entry.kind === 'light-request')
      ? {outcome: 'passed'}
      : {outcome: 'failed', reason: 'the startup layout read was not attempted and refused'};
  }
  return entries.length ? {outcome: 'failed', reason: `${entries.length} device attempt(s) during start`} : {outcome: 'passed'};
}

/**
 * The plug-in for one checkout. `python` must be Python 3.12 or later; a bare name is resolved on
 * the adapter's PATH, because the unit does not inherit the caller's shell.
 */
export function createPlugin({root = fileURLToPath(new URL('../..', import.meta.url)), python = process.env.PYTHON || 'python3'} = {}) {
  const demo = join(root, 'scripts/demo.py');
  const seed = async ({dataDir, scenario}) => {
    await run(python, [demo, 'seed', '--state-dir', dataDir, '--scenario', scenario], {cwd: root});
  };
  return {
    app: 'wall',
    repository: 'jimmie-potts/codex-nanoleaf',
    command: 'npm run verify --',
    root,
    defaultScenario: 'reference',
    scenarios: Object.fromEntries(Object.entries(SCENARIOS).map(([name, description]) => [name, {description, seed}])),
    build: {
      version: JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')).version,
      artifact: {file: 'bridge/wall.html'},
    },
    launch: ({dataDir, port}) => ({
      argv: [python, '-u', demo, 'serve', '--state-dir', dataDir, '--port', String(port)],
      env: {PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1'},
      cwd: root,
    }),
    readiness: {line: readyLine, probe, timeoutMs: 20000},
    components: [
      {id: 'wall-server', kind: 'actual', note: 'bridge/wall_server.py, started as the installed map starts'},
      {id: 'wall-page', kind: 'actual', note: 'bridge/wall.html with the Prism assets'},
      {id: 'state-store', kind: 'actual', note: 'private SQLite in the run data directory'},
      {id: 'hook-handler', kind: 'actual', note: 'bridge.handle_event applies driven task transitions'},
      {id: 'allocation', kind: 'actual', note: 'bridge.dashboard and project_map allocation, run by the worker stand-in'},
      {id: 'light-worker', kind: 'simulated', note: 'scripts/demo.py worker stand-in applies edits and allocation; it never renders or sends'},
      {id: 'lines-device', kind: 'simulated', note: 'tests/fixtures/lines-layout.json at 192.0.2.1; every request is refused by the process boundary'},
      {id: 'panels-device', kind: 'simulated', note: 'tests/fixtures/nl22-panels-fixture.json at 192.0.2.2; every request is refused by the process boundary'},
      {id: 'codex-metadata', kind: 'simulated', note: 'synthetic projects and tasks; no Codex state is read'},
    ],
    checks: [{id: 'device-boundary', run: deviceBoundary}],
    captureSteps: captureSteps({root, python}),
  };
}

export default createPlugin();
