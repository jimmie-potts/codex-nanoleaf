const assert = require('node:assert/strict');
const options = require('./wall_options.cjs');

/*
 * Prism presentation acceptance contract.
 *
 * Required live selectors:
 *   #wall.prism-scene
 *   .wall-line[data-line][data-line-id][role="button"]
 *   [data-edge][data-line-id] [data-packet][data-zone], [data-spark]
 *   [data-bed], [data-spill], .selection-ring, .highlight-ring,
 *   .pending-ring, .number-tag[data-line-id]
 *
 * Required public bridge:
 *   window.wallAssembly.snapshot() -> Prism.Renderer.snapshot()
 * The snapshot is used for the shared flow clock, activity, mode, reduced
 * motion, and pause reasons. Visible SVG attributes, computed styles,
 * accessibility, request traffic, and the app readout remain the assertions.
 */
module.exports = async function(page, root) {
  const failures = [];
  const check = async (name, fn) => {
    try { await fn(); }
    catch (error) { failures.push(`${name} -> ${error.message.split('\n')[0]}`); }
  };
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const refresh = () => page.evaluate(async () => {
    while (refreshing) await new Promise(resolve => setTimeout(resolve, 10));
    await refresh();
  });
  const snapshot = () => page.evaluate(() => {
    if (typeof window.wallAssembly?.snapshot !== 'function') throw Error('window.wallAssembly.snapshot() is required');
    return window.wallAssembly.snapshot();
  });
  const setMode = async mode => {
    await page.evaluate(value => action('/api/mode', {mode: value}), mode);
    await page.waitForFunction(value => state.mode === value && document.body.dataset.mode === value, mode);
    await settle();
  };
  const waitForPhase = async (min, max, lineId = null) => {
    const handle = await page.waitForFunction(([low, high, id]) => {
      const value = window.wallAssembly?.snapshot?.().lightPhase;
      if (!Number.isFinite(value) || value < low || value > high) return false;
      // Capture the painted attributes in the same browser turn as the phase.
      // A second browser call can arrive several frames later on a slow runner.
      const edge = id === null ? null : document.querySelector(`#wall [data-edge][data-line-id="${id}"]`);
      return {
        phase: value,
        packets: edge ? [...edge.querySelectorAll('[data-part="zone-core"] [data-packet]')].map(node => ({
          zone: +node.dataset.zone,
          x: +(/translate\(([-\d.]+)/.exec(node.getAttribute('transform')) || [0, NaN])[1],
          opacity: +getComputedStyle(node).opacity,
        })) : [],
        spark: edge ? +getComputedStyle(edge.querySelector('[data-spark]')).opacity : 0,
      };
    }, [min, max, lineId], {timeout: 10000});
    try { return await handle.jsonValue(); }
    finally { await handle.dispose(); }
  };
  const circularError = (actual, expected) => {
    const raw = Math.abs(actual - expected) % 1;
    return Math.min(raw, 1 - raw);
  };
  const phaseAcross = async (label, action) => {
    await waitForPhase(.22, .58);
    const before = await page.evaluate(() => {prism.light(performance.now());return {phase: wallAssembly.snapshot().lightPhase, now: performance.now()}});
    await action();
    await page.waitForTimeout(140);
    const after = await page.evaluate(() => {prism.light(performance.now());return {phase: wallAssembly.snapshot().lightPhase, now: performance.now()}});
    const expected = (before.phase + (after.now - before.now) / 2000) % 1;
    assert.ok(circularError(after.phase, expected) <= .025,
      `${label} preserves the shared 2 s flow clock (expected ${expected.toFixed(3)}, got ${after.phase.toFixed(3)})`);
  };
  const wallMotion = () => page.evaluate(() => {
    const s = wallAssembly.snapshot();
    return {
      snapshot: s,
      packets: [...document.querySelectorAll('#wall [data-packet]')].filter(node => +getComputedStyle(node).opacity > .02).length,
      sparks: [...document.querySelectorAll('#wall [data-spark]')].filter(node => +getComputedStyle(node).opacity > .02).length,
      activeAnimations: document.getElementById('wall').getAnimations({subtree: true}).filter(animation => animation.playState === 'running').length,
    };
  });
  const replay = async () => {await options.open(page); await page.locator('#replay').click(); await options.close(page)};
  const firstBedOpacity = () => page.evaluate(() => {
    const edge = document.querySelector('#wall [data-edge]');
    return Math.max(...[...edge.querySelectorAll('[data-bed]')].map(node => +getComputedStyle(node).opacity));
  });

  await page.setViewportSize({width: 1440, height: 1000});
  await page.locator('#wall').scrollIntoViewIfNeeded();
  try {
    await page.waitForFunction(() => window.wallAssembly?.snapshot?.().pauseReasons.length === 0);
  } catch (error) {
    const visibleState = await page.evaluate(() => ({
      pauseReasons: window.wallAssembly?.snapshot?.().pauseReasons,
      documentVisibility: document.visibilityState,
      host: document.getElementById('wallHost').getBoundingClientRect().toJSON(),
    }));
    throw Error(`Visible wall did not resume: ${JSON.stringify(visibleState)}`, {cause: error});
  }

  await check('Prism integration is visible and exposes the accepted snapshot bridge', async () => {
    assert.equal(await page.locator('#wall.prism-scene').count(), 1, 'The live wall is the Prism scene');
    const contract = await snapshot();
    assert.equal(contract.progress, 1, 'Presentation checks begin after assembly');
    assert.equal(contract.lines, await page.locator('#wall .wall-line[data-line]').count(), 'Snapshot and interactive Line count agree');
    assert.ok(contract.activity.length > 0, 'Fixture includes at least one task-active Line');
    assert.equal(await page.locator('#wall [data-packet]').count(), contract.lines * 8, 'Each Line has four material copies for each of two zone packets');
    assert.equal(await page.locator('#wall [data-part="zone-core"] [data-packet]').count(), contract.lines * 2, 'Each Line has exactly two visible core packet paths');
    assert.equal(await page.locator('#wall [data-spark]').count(), contract.lines, 'Each Line has one connector-center spark');
  });

  await setMode('work');

  await check('Work sends two colored packets inward and meets at the center every two seconds', async () => {
    const activeId = (await snapshot()).activity[0];
    const edge = `#wall [data-edge][data-line-id="${activeId}"]`;
    const early = (await waitForPhase(.08, .16, activeId)).packets;
    const late = (await waitForPhase(.42, .50, activeId)).packets;
    assert.deepEqual(early.map(item => item.zone), [0, 1], 'Packets preserve physical zone order');
    assert.ok(early.every(item => item.opacity > .8) && late.every(item => item.opacity > .8), 'Both zone packets are visibly traveling');
    assert.ok(early[0].x < late[0].x && early[0].x < 0, 'Zone 0 travels from its connector toward the center');
    assert.ok(early[1].x > late[1].x && early[1].x > 0, 'Zone 1 travels from its connector toward the center');
    const copies = await page.locator(edge).evaluate(node => [0, 1].map(zone => {
      const core = node.querySelector(`[data-part="zone-core"] [data-packet][data-zone="${zone}"]`);
      return ['wide-spill', 'near-spill', 'refracted-core'].map(part => {
        const copy = node.querySelector(`[data-part="${part}"] [data-packet][data-zone="${zone}"]`);
        return {part, exists: !!copy, transform: copy?.getAttribute('transform'), core: core?.getAttribute('transform')};
      });
    }));
    assert.ok(copies.flat().every(copy => copy.exists && copy.transform === copy.core),
      `Spill and refracted packet copies track their corresponding zone core (${JSON.stringify(copies)})`);
    const fills = await page.locator(edge).evaluate(node => [0, 1].map(zone => {
      const solid = node.querySelector(`[data-part="zone-core"] [data-solid$="-${zone}"]:not([data-hot-solid])`);
      return getComputedStyle(solid).fill;
    }));
    assert.equal(fills.length, 2, 'The tube exposes two independently paintable halves');
    assert.ok((await waitForPhase(.64, .70, activeId)).spark > .02,
      'A visible spark marks the inward packets meeting at the center');
    const idleId = await page.evaluate(id => wallAssembly.snapshot().activity.includes(id)
      ? [...document.querySelectorAll('#wall [data-edge]')].map(node => node.dataset.lineId).find(value => !wallAssembly.snapshot().activity.includes(value))
      : id, activeId);
    if (idleId) {
      assert.ok(await page.locator(`#wall [data-edge][data-line-id="${idleId}"] [data-packet]`).evaluateAll(nodes => nodes.every(node => +getComputedStyle(node).opacity === 0)),
        'An idle Line keeps a steady glow without packets');
    }
  });

  await check('polls, colors, and multi-selection preserve one shared flow phase', async () => {
    await phaseAcross('A plain poll', refresh);
    const ids = await page.locator('#wall .wall-line[data-line]').evaluateAll(nodes => nodes.map(node => node.dataset.line));
    await phaseAcross('A selection update', async () => {
      await page.locator(`#wall .wall-line[data-line="${ids[0]}"]`).click();
      await page.locator(`#wall .wall-line[data-line="${ids[1]}"]`).click({modifiers: ['Control']});
    });
    assert.equal(await page.locator('#wall .wall-line.selected').count(), 2, 'Control-click keeps multi-selection');

    const changed = await page.evaluate(() => {
      const value = structuredClone(state);
      if (value.projects?.length) value.projects[0].color = value.projects[0].color?.toLowerCase() === '#12abef' ? '#ef8a12' : '#12abef';
      return value;
    });
    const route = request => request.fulfill({json: changed});
    await page.route('**/api/state', route);
    try { await phaseAcross('A polled color update', refresh); }
    finally { await page.unroute('**/api/state', route); await refresh(); }
    await page.keyboard.press('Escape');
  });

  await check('Quiet is steady and lower; Free is dim, desaturated, and released', async () => {
    const work = await firstBedOpacity();
    await waitForPhase(.22, .58);
    await setMode('quiet');
    const quietStart = (await snapshot()).lightPhase;
    await page.waitForTimeout(220);
    const quietMotion = await wallMotion();
    assert.equal(circularError(quietMotion.snapshot.lightPhase, quietStart), 0, 'Quiet freezes the shared clock without resetting it');
    assert.equal(quietMotion.packets, 0, 'Quiet has no traveling packets');
    assert.equal(quietMotion.sparks, 0, 'Quiet has no spark');
    assert.equal(quietMotion.activeAnimations, 0, 'Quiet schedules no visible wall animation');
    const quiet = await firstBedOpacity();
    assert.ok(work > quiet, `Work bed (${work}) is brighter than Quiet (${quiet})`);

    await setMode('free');
    const free = await firstBedOpacity();
    const filter = await page.locator('#wall [data-layer="lines"]').first().evaluate(node => getComputedStyle(node).filter);
    assert.ok(quiet > free, `Quiet bed (${quiet}) is brighter than Free (${free})`);
    assert.notEqual(filter, 'none', 'Free visibly desaturates the tubes');
    assert.match(await page.locator('#readout').textContent(), /released/i, 'The readout says lights are released in Free');
    assert.equal(await page.locator('#locate').isDisabled(), true, 'Locate is disabled in Free');

    const resumed = await page.evaluate(async () => {
      const renderer = prism, original = renderer.setMode;
      let notifyTransition, timeout;
      const transitioned = new Promise(resolve => { notifyTransition = resolve; });
      // A poll already in flight can defer rendering beyond action() returning.
      // Keep observing until the real transition, with a bounded failure wait.
      renderer.setMode = function(mode) {
        const previous = this.snapshot().mode, now = performance.now();
        const result = original.call(this, mode);
        if (previous === 'free' && mode === 'work') notifyTransition({now, phase: this.snapshot().lightPhase});
        return result;
      };
      try {
        await action('/api/mode', {mode: 'work'});
        return await Promise.race([
          transitioned,
          new Promise((_, reject) => { timeout = setTimeout(() => reject(Error('Work transition was not rendered within 5 s')), 5000); }),
        ]);
      } finally { clearTimeout(timeout); renderer.setMode = original; }
    });
    assert.ok(resumed, 'The mode action reaches the renderer');
    assert.equal(resumed.phase, quietStart, 'Returning to Work retains the exact frozen phase');
    // Deliberately wait beyond the old 240 ms allowance. Slow rendering is
    // legitimate elapsed Work time, not a reason to permit a phase reset.
    await page.waitForTimeout(520);
    const after = await page.evaluate(() => {
      const now = performance.now(); prism.light(now);
      return {now, phase: wallAssembly.snapshot().lightPhase};
    });
    const expected = (resumed.phase + (after.now - resumed.now) / 2000) % 1;
    assert.ok(circularError(after.phase, expected) <= .025,
      `Resumed Work preserves the 50 ms flow boundary (expected ${expected.toFixed(3)}, got ${after.phase.toFixed(3)})`);
  });

  await check('reduced motion removes assembly and flow while preserving static mode hierarchy and Locate feedback', async () => {
    await setMode('work');
    await page.emulateMedia({reducedMotion: 'reduce'});
    try {
      await replay(); await settle();
      const reduced = await wallMotion();
      assert.equal(reduced.snapshot.reducedMotion, true);
      assert.equal(reduced.snapshot.progress, 1, 'Replay lands immediately at the final structure');
      assert.equal(reduced.snapshot.playing, false);
      assert.equal(reduced.packets, 0, 'Reduced motion suppresses flow');
      assert.equal(reduced.sparks, 0, 'Reduced motion suppresses the spark');
      assert.equal(reduced.activeAnimations, 0, 'Reduced motion has no running wall animations');
      const work = await firstBedOpacity();
      await setMode('quiet'); const quiet = await firstBedOpacity();
      await setMode('free'); const free = await firstBedOpacity();
      assert.ok(work > quiet && quiet > free, `Static mode hierarchy is Work ${work}, Quiet ${quiet}, Free ${free}`);

      await setMode('work');
      const id = await page.locator('#wall .wall-line[data-line]').first().getAttribute('data-line');
      await page.locator(`#wall .wall-line[data-line="${id}"]`).click();
      await page.locator('#locate').click(); await page.waitForTimeout(250);
      const locating = await page.locator(`#wall .wall-line[data-line="${id}"] .selection-ring`).evaluate(node => ({
        opacity: +getComputedStyle(node).opacity,
        stroke: getComputedStyle(node).stroke,
        width: +getComputedStyle(node).strokeWidth.replace('px', ''),
      }));
      assert.ok(locating.opacity > 0 && locating.width > 0, 'Locate retains static visible feedback');
      await page.keyboard.press('Escape');
    } finally {
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await setMode('work');
    }
  });

  await check('pending state and the operational readout stay visible at supported widths', async () => {
    const pending = await page.evaluate(() => {
      const value = structuredClone(state);
      value.pending = {settings: {}, lines: {[value.lines[0].id]: {project: 'a'}}, tasks: {}};
      return value;
    });
    const route = request => request.fulfill({json: pending});
    await page.route('**/api/state', route);
    try {
      await refresh();
      assert.match((await page.locator('#readout').textContent()).toLowerCase(), /pending/, 'Readout reports the pending edit');
      assert.equal(await page.locator('#wall .wall-line.pending').count(), 1, 'One Line carries the pending class');
      const ring = await page.locator('#wall .wall-line.pending .pending-ring').evaluate(node => ({
        opacity: +getComputedStyle(node).opacity,
        stroke: getComputedStyle(node).stroke,
      }));
      assert.ok(ring.opacity > 0, 'Pending ring is visible');
      assert.equal(ring.stroke, 'rgb(232, 121, 249)', 'Pending ring is magenta');
      for (const width of [1600, 1440, 1280, 1100, 1050]) {
        await page.setViewportSize({width, height: 1000}); await settle();
        const fit = await page.evaluate(() => {
          const readout = document.getElementById('readout');
          return {
            clipped: readout.scrollWidth > readout.clientWidth + 1 || readout.scrollHeight > readout.clientHeight + 1,
            header: document.querySelector('header').getBoundingClientRect().height,
            overflow: document.documentElement.scrollWidth > innerWidth,
          };
        });
        assert.equal(fit.clipped, false, `Readout is not clipped at ${width}px`);
        assert.ok(fit.header <= 60, `Toolbar stays in one row at ${width}px`);
        assert.equal(fit.overflow, false, `No horizontal overflow at ${width}px`);
      }
    } finally {
      await page.unroute('**/api/state', route);
      await page.setViewportSize({width: 1440, height: 1000});
      await refresh();
    }
  });

  await check('watching, Replay, selection, and local assembly preferences remain passive', async () => {
    const writes = [];
    const record = request => { if (request.method() !== 'GET') writes.push(request.url()); };
    const before = await page.evaluate(() => state.tasks.map(task => [task.id, task.status, task.started, task.unread]));
    page.on('request', record);
    try {
      const ids = await page.locator('#wall .wall-line[data-line]').evaluateAll(nodes => nodes.map(node => node.dataset.line));
      await page.locator(`#wall .wall-line[data-line="${ids[2]}"]`).click();
      await page.locator(`#wall .wall-line[data-line="${ids[3]}"]`).click({modifiers: ['Control']});
      await replay();
      await page.evaluate(() => prism.finish('finish'));
      await options.open(page);
      await page.locator('#assemblyOnEntry').click(); await page.locator('#assemblyOnEntry').click();
      await page.keyboard.press('Escape');
      await page.waitForTimeout(250);
      await page.keyboard.press('Escape');
      assert.deepEqual(writes, [], 'Passive wall use sends no write request');
    } finally { page.off('request', record); }
    const after = await page.evaluate(() => state.tasks.map(task => [task.id, task.status, task.started, task.unread]));
    assert.deepEqual(after, before, 'Passive wall use does not mutate task epochs or unread state');
  });

  if (failures.length) throw Error('Presentation checks failed:\n' + failures.join('\n'));
  console.log('Presentation checks passed: Prism flow, shared phase, modes, reduced motion, Locate, pending readout, and passive boundaries.');
};
