// Capture steps for the Nanoleaf wall verification adapter (#193).
//
// Each step drives the real wall page of one run and records every expected observation with
// `t.expect`. Observations come from what the page painted and listed, not from screenshots.
// Transitions are applied through the actual hook handler (`scripts/demo.py drive`). Every step
// also asserts that the page contacted only its own origin and that the run recorded no device
// attempt during the step (device-read-refused accepts only the map's own layout reads), and its
// capture carries that boundary record even when an earlier assertion failed. Every step asserts absolute observations, so each is `fresh`: the core reseeds its
// scenario and relaunches the wall on the same port before the step runs.
//
// Steps named `control-*` are negative controls: a known-wrong transition or presentation that the
// same assertions must reject. Their capture outcome is `failed` at the assertion named in
// NEGATIVE_CONTROLS; a passing control means the assertions cannot see that defect.
//
// hub-paired steps (#194) compare the wall with the paired Hub run's own feed, read with the wall's
// feed credential from the runtime directory, and accept during the step only the wall's
// connections to that Hub's port.
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {constants} from 'node:fs';
import {open, readFile} from 'node:fs/promises';
import {join, relative} from 'node:path';
import {promisify} from 'node:util';

const run = promisify(execFile);
export const BOUNDARY_LOG = 'device-boundary.jsonl';
/** Ports of the installed services; a run never answers on one, and a paired Hub never names one. */
export const INSTALLED_PORTS = new Set([8788, 8765, 8787, 8791, 41230, 41231]);
/**
 * The pairing convention of Hub #495's integrated preview. The credential files hold one
 * 43-character base64url token each and are never printed, recorded or attached.
 */
export const PAIRED = Object.freeze({
  scenario: 'hub-paired', feedToken: 'hub-feed-token', controllerToken: 'hub-controller-token', owner: 'verify-owner', consumer: 'nanoleaf',
  source: Object.freeze({provider: 'codex', client: 'cli', hostId: 'verify-host', sourceId: 'verify-source'}),
});

/** The port of a paired Hub run's origin, exactly `http://127.0.0.1:<port>/` and not an installed service's, or undefined. */
export function pairedPort(hubFeed) {
  const found = typeof hubFeed === 'string' ? /^http:\/\/127\.0\.0\.1:([1-9][0-9]{0,4})\/$/.exec(hubFeed) : null;
  const port = found ? Number(found[1]) : undefined;
  return port !== undefined && port <= 65535 && !INSTALLED_PORTS.has(port) ? port : undefined;
}

/** A connection the paired boundary allowed to the paired Hub's port: the only entry a hub-paired run may record. */
export const isPairedConnect = (entry, port) => port !== undefined && entry.kind === 'socket.connect' && entry.outcome === 'allowed' && entry.target === `127.0.0.1:${port}`;

/**
 * One credential file from the runtime directory, read as the wall reads it: a regular file owned by
 * this user, with no group or other access, never through a symlink, holding one 43-character
 * base64url token. The error never holds the value or a path.
 */
