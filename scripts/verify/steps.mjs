// Capture steps for the Nanoleaf wall verification adapter (#193).
//
// Each step drives the real wall page of one run and records every expected observation with
// `t.expect`. Observations come from what the page painted and listed, not from screenshots.
// Transitions are applied through the actual hook handler (`scripts/demo.py drive`). Every step
// also asserts that the run recorded no device attempt and that the page contacted only its own
// origin. Every step asserts absolute observations, so each is `fresh`: the core reseeds its
// scenario and relaunches the wall on the same port before the step runs.
//
// Steps named `control-*` are negative controls: a known-wrong transition or presentation that the
// same assertions must reject. Their capture outcome is `failed` at the assertion named in
// NEGATIVE_CONTROLS; a passing control means the assertions cannot see that defect.
import {execFile} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {promisify} from 'node:util';

const run = promisify(execFile);
export const BOUNDARY_LOG = 'device-boundary.jsonl';

/** The run's boundary log: one refused attempt per line. */
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
  const {stdout} = await run(options.python, [join(options.root, 'scripts/demo.py'), 'drive', '--state-dir', t.dataDir, transition],
    {cwd: options.root, signal: t.signal});
  t.note(`drove ${transition}: ${stdout.trim()}`);
}

/**
 * Record what leaves the page and the run for the whole step; `close` asserts that nothing did.
 * Call before the first navigation.
 */
async function watchBoundary(t) {
  const origin = new URL(t.url).origin;
  const foreign = [];
  t.page.on('request', request => {
    const target = new URL(request.url());
    if (target.origin !== origin && !['data:', 'blob:'].includes(target.protocol)) foreign.push(target.origin);
  });
  const before = (await boundaryEntries(t.dataDir)).length;
  return {
    async close({expected = 0} = {}) {
      // End visually settled, so the core's after.png shows the final state rather than a CSS transition.
      await t.page.waitForFunction(() => document.getAnimations().every(item => !(item instanceof CSSTransition) || item.playState !== 'running'),
        null, {timeout: 3000}).catch(() => t.note('CSS transitions were still running at the end of the step'));
      await t.expect('the page contacted only its own run', () => same([...new Set(foreign)], [], 'Requests left the run origin'));
      await t.expect(expected ? 'every device attempt was refused and recorded' : 'no device attempt was recorded', async () => {
        const entries = (await boundaryEntries(t.dataDir)).slice(before);
        check(entries.every(entry => entry.outcome === 'refused'), `An attempt was not refused: ${JSON.stringify(entries)}`);
        if (expected) check(entries.length >= expected, `Expected at least ${expected} refused attempt, saw ${entries.length}`);
        else same(entries.map(entry => `${entry.kind} ${entry.target}`), [], 'Device attempts during the step');
      });
    },
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
  return async t => {
    const boundary = await watchBoundary(t);
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
    await boundary.close();
  };
}

const COMPLETION = {task: 'task-0', from: 'working', to: 'unread', alerts: ['1 blocked', '1 question'],
  alertsName: 'the blocked and question alerts are unchanged', screenshot: 'completed'};
const APPROVAL = {task: 'task-1', from: 'blocked', to: 'working', alerts: ['1 question'],
  alertsName: 'the red alert clears and the question alert stays'};

/** Capture steps, with `python` the interpreter that runs `scripts/demo.py` and `root` the checkout. */
export function captureSteps(options) {
  return {
    'wall-ready': {
      description: 'The Lines wall draws 15 Lines and lists the five reference tasks, their alerts and both devices',
      scenario: 'reference',
      fresh: true,
      run: async t => {
        const boundary = await watchBoundary(t);
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
        await boundary.close();
      },
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
      run: async t => {
        const boundary = await watchBoundary(t);
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
        await boundary.close();
      },
    },
    'lighting-modes': {
      description: 'Work animates the active Lines, Quiet holds them steady, Free releases them, Replay reassembles the wall, and reduced motion holds it still',
      scenario: 'reference',
      fresh: true,
      run: async t => {
        const boundary = await watchBoundary(t);
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
        await boundary.close();
      },
    },
    'panels-view': {
      description: 'Choose Light Panels: tasks sit on triangles in their status colors, and Quiet there leaves the Lines in Work',
      scenario: 'reference',
      fresh: true,
      run: async t => {
        const boundary = await watchBoundary(t);
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
        await boundary.close();
      },
    },
    'device-read-refused': {
      description: 'With no saved drawing geometry the map asks the Lines for their layout; the boundary refuses and records it',
      scenario: 'layout-unavailable',
      fresh: true,
      run: async t => {
        const boundary = await watchBoundary(t);
        await t.page.goto(t.url);
        await t.page.waitForFunction(() => typeof state !== 'undefined' && state !== null, null, {timeout: 10000});
        await t.expect('the map reports the unavailable layout', async () =>
          same(await t.page.locator('#notice').textContent(), 'Layout unavailable. Check the light connection; the map will retry.', 'Notice'));
        await t.expect('the startup layout read was refused and recorded', async () => {
          const entries = await boundaryEntries(t.dataDir);
          same(entries.map(entry => [entry.kind, entry.method, entry.target, entry.outcome]).slice(0, 1),
            [['light-request', 'GET', '192.0.2.1', 'refused']], 'First boundary entry');
        });
        await boundary.close();
      },
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
    'control-stale-red': {
      description: 'Negative control: an approval for another tool leaves task-1 red, which approval-clears-red must reject',
      scenario: 'reference',
      fresh: true,
      run: transition(options, {...APPROVAL, transition: 'defect-approve-other-tool'}),
    },
  };
}

/** Each negative control and the assertion that must fail for it. */
export const NEGATIVE_CONTROLS = {
  'control-stale-completion': 'task-0 reads unread in the task list',
  'control-unread-painted-working': "task-0's Line is painted in the unread color",
  'control-stale-red': 'task-1 reads working in the task list',
};
