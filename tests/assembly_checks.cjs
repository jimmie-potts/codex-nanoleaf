const assert = require('node:assert/strict');

// Issue #38: wall-assembly-animation. Orb, outward assembly, triggers and preferences, completion, boundaries.
module.exports = async function(page, root) {
  const failures = [];
  const check = async (name, fn) => {try {await fn()} catch (error) {failures.push(`${name} -> ${error.message.split('\n')[0]}`)}};
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const refresh = () => page.evaluate(async () => {while (refreshing) await new Promise(resolve => setTimeout(resolve, 10)); await refresh()});
  const running = () => page.evaluate(() => document.getElementById('wall').getAnimations({subtree: true}).filter(a => a.id === 'assembly' && a.playState === 'running').length);
  const untilIdle = async (limit = 3000) => {const start = Date.now(); while (await running() > 0) {if (Date.now() - start > limit) return false; await page.waitForTimeout(50)} return Date.now() - start};
  const geometry = () => page.evaluate(() => ({
    groups: [...document.querySelectorAll('.wall-line')].map(g => [g.dataset.line, getComputedStyle(g).transform, getComputedStyle(g).opacity]),
    numbers: [...document.querySelectorAll('#wall .number')].map(n => [n.dataset.lineId, n.getAttribute('x'), n.getAttribute('y'), getComputedStyle(n.closest('.number-tag')).opacity]),
    joints: document.querySelectorAll('#wall .joint').length,
  }));
  const setPref = async (id, on) => {
    if (await page.locator('#' + id).isChecked() === on) return;
    if (!await page.locator('.assembly-prefs').evaluate(node => node.open)) await page.locator('.assembly-prefs > summary').click();
    await page.locator('#' + id).click(); // a real pointer click, so a covered control fails here
    assert.equal(await page.locator('#' + id).isChecked(), on, `${id} toggles with a mouse click`);
    await page.keyboard.press('Escape');
  };
  await page.setViewportSize({width: 1440, height: 1000});
  await page.evaluate(() => {try {localStorage.removeItem('wall.assembly.opening'); localStorage.removeItem('wall.assembly.entry')} catch {}});

  await check('C1-C3: first load assembles outward from the orb and lands on exact geometry', async () => {
    await page.reload(); await page.waitForSelector('.wall-line');
    assert.ok(await running() > 0, 'Assembly animations run right after geometry loads');
    const orb = await page.evaluate(() => {const o = document.querySelector('#wall .orb'); const box = document.getElementById('wall').viewBox.baseVal; return o && {cx: +o.getAttribute('cx'), cy: +o.getAttribute('cy'), centerX: box.x + box.width / 2, centerY: box.y + box.height / 2}});
    assert.ok(orb, 'A persistent orb exists on the wall');
    assert.ok(Math.abs(orb.cx - orb.centerX) < 1 && Math.abs(orb.cy - orb.centerY) < 1, 'The orb sits at the bounding-box center');
    const order = await page.evaluate(() => {
      const o = document.querySelector('#wall .orb'), cx = +o.getAttribute('cx'), cy = +o.getAttribute('cy');
      return [...document.querySelectorAll('.wall-line')].map(g => {const a = g.getAnimations().find(x => x.id === 'assembly'); const l = state.lines.find(l => l.id === g.dataset.line); const p = l.points.map(transform); const d = Math.min(...p.map(q => Math.hypot(q[0] - cx, q[1] - cy))); return [d, a ? a.effect.getTiming().delay : null]});
    });
    assert.ok(order.every(([, delay]) => delay !== null), 'Every Line has an assembly animation');
    const nearest = order.reduce((a, b) => a[0] < b[0] ? a : b), farthest = order.reduce((a, b) => a[0] > b[0] ? a : b);
    assert.ok(nearest[1] < farthest[1], `Lines near the orb start before far ones (near ${nearest[1]} ms, far ${farthest[1]} ms)`);
    assert.ok((await geometry()).joints > 0, 'Joints glow during assembly');
    const length = await page.evaluate(() => Math.max(...document.getElementById('wall').getAnimations({subtree: true}).filter(a => a.id === 'assembly').map(a => a.effect.getTiming().delay + a.effect.getTiming().duration)));
    assert.ok(length >= 1800 && length <= 2400, `The sequence is roughly two seconds long (${length} ms)`);
    const took = await untilIdle(); assert.ok(took !== false && took <= 2600, `Assembly finishes within about two seconds (${took} ms observed after load)`);
    const final = await geometry();
    assert.ok(final.groups.every(([, t, o]) => (t === 'none' || t === 'matrix(1, 0, 0, 1, 0, 0)') && o === '1'), 'Every Line settles at identity with full opacity');
    assert.ok(final.numbers.every(([, , , o]) => o === '1'), 'Number tags are fully visible after assembly');
    assert.equal(final.joints, 0, 'Joints are removed after assembly');
    const clean = await page.evaluate(() => {wallFingerprint = ''; drawWall(); return [...document.querySelectorAll('#wall .number')].map(n => [n.dataset.lineId, n.getAttribute('x'), n.getAttribute('y')])});
    assert.deepEqual(final.numbers.map(([id, x, y]) => [id, x, y]), clean, 'Assembly leaves the geometry exactly as a plain draw');
    assert.equal(await page.locator('.wall-line').count(), 15);
  });

  await check('C4: preferences are browser-local, default on, and gate opening and entry playback', async () => {
    assert.equal(await page.locator('#assemblyOnOpen').isChecked(), true, 'Play on opening defaults on');
    assert.equal(await page.locator('#assemblyOnEntry').isChecked(), true, 'Play on view entry defaults on');
    await setPref('assemblyOnOpen', false);
    assert.equal(await page.evaluate(() => localStorage.getItem('wall.assembly.opening')), '0', 'Opening preference persists');
    await page.reload(); await page.waitForSelector('.wall-line'); await page.waitForTimeout(300);
    assert.equal(await running(), 0, 'No assembly on load when the opening preference is off');
    assert.equal(await page.locator('#assemblyOnOpen').isChecked(), false, 'Preference survives reload');
    assert.ok((await geometry()).groups.every(([, t]) => t === 'none' || t === 'matrix(1, 0, 0, 1, 0, 0)'), 'Structure is complete without assembly');
    await page.locator('#replay').click();
    assert.ok(await running() > 0, 'Replay still plays with opening off');
    await untilIdle();
    await setPref('assemblyOnEntry', false);
    await page.evaluate(() => wallAssembly.play('entry')); await settle();
    assert.equal(await running(), 0, 'Entry playback respects the entry preference');
    await setPref('assemblyOnEntry', true);
    await page.evaluate(() => wallAssembly.play('entry')); await settle();
    assert.ok(await running() > 0, 'Entry playback is available through the integration point');
    await untilIdle();
    await setPref('assemblyOnOpen', true);
  });

  await check('C5: polling, mode, and layout changes never trigger assembly', async () => {
    await untilIdle();
    await refresh(); await settle(); assert.equal(await running(), 0, 'A poll does not start assembly');
    const failing = request => request.fulfill({status: 503, json: {error: 'Local map status unavailable. Retrying shortly.'}});
    await page.route('**/api/state', failing); await refresh(); await page.unroute('**/api/state', failing);
    await page.evaluate(() => {errorUntil = 0}); await refresh(); await settle();
    assert.equal(await running(), 0, 'Reconnecting after a failed poll does not start assembly');
    await page.evaluate(() => {window.dispatchEvent(new Event('focus')); document.dispatchEvent(new Event('visibilitychange'))}); await settle();
    assert.equal(await running(), 0, 'Returning focus or visibility does not start assembly');
    await page.evaluate(() => action('/api/mode', {mode: 'quiet'})); await page.waitForFunction(() => state.mode === 'quiet'); await settle();
    assert.equal(await running(), 0, 'A mode change does not start assembly');
    await page.evaluate(() => action('/api/settings', {style: 'classic'})); await page.waitForFunction(() => state.settings.style === 'classic'); await settle();
    assert.equal(await running(), 0, 'A layout change does not start assembly');
    await page.evaluate(() => action('/api/settings', {style: 'project'})); await page.waitForFunction(() => state.settings.style === 'project');
    await page.evaluate(() => action('/api/mode', {mode: 'work'})); await page.waitForFunction(() => state.mode === 'work');
  });

  await check('C6: assembly settles into the current mode and reduced motion skips it', async () => {
    await page.evaluate(() => action('/api/mode', {mode: 'quiet'})); await page.waitForFunction(() => state.mode === 'quiet' && document.body.dataset.mode === 'quiet');
    await page.locator('#replay').click(); await untilIdle();
    const quietHalo = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('.wall-line[data-status] .glow')).opacity));
    const quietToken = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--glow-quiet')));
    assert.equal(quietHalo, quietToken, 'Quiet halo after assembly');
    await page.evaluate(() => action('/api/mode', {mode: 'work'})); await page.waitForFunction(() => state.mode === 'work');
    await page.emulateMedia({reducedMotion: 'reduce'});
    try {
      await page.locator('#replay').click(); await settle();
      assert.equal(await running(), 0, 'Reduced motion skips assembly');
      assert.equal(await page.locator('#wall .orb').count(), 1, 'The orb is still present');
      assert.ok((await geometry()).groups.every(([, t, o]) => (t === 'none' || t === 'matrix(1, 0, 0, 1, 0, 0)') && o === '1'), 'Structure is complete immediately');
      await page.reload(); await page.waitForSelector('.wall-line'); await page.waitForTimeout(300);
      assert.equal(await running(), 0, 'Reduced motion skips the opening assembly too');
      assert.equal(await page.locator('#wall .orb').count(), 1, 'The orb is drawn at load under reduced motion');
    } finally {await page.emulateMedia({reducedMotion: 'no-preference'})}
    await page.evaluate(async () => {while (refreshing) await new Promise(resolve => setTimeout(resolve, 10)); await refresh()});
    await page.evaluate(() => action('/api/mode', {mode: 'work'})); await page.waitForFunction(() => state.mode === 'work'); await untilIdle();
  });

  await check('C7: an interaction completes assembly and acts; repeated Replay does not queue', async () => {
    const ids = await page.locator('.wall-line').evaluateAll(nodes => nodes.map(node => node.dataset.line));
    await page.locator('#replay').click(); await page.waitForTimeout(150);
    assert.ok(await running() > 0);
    await page.locator(`[data-line="${ids[3]}"]`).click({delay: 120}); // a human-speed press
    assert.equal(await running(), 0, 'Interaction completes the assembly immediately');
    await settle();
    assert.equal(await page.locator('.wall-line.selected').getAttribute('data-line', {timeout: 2000}), ids[3], 'The intended selection happens for a held click');
    await page.locator('#clear').click();
    await page.locator('#replay').click(); await page.waitForTimeout(150);
    await page.locator(`[data-line="${ids[4]}"]`).focus(); await page.keyboard.press('Enter');
    assert.equal(await running(), 0, 'A key press completes the assembly');
    await settle();
    assert.equal(await page.locator('.wall-line.selected').getAttribute('data-line', {timeout: 2000}), ids[4], 'The intended selection happens for a key press');
    assert.ok((await geometry()).groups.every(([, t, o]) => (t === 'none' || t === 'matrix(1, 0, 0, 1, 0, 0)') && o === '1'), 'Structure is complete after the interaction');
    await page.locator('#clear').click();
    await page.locator('#replay').click(); await page.waitForTimeout(100);
    const first = await page.evaluate(() => document.getElementById('wall').getAnimations({subtree: true}).filter(a => a.id === 'assembly').length);
    await page.locator('#replay').click(); await page.locator('#replay').click(); await page.waitForTimeout(100);
    const after = await page.evaluate(() => document.getElementById('wall').getAnimations({subtree: true}).filter(a => a.id === 'assembly').length);
    assert.equal(after, first, 'Repeated Replay does not add sequences');
    await untilIdle(); await page.waitForTimeout(600);
    assert.equal(await running(), 0, 'No queued sequence plays afterwards');
  });

  await check('C8: lists update during assembly and disconnected sections assemble independently', async () => {
    const snapshot = await page.evaluate(() => structuredClone(state));
    const renamed = structuredClone(snapshot); renamed.tasks[0].title = 'Renamed during assembly';
    const route = request => request.fulfill({json: renamed});
    await page.locator('#replay').click(); await page.waitForTimeout(100);
    await page.route('**/api/state', route);
    try {
      await refresh(); await settle();
      assert.ok(await running() > 0, 'Assembly keeps playing through a non-geometry poll');
      assert.match(await page.locator('#taskList').textContent(), /Renamed during assembly/, 'The task list updates during assembly');
      await untilIdle();
      assert.match(await page.locator(`.wall-line[data-line="${renamed.tasks[0].line}"] title`).textContent(), /Renamed during assembly/, 'The wall finishes into the latest state');
    } finally {await page.unroute('**/api/state', route)}
    const split = structuredClone(snapshot);
    split.lines.forEach((line, i) => {if (i >= 8) line.points = line.points.map(([x, y]) => [x + 3000, y])});
    const splitRoute = request => request.fulfill({json: split});
    await page.route('**/api/state', splitRoute);
    try {
      await refresh(); await settle(); await untilIdle();
      await page.locator('#replay').click(); await page.waitForTimeout(50);
      const sections = await page.evaluate(() => {
        const o = document.querySelector('#wall .orb'), cx = +o.getAttribute('cx');
        return [...document.querySelectorAll('.wall-line')].map(g => {const l = state.lines.find(l => l.id === g.dataset.line); const p = l.points.map(transform); const a = g.getAnimations().find(x => x.id === 'assembly'); return {right: p[1][0] > cx + 1000, delay: a.effect.getTiming().delay, near: Math.min(...p.map(q => Math.hypot(q[0] - cx, q[1] - +o.getAttribute('cy'))))}});
      });
      const left = sections.filter(s => !s.right), right = sections.filter(s => s.right);
      assert.ok(left.length && right.length, 'The synthetic layout has two sections');
      assert.equal(Math.min(...right.map(s => s.delay)), Math.min(...left.map(s => s.delay)), 'Each section starts from its own root at the same time');
      const rightRoot = right.reduce((a, b) => a.delay < b.delay ? a : b), rightFar = right.reduce((a, b) => a.near > b.near ? a : b);
      assert.ok(rightRoot.near <= rightFar.near && rightRoot.delay < rightFar.delay, 'The far section assembles outward from its nearest Line');
      await untilIdle();
    } finally {await page.unroute('**/api/state', splitRoute); await refresh(); await untilIdle()}
  });

  await check('C8: geometry changes and connection failures end assembly and the map shows the latest state', async () => {
    const snapshot = await page.evaluate(() => structuredClone(state));
    const rotated = structuredClone(snapshot); rotated.settings.rotation = 90;
    const route = request => request.fulfill({json: rotated});
    await page.locator('#replay').click();
    assert.ok(await running() > 0, 'Assembly is running before the geometry changes');
    await page.route('**/api/state', route);
    try {
      await refresh(); await settle();
      assert.equal(await running(), 0, 'A geometry change ends assembly immediately');
      assert.equal(await page.evaluate(() => state.settings.rotation), 90);
      const drawn = await page.evaluate(() => wallFingerprint.includes('"rotation":90'));
      assert.ok(drawn, 'The wall shows the latest geometry after assembly ends');
    } finally {await page.unroute('**/api/state', route)}
    await refresh(); await untilIdle();
    const failing = request => request.fulfill({status: 503, json: {error: 'Local map status unavailable. Retrying shortly.'}});
    await page.locator('#replay').click();
    assert.ok(await running() > 0, 'Assembly is running before the connection fails');
    await page.route('**/api/state', failing);
    try {
      await refresh(); await settle();
      assert.equal(await running(), 0, 'A connection failure ends assembly immediately');
      assert.match(await page.locator('#connection').textContent(), /Disconnected/);
    } finally {await page.unroute('**/api/state', failing); await page.evaluate(() => {errorUntil = 0}); await refresh()}
  });

  await check('C9: assembly writes nothing and keeps the status pulses on phase', async () => {
    const writes = [];
    const record = request => {if (request.method() !== 'GET') writes.push(request.url())};
    page.on('request', record);
    try {
      await page.locator('#replay').click(); await page.waitForTimeout(300);
      const during = await page.evaluate(() => {const a = document.querySelector('.wall-line[data-status] .glow').getAnimations().find(x => x.animationName === 'pulse'); return a && a.startTime === 0 && a.playState === 'running'});
      assert.equal(during, true, 'Status pulses keep running on the document timeline during assembly');
      await untilIdle();
      const after = await page.evaluate(() => {const a = document.querySelector('.wall-line[data-status] .glow').getAnimations().find(x => x.animationName === 'pulse'); return a && a.startTime === 0});
      assert.equal(after, true, 'Status pulses keep the page-wide phase after assembly');
      await setPref('assemblyOnEntry', false); await setPref('assemblyOnEntry', true);
      assert.deepEqual(writes, [], 'Assembly, Replay, and preferences issue no write requests');
    } finally {page.off('request', record)}
  });

  if (failures.length) throw Error('Assembly checks failed:\n' + failures.join('\n'));
  console.log('Assembly checks passed: orb, outward assembly, geometry, preferences, triggers, modes, reduced motion, completion, cancellation, and boundaries.');
};