async function pairedToken(runtimeDir, name) {
  const refused = new Error(`hub-paired needs a private ${name} file in the run directory`);
  if (!runtimeDir) throw refused;
  let handle;
  try {
    handle = await open(join(runtimeDir, name), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  } catch {
    throw refused;
  }
  try {
    const info = await handle.stat();
    if (!info.isFile() || info.size > 128 || (info.mode & 0o077) !== 0 || info.uid !== process.getuid()) throw refused;
    const token = (await handle.readFile('utf8')).trim();
    if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw refused;
    return token;
  } finally {
    await handle.close();
  }
}

/** The paired Hub run's monitor feed, as the wall reads it: the same route, credential and header. */
export async function readHubFeed({inputs, runtimeDir, signal}) {
  const port = pairedPort(inputs?.['hub-feed']);
  if (port === undefined) throw new Error('hub-paired has no paired Hub origin');
  const token = await pairedToken(runtimeDir, PAIRED.feedToken);
  let response;
  try {
    response = await fetch(`http://127.0.0.1:${port}/api/monitor/v1/sessions?snapshotVersion=1.2`,
      {headers: {authorization: `Bearer ${token}`, 'x-pixoo-request': '1'}, redirect: 'error', signal});
  } catch {
    throw new Error('the paired Hub feed did not answer');
  }
  if (!response.ok) throw new Error(`the paired Hub feed answered ${response.status}`);
  return response.json();
}

/** The run's own read-only verification route (`GET /verify/state`): feed freshness and applied integration settings. */
export async function wallState(url, signal) {
  const response = await fetch(new URL('verify/state', url), {signal});
  if (!response.ok) throw new Error(`the wall's verification state answered ${response.status}`);
  return response.json();
}

/** The run's boundary log: one refused attempt, or one allowed paired connection, per line. */
export async function boundaryEntries(dataDir) {
  try {
    return (await readFile(join(dataDir, BOUNDARY_LOG), 'utf8')).split('\n').filter(Boolean).map(line => JSON.parse(line));
  } catch (error) {
    if (error.code === 'ENOENT') return [];
    throw error;
  }
}

function check(condition, message) {
  if (!condition) throw new Error(message);
}

/** JSON with object keys sorted, so equal values compare equal whatever their key order. */
function stable(value) {
  return JSON.stringify(value, (key, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(name => [name, item[name]])) : item);
}

function same(actual, expected, message) {
  const [a, e] = [stable(actual), stable(expected)];
  if (a !== e) throw new Error(`${message}: expected ${e}, saw ${a}`);
}

/**
 * The rule for every check: throw or reject on a mismatch, or return `true`. A returned `false` is a
 * mismatch, and any other value, such as a count of 0 meaning "none", is a malformed check. The
 * wrapper keeps a predicate that resolves `false` from being recorded as passed.
 */
export function strict(check) {
  return async () => {
    const value = await check();
    if (value === undefined || value === true) return;
    if (value === false) throw new Error('the observation did not match');
    throw new Error(`the check returned ${JSON.stringify(value) ?? String(value)} instead of throwing on a mismatch or returning true`);
  };
}

/** Give a step a context whose `expect` applies `strict` to every check. */
export function strictChecks(run) {
  return t => run({...t, expect: (name, check) => t.expect(name, strict(check))});
}

/** Wait for any poll in flight, then take one fresh poll and let the page paint it. */
async function settle(page) {
  await page.evaluate(async () => {
    while (refreshing) await new Promise(resolve => setTimeout(resolve, 10));
    await refresh();
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

/** Open the wall, wait for its first state and for the opening assembly to finish. */
async function openWall(t, device) {
  await t.page.goto(device ? `${t.url.replace(/\/$/, '')}/?device=${device}` : t.url);
  await t.page.waitForFunction(() => typeof state !== 'undefined' && state?.lines.length > 0, null, {timeout: 10000});
  if (!device) {
    await t.page.waitForFunction(() => {
      const snapshot = window.wallAssembly?.snapshot();
      return snapshot && snapshot.progress === 1 && !snapshot.playing;
    }, null, {timeout: 15000});
  }
  await settle(t.page);
}

/** The page's view of tasks: status from the task list badge and Line from the state it rendered. */
function tasks(page) {
  return page.evaluate(() => Object.fromEntries(state.tasks.map(task => {
    const badge = document.querySelector(`#taskList .task[data-task="${CSS.escape(task.id)}"] .badge`);
    return [task.id, {listed: badge?.dataset.status ?? null, line: task.line}];
  })));
}

/** Each Line's two painted zone colors, read from the drawn SVG fills. */
function painted(page) {
  return page.evaluate(() => Object.fromEntries(prism.layout.lines.map(line => [line.id, [0, 1].map(zone => {
    const fills = [...document.querySelectorAll(`#wall [data-solid="${line.index}-${zone}"]:not([data-hot-solid])`)]
      .map(node => node.getAttribute('fill').toLowerCase());
    return new Set(fills).size === 1 ? fills[0] : fills.join('|') || null;
  })])));
}

function alerts(page) {
  return page.evaluate(() => [...document.querySelectorAll('#readout [data-alert]')].map(node => node.textContent));
}

function palette(page) {
  return page.evaluate(() => state.palette);
}

/** Apply a named transition through the actual hook handler. */
async function drive(t, options, transition) {
  const {stdout} = await run(options.python, [options.demo ?? join(options.root, 'scripts/demo.py'), 'drive', '--state-dir', t.dataDir, transition],
    {cwd: options.root, signal: t.signal});
  t.note(`drove ${transition}: ${stdout.trim()}`);
}

/** The map's own layout read of the Lines: a GET of the whole layout, the only device attempt a run can expect. */
export const isLayoutRead = entry => entry.kind === 'light-request' && entry.method === 'GET' && entry.target === '192.0.2.1' && entry.endpoint === '';

/**
 * The map reads its layout at most three times: at startup, then twice more, each on the first poll
 * 10 s or more after its previous read. The recorded times trail the map's decisions by the few
 * milliseconds each read takes to start, so consecutive reads must be at least 9.9 s apart.
 */
export const LAYOUT_READS = {most: 3, apartMs: 9900};

/** Why a run's layout reads exceed the map's bound, or null when they stay within it. */
export function layoutReadProblem(entries) {
  const reads = entries.filter(isLayoutRead);
  if (reads.length > LAYOUT_READS.most) return `${reads.length} layout reads, more than the map's ${LAYOUT_READS.most}`;
  for (let index = 1; index < reads.length; index++) {
    const apart = Date.parse(reads[index].at) - Date.parse(reads[index - 1].at);
    if (!(apart >= LAYOUT_READS.apartMs)) return `layout read ${index + 1} came ${apart} ms after the previous one`;
  }
  return null;
}

/** What a step accepts from the boundary log: no entry at all unless a policy names what it tolerates. */
const NOTHING = {name: 'no device attempt was recorded during the step'};
const LAYOUT_READS_ONLY = {name: "the only device attempts during the step are the map's bounded layout reads", tolerate: () => isLayoutRead,
  label: 'Other device attempts during the step', since: entries => same(layoutReadProblem(entries), null, 'Layout reads since the seed')};
const PAIRED_FEED_ONLY = {name: 'only the paired Hub feed was contacted during the step', label: 'Device attempts or other connections during the step',
  tolerate: t => {
    const port = pairedPort(t.inputs?.['hub-feed']);
    return entry => isPairedConnect(entry, port);
  }};

/**
 * Record what leaves the page and the run during a step. `close` asserts that nothing did, apart
 * from the log entries the policy tolerates; `attach` writes the step's boundary record into its capture.
 */
async function watchBoundary(t, policy = NOTHING) {
  const origin = new URL(t.url).origin;
  const foreign = [];
  t.page.on('request', request => {
    const target = new URL(request.url());
    if (target.origin !== origin && !['data:', 'blob:'].includes(target.protocol)) foreign.push(target.origin);
  });
  const before = (await boundaryEntries(t.dataDir)).length;
  const during = async () => (await boundaryEntries(t.dataDir)).slice(before);
  const describe = entry => [entry.kind, entry.method, entry.target, entry.outcome === 'allowed' ? 'allowed' : undefined].filter(Boolean).join(' ');
  return {
    async close() {
      // End visually settled, so the core's after.png shows the final state rather than a CSS transition.
      await t.page.waitForFunction(() => document.getAnimations().every(item => !(item instanceof CSSTransition) || item.playState !== 'running'),
        null, {timeout: 3000}).catch(() => t.note('CSS transitions were still running at the end of the step'));
      await t.expect('the page contacted only its own run', () => same([...new Set(foreign)], [], 'Requests left the run origin'));
      const entries = await during();
      const tolerated = policy.tolerate?.(t) ?? (() => false);
      await t.expect(policy.name, async () => {
        same(entries.filter(entry => !tolerated(entry)).map(describe), [], policy.label ?? 'Device attempts during the step');
        if (policy.since) policy.since(await boundaryEntries(t.dataDir));
      });
    },
    async attach() {
      await t.attach('device-boundary.json', `${JSON.stringify({recordedBeforeStep: before, duringStep: await during()}, null, 2)}\n`);
    },
  };
}

/**
 * A step between the boundary watch and its closing assertions. The step's boundary record goes
 * into its capture even when an earlier assertion failed.
 */
function bounded(run, policy) {
  return async t => {
    const boundary = await watchBoundary(t, policy);
    try {
      await run(t);
      await boundary.close();
    } finally {
      await boundary.attach().catch(error => t.note(`the boundary record was not attached: ${error.message}`));
    }
  };
}

/** Serve the page with one exact source replacement, a presentation defect the assertions must catch. */
async function injectPageDefect(t, target, replacement) {
  let applied = 0;
  await t.page.route(url => url.pathname === '/', async route => {
    const response = await route.fetch();
    const body = await response.text();
    applied = body.split(target).length - 1;
    await route.fulfill({response, body: body.replace(target, replacement)});
  });
  return () => t.expect('the presentation defect is injected exactly once', () => same(applied, 1, 'Mutation sites'));
}

const REFERENCE_TASKS = {
  'task-0': 'working', 'task-1': 'blocked', 'task-2': 'question', 'task-3': 'unread', 'task-4': 'working',
};
// A presentation defect: unread Lines keep the working color, so a completion never shows on the wall.
const UNREAD_PAINTED_WORKING = [
  "const status=task?.status||'base',",
  "const status=(task?.status==='unread'?'working':task?.status)||'base',",
];

/**
 * One driven task transition: the task moves from `from` to `to` on the same Line, its Line is
 * repainted in the new status color, no other Line changes and the alerts read `alerts` afterwards.
 */
function transition(options, {transition: name, task, from, to, alerts: expected, alertsName, pageDefect, screenshot}) {
  return bounded(async t => {
    const confirmDefect = pageDefect ? await injectPageDefect(t, ...pageDefect) : null;
    await openWall(t);
    if (confirmDefect) await confirmDefect();
    const before = await tasks(t.page), beforePaint = await painted(t.page);
    const line = before[task]?.line;
    await t.expect(`${task} starts ${from} on a Line`, () => {
      same(before[task]?.listed, from, `${task} status`);
      check(line, `${task} has no Line`);
    });
    await drive(t, options, name);
    await settle(t.page);
    const after = await tasks(t.page), afterPaint = await painted(t.page), colors = await palette(t.page);
    await t.expect(`${task} reads ${to} in the task list`, () => same(after[task].listed, to, `${task} status`));
    await t.expect(`${task} keeps its Line`, () => same(after[task].line, line, `${task} Line`));
    await t.expect(`${task}'s Line is painted in the ${to} color`, () => same(afterPaint[line], [colors[to], colors[to]], 'Painted zones'));
    await t.expect('every other Line keeps its colors', () => {
      const changed = Object.keys(afterPaint).filter(id => id !== line && JSON.stringify(afterPaint[id]) !== JSON.stringify(beforePaint[id]));
      same(changed, [], 'Lines that changed');
    });
    await t.expect(alertsName, async () => same(await alerts(t.page), expected, 'Alerts'));
    if (screenshot) await t.screenshot(screenshot);
  });
}

/** The wall's task key for a shared session: `shared-` and the SHA-256 of its identity fields, as bridge/shared_input.py keys it. */
export function sessionKey(identity) {
  const fields = ['provider', 'client', 'hostId', 'sourceId', 'sessionId'].map(name => identity[name]);
  return 'shared-' + createHash('sha256').update(JSON.stringify(fields)).digest('hex');
}

const fromPairedSource = session => Object.entries(PAIRED.source).every(([name, value]) => session.identity[name] === value);
const sameIdentity = (a, b) => ['provider', 'client', 'hostId', 'sourceId', 'sessionId'].every(name => a[name] === b[name]);

/**
 * What the wall must show for the Hub's snapshot, written from docs/shared-input.md rather than
 * from the wall's code: each top-level session from the paired source is one task. A direct
 * subagent's attention and the owner's count of fresh active subagents raise it; a turn-ended
 * notice this consumer has not acknowledged makes an otherwise idle task unread. Its title is the
 * Hub's label, then its title. Its evidence is current when the collector runs and the session is
 * current. Deeper subagent chains and orphans (a known parent missing from the snapshot, which the
 * wall shows only for its alerts) are not modelled; the integrated preview's Hub seeds neither.
 */
export function pairedExpectations(snapshot) {
  const sessions = snapshot.sessions.filter(fromPairedSource);
  return Object.fromEntries(sessions.filter(session => session.parent.status !== 'known').map(session => {
    const children = sessions.filter(child => child.parent.status === 'known' && sameIdentity(child.parent.identity, session.identity));
    const kinds = new Set([session, ...children].flatMap(item => item.attention.map(attention => attention.kind)));
    const status = kinds.has('approval') || kinds.has('input') ? 'blocked' : kinds.has('question') ? 'question'
      : session.activity === 'active' || session.children.active > 0 ? 'working'
        : session.read !== 'read' && session.notices.some(notice => !notice.acknowledgedBy.includes(PAIRED.consumer)) ? 'unread' : 'idle';
    const evidence = snapshot.collector === 'running' && session.freshness === 'current' ? 'current' : 'uncertain';
    return [sessionKey(session.identity), {status, title: session.label ?? session.title?.value ?? null, evidence}];
  }));
}

/**
 * Wait until the wall's feed is current at the revision the Hub serves; return the Hub's envelope at
 * that revision. A failed read of either side is retried within the window, which ends with the last reason.
 */
async function pairedSnapshot(t) {
  let seen = 'no read yet';
  for (let waited = 0; waited < 15000; waited += 250) {
    try {
      const [wall, hub] = [(await wallState(t.url, t.signal)).feed, await readHubFeed(t)];
      if (wall.connection === 'current' && wall.revision === hub.snapshot.revision) return hub;
      seen = `the wall is ${wall.connection}${wall.error ? ` (${wall.error})` : ''} at revision ${wall.revision}; the Hub serves ${hub.snapshot.revision}`;
    } catch (error) {
      seen = error.message;
    }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`The wall did not reach the Hub's revision: ${seen}`);
}

/**
 * The Hub's lifecycle state painted on the wall. `transition` first drives one of the paired
 * run's known-wrong writers, for a negative control.
 */
function pairedLifecycle(options, {transition} = {}) {
  return bounded(async t => {
    if (transition) await drive(t, options, transition);
    const hub = await pairedSnapshot(t);
    const expected = pairedExpectations(hub.snapshot);
    await t.expect('the paired Hub serves at least one session from the paired source', () => check(Object.keys(expected).length > 0, 'No session from the paired source'));
    await openWall(t);
    const [listed, paint, colors] = [await t.page.evaluate(() => Object.fromEntries(state.tasks.map(task => [task.id, {
      listed: document.querySelector(`#taskList .task[data-task="${CSS.escape(task.id)}"] .badge`)?.dataset.status ?? null,
      title: task.title, line: task.line, evidence: task.statusEvidence ?? null,
    }]))), await painted(t.page), await palette(t.page)];
    await t.expect('each Hub-fed task is placed on a Line', () =>
      same(Object.keys(expected).filter(id => !listed[id]?.line), [], 'Hub-fed tasks without a Line'));
    await t.expect('the task list shows each Hub session with its lifecycle status', () =>
      same(Object.fromEntries(Object.entries(listed).map(([id, task]) => [id, task.listed])),
        Object.fromEntries(Object.entries(expected).map(([id, task]) => [id, task.status])), 'Listed statuses'));
    await t.expect("each Hub-fed task shows the Hub's label or title", () => {
      for (const [id, task] of Object.entries(expected)) if (task.title !== null) same(listed[id]?.title, task.title, `${id} title`);
    });
    await t.expect('each Hub-fed task reports the evidence the Hub gives', () =>
      same(Object.fromEntries(Object.entries(listed).map(([id, task]) => [id, task.evidence])),
        Object.fromEntries(Object.entries(expected).map(([id, task]) => [id, task.evidence])), 'Status evidence'));
    await t.expect("each Hub-fed task paints its Line in its status's color", () => {
      for (const id of Object.keys(expected)) {
        const task = listed[id];
        const color = colors[task.listed === 'idle' ? 'base' : task.listed];
        same(paint[task.line], [color, color], `${id} Line`);
      }
    });
    await t.expect('the B.U.N.N.Y. link leads to the paired Hub run', async () => {
      const links = await t.page.locator('a.hub-link').evaluateAll(nodes => nodes.map(node => [node.textContent, node.getAttribute('href'), node.getAttribute('target')]));
      same(links, [['B.U.N.N.Y.', t.inputs['hub-feed'], '_blank']], 'Header Hub link');
    });
    await t.expect("the wall stayed current at the Hub's revision", async () => {
      const [wall, now] = [(await wallState(t.url, t.signal)).feed, await readHubFeed(t)];
      same({source: wall.source, connection: wall.connection, ownerId: wall.ownerId, revision: wall.revision, hub: now.snapshot.revision},
        {source: 'shared', connection: 'current', ownerId: PAIRED.owner, revision: hub.snapshot.revision, hub: hub.snapshot.revision}, 'Paired feed');
    });
    await t.screenshot('hub-fed');
  }, PAIRED_FEED_ONLY);
}

const COMPLETION = {task: 'task-0', from: 'working', to: 'unread', alerts: ['1 blocked', '1 question'],
  alertsName: 'the blocked and question alerts are unchanged', screenshot: 'completed'};
const APPROVAL = {task: 'task-1', from: 'blocked', to: 'working', alerts: ['1 question'],
  alertsName: 'the red alert clears and the question alert stays'};

/** Apply `strictChecks` to every step of a step map. */
export function strictSteps(steps) {
  return Object.fromEntries(Object.entries(steps).map(([name, step]) => [name, {...step, run: strictChecks(step.run)}]));
}

/**
 * Capture steps, with `python` the interpreter that runs the demo, `root` the checkout and `demo` the
 * entry point that seeds, serves and drives it. Each capture's log names that entry, so a capture
 * made beneath the test backstop says so.
 */
export function captureSteps(options) {
  const entry = relative(options.root, options.demo ?? join(options.root, 'scripts/demo.py'));
  return Object.fromEntries(Object.entries(strictSteps(definitions(options))).map(([name, step]) =>
    [name, {...step, run: t => {
      t.note(`demo entry: ${entry}`);
      return step.run(t);
    }}]));
}

function definitions(options) {
  return {
    'wall-ready': {
      description: 'The Lines wall draws 15 Lines and lists the five reference tasks, their alerts and both devices',
      scenario: 'reference',
      fresh: true,
      run: bounded(async t => {
        await openWall(t);
        await t.expect('the wall draws 15 Lines', async () => same(await t.page.locator('.wall-line').count(), 15, 'Lines'));
        await t.expect('the task list shows each reference task with its status', async () => {
          const listed = Object.fromEntries(Object.entries(await tasks(t.page)).map(([id, task]) => [id, task.listed]));
          same(listed, REFERENCE_TASKS, 'Listed statuses');
        });
        await t.expect('the readout reports one blocked and one question alert', async () => same(await alerts(t.page), ['1 blocked', '1 question'], 'Alerts'));
        await t.expect('the Device control offers Lines and Light Panels', async () =>
          same(await t.page.locator('#device option').evaluateAll(nodes => nodes.map(node => [node.value, node.textContent])),
            [['wall', 'Lines'], ['panels', 'Light Panels']], 'Devices'));
        await t.expect('each placed task paints its Line in its status color', async () => {
          const [listed, paint, colors] = [await tasks(t.page), await painted(t.page), await palette(t.page)];
          for (const [id, task] of Object.entries(listed)) {
            if (task.line) same(paint[task.line], [colors[task.listed], colors[task.listed]], `${id} Line`);
          }
        });
      }),
    },
    'task-completes': {
      description: 'task-0 finishes its turn through the hook handler; its Line turns unread and keeps its place',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {...COMPLETION, transition: 'complete'}),
    },
    'approval-clears-red': {
      description: 'task-1 receives its shell approval; the red alert clears and its Line turns working',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {...APPROVAL, transition: 'approve'}),
    },
    'approval-requested': {
      description: 'task-4 asks for a shell approval; its Line turns blocked and a second red alert appears',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {transition: 'request-approval', task: 'task-4', from: 'working', to: 'blocked',
        alerts: ['2 blocked', '1 question'], alertsName: 'a second red alert appears'}),
    },
    'task-resumes': {
      description: 'task-3 starts a new turn; its unread Line turns working and the alerts stay',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {transition: 'resume', task: 'task-3', from: 'unread', to: 'working',
        alerts: ['1 blocked', '1 question'], alertsName: 'the blocked and question alerts are unchanged'}),
    },
    'project-layout': {
      description: 'Switch to Project layout and reserve two free Lines for Notification Service from the page',
      scenario: 'reference',
      fresh: true,
      run: bounded(async t => {
        await openWall(t);
        const free = await t.page.evaluate(() => state.lines.filter(line => !line.task).slice(0, 2).map(line => line.id));
        await t.expect('two Lines are free to reserve', () => same(free.length, 2, 'Free Lines'));
        await t.page.locator('#wallOptions > summary').click();
        await t.page.locator('#project').click();
        await t.page.waitForFunction(() => state.settings.style === 'project');
        await t.page.locator('#wallOptions > summary').click();
        await t.page.locator(`[data-line="${free[0]}"]`).first().click();
        await t.page.locator(`[data-line="${free[1]}"]`).first().click({modifiers: ['Control']});
        await t.page.locator('#assignProject').selectOption('a');
        await t.page.waitForFunction(ids => ids.every(id => state.lines.find(line => line.id === id)?.project === 'a'), free, {timeout: 5000}).catch(() => {});
        await settle(t.page);
        const seen = await t.page.evaluate(() => ({style: state.settings.style, pending: state.pending,
          lines: state.lines.map(line => ({id: line.id, project: line.project, signature: line.signature}))}));
        await t.expect('the layout is Project', async () => {
          same(seen.style, 'project', 'Style');
          same(await t.page.locator('#project').getAttribute('aria-pressed'), 'true', 'Project pressed');
        });
        await t.expect('both Lines are reserved for Notification Service', () =>
          same(seen.lines.filter(line => free.includes(line.id)).map(line => line.project), ['a', 'a'], 'Reservations'));
        await t.expect('the edit was applied, not left pending', () => same(seen.pending, null, 'Pending edit'));
        await t.expect("each reserved Line paints its project half in the project's color", async () => {
          const paint = await painted(t.page);
          for (const line of seen.lines.filter(item => free.includes(item.id))) same(paint[line.id][line.signature], '#ad8dff', `${line.id} project half`);
        });
      }),
    },
    'lighting-modes': {
      description: 'Work animates the active Lines, Quiet holds them steady, Free releases them, Replay reassembles the wall, and reduced motion holds it still',
      scenario: 'reference',
      fresh: true,
      run: bounded(async t => {
        // The capture context prefers reduced motion; this step checks the animation itself, so it opts out first.
        await t.page.emulateMedia({reducedMotion: 'no-preference'});
        await openWall(t);
        const phaseMoves = async () => {
          const first = await t.page.evaluate(() => wallAssembly.snapshot().lightPhase);
          await t.page.waitForTimeout(400);
          return first !== await t.page.evaluate(() => wallAssembly.snapshot().lightPhase);
        };
        const mode = async name => {
          await t.page.locator(`#${name}`).click();
          await t.page.waitForFunction(value => state.mode === value && document.body.dataset.mode === value, name, {timeout: 5000});
          await settle(t.page);
        };
        await t.expect('Work animates every Line with an active task', async () => {
          const snapshot = await t.page.evaluate(() => ({mode: wallAssembly.snapshot().mode, activity: wallAssembly.snapshot().activity.length,
            active: state.lines.filter(line => state.tasks.some(task => task.id === line.task && task.status !== 'idle')).length}));
          same([snapshot.mode, snapshot.activity], ['work', snapshot.active], 'Mode and active Lines');
          check(snapshot.active > 0, 'No active Lines');
          check(await phaseMoves(), 'The light phase did not advance in Work');
        });
        await mode('quiet');
        await t.expect('Quiet holds steady colors', async () => {
          same(await t.page.evaluate(() => wallAssembly.snapshot().mode), 'quiet', 'Renderer mode');
          check(!await phaseMoves(), 'The light phase advanced in Quiet');
        });
        await mode('free');
        await t.expect('Free releases the lights and disables Locate', async () => {
          same(await t.page.locator('#wallNote').textContent(), 'Free · lights released', 'Mode note');
          same(await t.page.locator('#locate').isDisabled(), true, 'Locate disabled');
        });
        await mode('work');
        await t.expect('Work resumes the animation', async () => check(await phaseMoves(), 'The light phase did not resume'));
        await t.page.locator('#wallOptions > summary').click();
        await t.page.locator('#replay').click();
        await t.expect('Replay reassembles the wall and finishes', async () => {
          await t.page.waitForFunction(() => wallAssembly.snapshot().playing, null, {timeout: 3000});
          await t.page.waitForFunction(() => wallAssembly.snapshot().progress === 1 && !wallAssembly.snapshot().playing, null, {timeout: 15000});
        });
        await t.page.emulateMedia({reducedMotion: 'reduce'});
        await t.page.locator('#replay').click();
        await t.expect('Reduced motion holds Work steady and skips the Replay animation', async () => {
          check(!await phaseMoves(), 'The light phase advanced with reduced motion');
          const samples = [];
          for (let i = 0; i < 5; i++) {
            samples.push(await t.page.evaluate(() => {
              const snapshot = wallAssembly.snapshot();
              return {playing: snapshot.playing, progress: snapshot.progress, reduced: snapshot.reducedMotion};
            }));
            await t.page.waitForTimeout(60);
          }
          same([...new Set(samples.map(sample => JSON.stringify(sample)))], [JSON.stringify({playing: false, progress: 1, reduced: true})], 'Replay with reduced motion');
        });
        await t.page.locator('#wallOptions > summary').click();
        await t.expect('the Light Panels keep their own mode', async () =>
          same(await t.page.evaluate(async () => (await (await fetch('/api/state?device=panels')).json()).mode), 'work', 'Panels mode'));
      }),
    },
    'panels-view': {
      description: 'Choose Light Panels: tasks sit on triangles in their status colors, and Quiet there leaves the Lines in Work',
      scenario: 'reference',
      fresh: true,
      run: bounded(async t => {
        await openWall(t);
        await t.page.locator('#device').selectOption('panels');
        await t.page.waitForFunction(() => state.kind === 'panels' && document.querySelectorAll('.wall-triangle').length > 0, null, {timeout: 5000});
        await settle(t.page);
        await t.expect('every Light Panels triangle is drawn', async () => {
          const [drawn, lines] = await t.page.evaluate(() => [document.querySelectorAll('.wall-triangle').length, state.lines.length]);
          check(lines > 0, 'No triangles in the state');
          same(drawn, lines, 'Triangles');
        });
        await t.expect('each placed task colors its triangle by status', async () => {
          const placed = await t.page.evaluate(() => state.tasks.filter(task => task.line).map(task => {
            const group = document.querySelector(`.wall-triangle[data-line="${CSS.escape(task.line)}"]`);
            const probe = document.createElement('i');
            probe.style.color = `var(--wall-${task.status})`;
            document.body.append(probe);
            const expected = getComputedStyle(probe).color;
            probe.remove();
            return {id: task.id, status: group?.dataset.status, fill: group && getComputedStyle(group.querySelector('.tri-face')).fill, expected, want: task.status};
          }));
          check(placed.length > 0, 'No task is placed on a triangle');
          for (const task of placed) same([task.status, task.fill], [task.want, task.expected], `${task.id} triangle`);
        });
        await t.page.locator('#quiet').click();
        await t.page.waitForFunction(() => state.mode === 'quiet', null, {timeout: 5000});
        await t.expect('Quiet on the Light Panels leaves the Lines in Work', async () => {
          same(await t.page.evaluate(() => state.mode), 'quiet', 'Panels mode');
          same(await t.page.evaluate(async () => (await (await fetch('/api/state')).json()).mode), 'work', 'Lines mode');
        });
      }),
    },
    'device-read-refused': {
      description: 'With no saved drawing geometry the map asks the Lines for their layout; the boundary refuses and records it',
      scenario: 'layout-unavailable',
      fresh: true,
      run: bounded(async t => {
        await t.page.goto(t.url);
        await t.page.waitForFunction(() => typeof state !== 'undefined' && state !== null, null, {timeout: 10000});
        await t.expect('the map reports the unavailable layout', async () =>
          same(await t.page.locator('#notice').textContent(), 'Layout unavailable. Check the light connection; the map will retry.', 'Notice'));
        await t.expect('the startup layout read was refused and recorded', async () => {
          const entries = await boundaryEntries(t.dataDir);
          same(entries.map(entry => [entry.kind, entry.method, entry.target, entry.outcome]).slice(0, 1),
            [['light-request', 'GET', '192.0.2.1', 'refused']], 'First boundary entry');
        });
      }, LAYOUT_READS_ONLY),
    },
    'hub-lifecycle-painted': {
      description: "The wall follows the paired Hub run's feed: each session from the paired source is listed with its lifecycle status and paints its Line in that status's color",
      scenario: 'hub-paired',
      fresh: true,
      run: pairedLifecycle(options),
    },
    'control-stale-completion': {
      description: 'Negative control: a Stop for an earlier turn leaves task-0 working, which task-completes must reject',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {...COMPLETION, transition: 'defect-complete-stale-turn'}),
    },
    'control-unread-painted-working': {
      description: 'Negative control: a page that paints unread Lines in the working color, which task-completes must reject',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {...COMPLETION, transition: 'complete', pageDefect: UNREAD_PAINTED_WORKING}),
    },
    'control-device-attempt': {
      description: 'Negative control: a completion whose worker stand-in also tries to send the effect to each device, which task-completes must reject',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {...COMPLETION, transition: 'defect-complete-contacts-device'}),
    },
    'control-stale-red': {
      description: 'Negative control: an approval for another tool leaves task-1 red, which approval-clears-red must reject',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {...APPROVAL, transition: 'defect-approve-other-tool'}),
    },
    'control-paired-installed-port': {
      description: "Negative control: the paired stand-in polls the installed Hub's port, which the boundary refuses and hub-lifecycle-painted must reject",
      scenario: 'hub-paired',
      fresh: true,
      run: pairedLifecycle(options, {transition: 'defect-poll-installed-hub'}),
    },
    'control-paired-light-request': {
      description: 'Negative control: the paired stand-in also tries to send the effect to each device, which the boundary refuses and hub-lifecycle-painted must reject',
      scenario: 'hub-paired',
      fresh: true,
      run: pairedLifecycle(options, {transition: 'defect-paired-light-request'}),
    },
  };
}

/** Each negative control and the assertion that must fail for it. */
export const NEGATIVE_CONTROLS = {
  'control-stale-completion': 'task-0 reads unread in the task list',
  'control-unread-painted-working': "task-0's Line is painted in the unread color",
  'control-stale-red': 'task-1 reads working in the task list',
  'control-device-attempt': 'no device attempt was recorded during the step',
  'control-paired-installed-port': 'only the paired Hub feed was contacted during the step',
  'control-paired-light-request': 'only the paired Hub feed was contacted during the step',
};
