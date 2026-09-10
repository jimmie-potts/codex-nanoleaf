const assert = require('node:assert/strict');

/*
 * Prism assembly acceptance contract.
 *
 * Required live selectors:
 *   #wall.prism-scene
 *   [data-root] containing [data-edge] and [data-node]
 *   [data-slide], [data-rim][data-open], [data-charge], [data-shutters]
 *   static .wall-line[data-line][role="button"], [data-hit], and
 *   .number-tag[data-line-id]
 *
 * Required public bridge:
 *   window.wallAssembly.play(reason), active(), snapshot()
 * snapshot() forwards Prism.Renderer.snapshot(). The existing lexical `prism`
 * handle is used for deterministic finish calls. Public Prism.Renderer is used
 * directly only for disconnected-component acceptance. Tests assert visible
 * geometry, timing, accessibility, request traffic, and app state rather than
 * private traversal tables or frame IDs.
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
  const waitProgress = (low, high) => page.waitForFunction(([min, max]) => {
    const current = window.wallAssembly?.snapshot?.();
    return current?.playing && current.progress >= min && current.progress <= max;
  }, [low, high], {timeout: 4500});
  const untilIdle = async () => {
    const started = await page.evaluate(() => performance.now());
    await page.waitForFunction(() => {
      const current = window.wallAssembly?.snapshot?.();
      return current && !current.playing && current.progress === 1;
    }, null, {timeout: 4500});
    return page.evaluate(value => performance.now() - value, started);
  };
  const setPref = async (id, on) => {
    if (await page.locator('#' + id).isChecked() === on) return;
    if (!await page.locator('.assembly-prefs').evaluate(node => node.open)) await page.locator('.assembly-prefs > summary').click();
    await page.locator('#' + id).click();
    assert.equal(await page.locator('#' + id).isChecked(), on, `${id} toggles with a pointer click`);
    await page.keyboard.press('Escape');
  };
  const finalGeometry = () => page.evaluate(() => ({
    progress: wallAssembly.snapshot().progress,
    roots: [...document.querySelectorAll('#wall [data-root]')].map(node => node.getAttribute('transform')),
    edges: [...document.querySelectorAll('#wall [data-edge]')].map(node => ({
      id: node.dataset.lineId,
      visible: getComputedStyle(node).visibility,
      transform: node.getAttribute('transform'),
    })),
    rims: [...document.querySelectorAll('#wall [data-node]')].map(node => [...node.querySelectorAll('[data-rim]')].map(rim => +rim.dataset.open)),
    labels: [...document.querySelectorAll('#wall .number-tag[data-line-id]')].map(node => ({
      id: node.dataset.lineId,
      visibility: getComputedStyle(node).visibility,
      opacity: +getComputedStyle(node).opacity,
      transform: node.getAttribute('transform'),
    })),
    transientVisible: [...document.querySelectorAll('#wall [data-charge], #wall [data-shutters], #wall [data-socket]')]
      .filter(node => getComputedStyle(node).visibility !== 'hidden' && +getComputedStyle(node).opacity > .01).length,
    legacyOverlays: document.querySelectorAll('#wall .orb, #wall .joints, #wall .joint').length,
  }));

  await page.setViewportSize({width: 1440, height: 1000});
  await page.evaluate(() => {
    try {
      localStorage.removeItem('wall.assembly.opening');
      localStorage.removeItem('wall.assembly.entry');
      localStorage.setItem('wall.numbers.showAll', '1');
    } catch {}
  });

  await check('first load is a two-second mechanical assembly rooted with its beams', async () => {
    await page.reload();
    await page.waitForSelector('#wall.prism-scene .wall-line[data-line]');
    assert.equal(await page.locator('#showNumbers').getAttribute('aria-pressed'), 'true', 'Assembly checks explicitly enable all browser-local numbers');
    assert.equal(await page.evaluate(() => typeof window.wallAssembly?.snapshot), 'function', 'snapshot bridge exists');
    await waitProgress(.20, .46);
    const middle = await page.evaluate(() => {
      const current = wallAssembly.snapshot();
      return {
        current,
        roots: [...document.querySelectorAll('#wall [data-root]')].map(root => ({
          transform: root.getAttribute('transform'),
          edges: root.querySelectorAll('[data-edge]').length,
          nodes: root.querySelectorAll('[data-node]').length,
        })),
        slides: [...document.querySelectorAll('#wall [data-slide]')].map(node => node.getAttribute('transform')),
        tubes: document.querySelectorAll('#wall [data-part="tube-body"]').length,
        facets: document.querySelectorAll('#wall [data-part="tube-facets"]').length,
        connectors: [...document.querySelectorAll('#wall [data-node]')].map(node => ({
          events: getComputedStyle(node).pointerEvents,
          rims: node.querySelectorAll('[data-rim]').length,
        })),
        materialEvents: getComputedStyle(document.querySelector('#wall [data-layer="materials"]')).pointerEvents,
        controls: [...document.querySelectorAll('#wall .wall-line[data-line]')].map(node => ({
          role: node.getAttribute('role'),
          tab: node.getAttribute('tabindex'),
          events: getComputedStyle(node).pointerEvents,
          hit: !!node.querySelector('[data-hit]'),
          transform: node.getAttribute('transform'),
        })),
        labels: [...document.querySelectorAll('#wall .number-tag[data-line-id]')].map(node => ({
          visible: getComputedStyle(node).visibility,
          opacity: +getComputedStyle(node).opacity,
          transform: node.getAttribute('transform'),
        })),
      };
    });
    assert.ok(middle.current.playing && middle.current.progress > 0 && middle.current.progress < 1, 'Assembly is observably in flight');
    assert.equal(middle.roots.length, middle.current.components, 'Each component has one moving root wrapper');
    assert.ok(middle.roots.every(item => item.edges > 0 && item.nodes > 0), 'Root wrappers move connectors and beams as one mechanism');
    assert.ok(middle.roots.some(item => item.transform && !/^rotate\(0(?:[ )]|$)/.test(item.transform)), 'At least one root wrapper is rotated during assembly');
    assert.ok(middle.slides.some(value => /translate\((?!0(?:\.0+)?\s)/.test(value)), 'Tubes visibly slide out from connectors');
    assert.equal(middle.tubes, middle.current.lines, 'Each Line keeps its full tube body while sliding');
    assert.equal(middle.facets, middle.current.lines, 'Each Line keeps the approved tube facets while sliding');
    assert.ok(middle.connectors.every(item => item.rims === 6), 'All six rim segments remain mounted throughout assembly');
    assert.ok(middle.connectors.every(item => item.events === 'none') && middle.materialEvents === 'none', 'Materials and connectors cannot intercept input');
    assert.equal(middle.controls.length, middle.current.lines, 'Static final-position controls exist throughout assembly');
    assert.ok(middle.controls.every(item => item.role === 'button' && item.tab === '0' && item.hit && item.transform), 'Every static hit target remains keyboard and pointer usable');
    assert.equal(middle.labels.length, middle.current.lines, 'Final label nodes remain mounted during assembly');
    assert.ok(middle.labels.every(item => item.visible === 'visible' && item.transform), 'showAllNumbers keeps every final-position label available');
    assert.ok(middle.labels.every(item => item.opacity < .05), 'Number labels wait until the final assembly beat to fade in');

    const elapsed = await untilIdle();
    assert.ok(elapsed > 900 && elapsed < 1900, `The remaining first-load sequence completes on the two-second schedule (${elapsed.toFixed(0)} ms from mid-sequence)`);
    const final = await finalGeometry();
    assert.equal(final.progress, 1);
    assert.ok(final.edges.every(edge => edge.visible !== 'hidden'), 'Every physical Line is visible at its final geometry');
    assert.ok(final.rims.every(rims => rims.length === 6 && rims.every(value => Math.abs(value - 1) < .001)), 'All six rim segments on every connector stay open and persistent');
    assert.ok(final.labels.every(label => label.visibility === 'visible' && label.opacity > .99 && label.transform), 'All Line numbers finish visible at their final label transforms');
    assert.equal(final.transientVisible, 0, 'Charges, shutters, and loop sockets leave no visible overlay');
    assert.equal(final.legacyOverlays, 0, 'No legacy orb or joint overlays remain');
  });

  await check('Replay lasts two seconds and begins one fresh flow epoch at completion', async () => {
    await page.locator('#replay').click();
    await page.waitForFunction(() => wallAssembly.snapshot().playing);
    const start = await page.evaluate(() => performance.now());
    await untilIdle();
    const result = await page.evaluate(value => ({elapsed: performance.now() - value, ...wallAssembly.snapshot()}), start);
    assert.ok(result.elapsed >= 1850 && result.elapsed <= 2350, `Replay takes about two seconds (${result.elapsed.toFixed(0)} ms)`);
    assert.ok(result.lightPhase >= 0 && result.lightPhase < .08, `Flow starts at phase zero after Replay (${result.lightPhase.toFixed(3)})`);
    await page.waitForFunction(() => wallAssembly.snapshot().lightPhase > .18);
    const before = await page.evaluate(() => ({phase: wallAssembly.snapshot().lightPhase, time: performance.now()}));
    await page.evaluate(() => prism.finish('finish'));
    await page.waitForTimeout(120);
    const after = await page.evaluate(() => ({phase: wallAssembly.snapshot().lightPhase, time: performance.now()}));
    const expected = (before.phase + (after.time - before.time) / 2000) % 1;
    const error = Math.min(Math.abs(after.phase - expected), 1 - Math.abs(after.phase - expected));
    assert.ok(error <= .025, `A redundant finish preserves the flow clock within 50 ms (expected ${expected.toFixed(3)}, got ${after.phase.toFixed(3)})`);
  });

  await check('browser-local preferences gate opening and entry playback while Replay remains available', async () => {
    assert.equal(await page.locator('#assemblyOnOpen').isChecked(), true, 'Opening playback defaults on');
    assert.equal(await page.locator('#assemblyOnEntry').isChecked(), true, 'Entry playback defaults on');
    await setPref('assemblyOnOpen', false);
    assert.equal(await page.evaluate(() => localStorage.getItem('wall.assembly.opening')), '0', 'Opening preference is browser-local');
    await page.reload(); await page.waitForSelector('#wall.prism-scene .wall-line[data-line]'); await page.waitForTimeout(250);
    assert.equal((await snapshot()).playing, false, 'Opening disabled lands immediately on the final wall');
    assert.equal((await snapshot()).progress, 1);
    await page.locator('#replay').click();
    assert.equal((await snapshot()).playing, true, 'Replay remains available when opening playback is disabled');
    await untilIdle();

    await setPref('assemblyOnEntry', false);
    await page.evaluate(() => wallAssembly.play('entry')); await settle();
    assert.equal((await snapshot()).playing, false, 'Entry playback respects its local preference');
    await setPref('assemblyOnEntry', true);
    await page.evaluate(() => wallAssembly.play('entry'));
    assert.equal((await snapshot()).playing, true, 'The public entry integration starts playback when enabled');
    await untilIdle();
    await setPref('assemblyOnOpen', true);
  });

  await check('polls, colors, selection, and focus do not restart completed assembly', async () => {
    assert.equal((await snapshot()).playing, false);
    await refresh(); await settle();
    assert.equal((await snapshot()).playing, false, 'A normal poll does not assemble');
    const changed = await page.evaluate(() => {
      const value = structuredClone(state);
      if (value.projects?.length) value.projects[0].color = '#12abef';
      return value;
    });
    const route = request => request.fulfill({json: changed});
    await page.route('**/api/state', route);
    try { await refresh(); await settle(); assert.equal((await snapshot()).playing, false, 'A color poll does not assemble'); }
    finally { await page.unroute('**/api/state', route); await refresh(); }
    const id = await page.locator('#wall .wall-line[data-line]').first().getAttribute('data-line');
    await page.locator(`#wall .wall-line[data-line="${id}"]`).click();
    assert.equal((await snapshot()).playing, false, 'Selection does not assemble');
    await page.locator(`#wall .wall-line[data-line="${id}"]`).focus();
    await page.evaluate(() => { window.dispatchEvent(new Event('focus')); document.dispatchEvent(new Event('visibilitychange')); });
    await page.waitForTimeout(1100);
    assert.equal(await page.evaluate(value => document.activeElement?.dataset.line === value, id), true, 'Polling preserves keyboard focus');
    assert.equal((await snapshot()).playing, false, 'Focus and visibility events do not assemble');
    await page.locator('#clear').click();
  });

  await check('Quiet settles steady and reduced motion skips every assembly path', async () => {
    await page.evaluate(() => action('/api/mode', {mode: 'quiet'}));
    await page.waitForFunction(() => state.mode === 'quiet');
    await page.locator('#replay').click();
    assert.equal((await snapshot()).playing, true, 'Quiet may show the mechanical assembly');
    await untilIdle();
    const quiet = await snapshot();
    assert.equal(quiet.mode, 'quiet');
    assert.equal(await page.locator('#wall [data-packet]').evaluateAll(nodes => nodes.filter(node => +getComputedStyle(node).opacity > .02).length), 0, 'Quiet settles without flow');

    await page.evaluate(() => action('/api/mode', {mode: 'work'}));
    await page.waitForFunction(() => state.mode === 'work');
    await page.emulateMedia({reducedMotion: 'reduce'});
    try {
      await page.locator('#replay').click(); await settle();
      const reduced = await snapshot();
      assert.equal(reduced.reducedMotion, true);
      assert.equal(reduced.playing, false, 'Reduced motion skips Replay');
      assert.equal(reduced.progress, 1, 'Reduced motion lands at final geometry');
      await page.reload(); await page.waitForSelector('#wall.prism-scene .wall-line[data-line]'); await page.waitForTimeout(250);
      assert.equal((await snapshot()).playing, false, 'Reduced motion skips opening playback');
      assert.ok((await finalGeometry()).rims.every(rims => rims.length === 6 && rims.every(value => Math.abs(value - 1) < .001)), 'Final connector rims remain under reduced motion');
    } finally {
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await refresh();
    }
  });

  await check('pointer and keyboard input finish assembly first and still execute the intended selection', async () => {
    const ids = await page.locator('#wall .wall-line[data-line]').evaluateAll(nodes => nodes.map(node => node.dataset.line));
    await page.locator('#replay').click(); await waitProgress(.05, .35);
    const pointerTarget = page.locator(`#wall .wall-line[data-line="${ids[3]}"]`);
    const box = await pointerTarget.boundingBox();
    assert.ok(box && box.width > 0 && box.height > 0, 'The static hit layer has a pointer target during assembly');
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    const pressed = await snapshot();
    assert.equal(pressed.playing, false, 'Pointer down commits assembly');
    assert.ok(pressed.lightPhase < .08, 'Interaction completion starts the flow at phase zero');
    await page.waitForTimeout(600);
    await page.mouse.up(); await settle();
    assert.equal(await page.locator(`#wall .wall-line[data-line="${ids[3]}"]`).getAttribute('aria-pressed'), 'true', 'The held click still selects its intended Line');
    await page.locator('#clear').click();

    await page.locator('#replay').click(); await waitProgress(.05, .35);
    await page.locator(`#wall .wall-line[data-line="${ids[4]}"]`).focus();
    await page.keyboard.press('Enter');
    assert.equal((await snapshot()).playing, false, 'Keyboard activation commits assembly');
    assert.equal(await page.locator(`#wall .wall-line[data-line="${ids[4]}"]`).getAttribute('aria-pressed'), 'true', 'Enter still selects its intended Line');
    await page.locator('#clear').click();

    await page.locator('#replay').click(); await page.waitForTimeout(120);
    const before = (await snapshot()).progress;
    await page.locator('#replay').click(); await page.locator('#replay').click(); await page.waitForTimeout(120);
    assert.ok((await snapshot()).progress >= before, 'Repeated Replay never restarts or queues the active sequence');
    await untilIdle(); await page.waitForTimeout(350);
    assert.equal((await snapshot()).playing, false, 'No queued replay begins later');
  });

  await check('task text updates during assembly; geometry and connection changes commit it', async () => {
    const original = await page.evaluate(() => structuredClone(state));
    const renamed = structuredClone(original);
    renamed.tasks[0].title = 'Renamed during Prism assembly';
    const renamedRoute = request => request.fulfill({json: renamed});
    await page.locator('#replay').click(); await page.waitForTimeout(100);
    await page.route('**/api/state', renamedRoute);
    try {
      await refresh();
      assert.equal((await snapshot()).playing, true, 'A text-only poll keeps assembly running');
      assert.match(await page.locator('#taskList').textContent(), /Renamed during Prism assembly/, 'Task list updates immediately');
      await untilIdle();
      assert.match(await page.locator(`#wall .wall-line[data-line="${renamed.tasks[0].line}"] title`).textContent(), /Renamed during Prism assembly/, 'Final wall title uses the latest task text');
    } finally { await page.unroute('**/api/state', renamedRoute); }

    const rotated = structuredClone(original); rotated.settings.rotation = (original.settings.rotation + 90) % 360;
    const rotatedRoute = request => request.fulfill({json: rotated});
    await page.locator('#replay').click(); await page.route('**/api/state', rotatedRoute);
    try {
      await refresh(); await settle();
      assert.equal((await snapshot()).playing, false, 'A geometry change commits assembly immediately');
      assert.equal(await page.evaluate(() => state.settings.rotation), rotated.settings.rotation, 'The wall adopts the latest geometry');
    } finally { await page.unroute('**/api/state', rotatedRoute); await refresh(); }

    const failing = request => request.fulfill({status: 503, json: {error: 'Local map status unavailable. Retrying shortly.'}});
    await page.locator('#replay').click(); await page.route('**/api/state', failing);
    try {
      await refresh(); await settle();
      assert.equal((await snapshot()).playing, false, 'A connection failure commits assembly');
      assert.match(await page.locator('#connection').textContent(), /Disconnected/);
    } finally {
      await page.unroute('**/api/state', failing);
      await page.evaluate(() => { errorUntil = 0; });
      await refresh();
    }
  });

  await check('provided roots start disconnected components together without inventing a controller root', async () => {
    const result = await page.evaluate(async () => {
      const host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:0;top:0;width:500px;height:500px;z-index:-1';
      document.body.append(host);
      const layout = {
        version: 1,
        rootIds: ['connector-a', 'connector-c'],
        nodes: [
          {id: 'connector-a', x: 0, y: 0, sourceIds: ['a']},
          {id: 'connector-b', x: 200, y: 0, sourceIds: ['b']},
          {id: 'connector-c', x: 0, y: 360, sourceIds: ['c']},
          {id: 'connector-d', x: 200, y: 360, sourceIds: ['d']},
        ],
        lines: [
          {id: 'physical-8', number: 8, a: 'connector-a', b: 'connector-b', zoneIds: ['8a', '8b'], colors: ['#12abef', '#ef8a12']},
          {id: 'physical-2', number: 2, a: 'connector-c', b: 'connector-d', zoneIds: ['2a', '2b'], colors: ['#65e7ff', '#b489ff']},
        ],
      };
      const renderer = new Prism.Renderer(host, layout, {animate: true});
      await new Promise((resolve, reject) => {
        const limit = performance.now() + 2500;
        const poll = () => renderer.snapshot().progress >= .22 ? resolve() : performance.now() > limit ? reject(Error('synthetic assembly did not advance')) : requestAnimationFrame(poll);
        poll();
      });
      const current = renderer.snapshot();
      const extensions = [...host.querySelectorAll('[data-slide]')].map(node => (/translate\(([-\d.]+)/.exec(node.getAttribute('transform')) || [0, NaN])[1]).map(Number);
      const identifiers = [...host.querySelectorAll('[data-edge]')].map(node => node.dataset.lineId);
      const numbers = [...host.querySelectorAll('.number')].map(node => node.textContent);
      renderer.destroy(); host.remove();
      return {current, extensions, identifiers, numbers};
    });
    assert.equal(result.current.components, 2);
    assert.deepEqual(result.current.rootIds, ['connector-a', 'connector-c'], 'App-provided root IDs are retained in component order');
    assert.ok(Math.abs(result.extensions[0] - result.extensions[1]) < .5, 'Both disconnected component roots begin at the same assembly beat');
    assert.deepEqual(result.identifiers, ['physical-8', 'physical-2'], 'Physical IDs and deployment order remain stable');
    assert.deepEqual(result.numbers, ['08', '02'], 'Physical numbers are not derived from array position');
  });

  await check('assembly, Replay, and local preferences send no write requests', async () => {
    const writes = [];
    const record = request => { if (request.method() !== 'GET') writes.push(request.url()); };
    page.on('request', record);
    try {
      await page.locator('#replay').click(); await page.waitForTimeout(180);
      await page.evaluate(() => prism.finish('finish'));
      await setPref('assemblyOnEntry', false); await setPref('assemblyOnEntry', true);
      assert.deepEqual(writes, [], 'Passive Prism behavior does not cross the controller write boundary');
    } finally { page.off('request', record); }
  });

  if (failures.length) throw Error('Assembly checks failed:\n' + failures.join('\n'));
  console.log('Assembly checks passed: mechanical roots, persistent materials, timing, preferences, interruption, disconnected components, and passive boundaries.');
};
