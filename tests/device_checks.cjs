const assert = require('node:assert/strict');
const path = require('node:path');
const options = require('./wall_options.cjs');

// Issue #44: a Device selector switches the map between the Lines and the synthetic NL22 Light
// Panels against the real demo server. Selection and switching stay passive, triangles support
// the Lines' actions without the Lines-only halves, and every device-scoped action names its device.
module.exports = async function(page, root) {
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const refresh = () => page.evaluate(async () => {while (refreshing) await new Promise(resolve => setTimeout(resolve, 10)); await refresh()});
  const base = new URL(page.url()).origin;
  const readState = async device => page.evaluate(async id => (await fetch('/api/state' + (id ? '?device=' + id : ''))).json(), device);
  const urlDevice = () => new URL(page.url()).searchParams.get('device');
  const triangles = page.locator('#wall .wall-triangle[data-line]');
  const triangle = id => page.locator(`#wall .wall-triangle[data-line="${id}"]`);
  const runningAnimations = () => page.evaluate(() => document.getElementById('wall').getAnimations({subtree: true}).filter(animation => animation.playState === 'running').length);
  const writes = [];
  const record = request => {if (request.method() !== 'GET') writes.push({path: new URL(request.url()).pathname, body: request.postDataJSON()})};
  const viewport = page.viewportSize();
  const restore = async () => {
    await page.evaluate(async () => {
      if (state?.kind === 'panels') {
        await action('/api/mode', {mode: 'work'});
        await action('/api/settings', {style: 'classic', rotation: 0, flip_x: 0, flip_y: 0});
        await action('/api/assign', {lines: Object.fromEntries(state.lines.map(line => [line.id, {project: null}]))});
      }
    });
    if (await page.evaluate(() => state?.device) !== 'wall') {await page.selectOption('#device', 'wall'); await page.waitForFunction(() => state?.device === 'wall' && document.querySelector('#wall.prism-scene'))}
    await page.evaluate(() => {selected.clear(); taskFocus = null; document.activeElement.blur(); render()});
    await page.waitForFunction(() => !window.wallAssembly.snapshot()?.playing);
  };
  page.on('request', record);
  try {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.evaluate(() => {selected.clear(); taskFocus = null; showAllTasks = false; document.activeElement.blur()});
    await options.close(page);
    await refresh(); await settle();

    // AC1: opens on Lines; a labelled selector lists both devices; header stays Mode-only.
    assert.equal(await page.evaluate(() => state.device), 'wall', 'The map opens on the Lines');
    assert.equal(urlDevice(), null, 'The Lines need no URL parameter');
    assert.equal(await page.locator('#deviceControl').isVisible(), true, 'The Device control is shown with two registered devices');
    assert.equal(await page.locator('label[for="device"]').textContent(), 'Device');
    assert.deepEqual(await page.locator('#device option').evaluateAll(nodes => nodes.map(node => [node.value, node.textContent])), [['wall', 'Lines'], ['panels', 'Light Panels']]);
    assert.equal(await page.locator('#device').inputValue(), 'wall');
    assert.equal(await page.locator('header .control').count(), 1, 'The header keeps the Mode group only');
    assert.equal(await page.locator('.canvas-head #device').count(), 1, 'The selector sits in the wall heading row');
    const linesBefore = await readState();

    // Switching is passive: only state polls, no Locate, no assembly on the Panels.
    writes.length = 0;
    await page.selectOption('#device', 'panels');
    await page.waitForFunction(() => state?.device === 'panels' && document.body.dataset.kind === 'panels');
    await settle();
    assert.equal(urlDevice(), 'panels', 'The chosen device is kept in the URL');
    assert.equal(await page.locator('#device').inputValue(), 'panels');
    assert.equal(await triangles.count(), 18, 'The synthetic Panels draw 18 triangles');
    assert.equal(await page.locator('#wall.prism-scene').count(), 0, 'The Panels are plain SVG, not Prism');
    assert.equal(await page.evaluate(() => window.wallAssembly.snapshot()?.playing ?? false), false, 'No assembly plays on the Panels');
    assert.equal(await page.locator('#lineCount').textContent(), '18 triangles');
    assert.deepEqual(await page.locator('#wall .wall-triangle .tri-number').evaluateAll(nodes => nodes.map(node => node.textContent)), Array.from({length: 18}, (_, i) => String(i + 1)), 'Triangles are numbered in the reader\'s order');
    assert.deepEqual(await page.evaluate(() => [...document.querySelectorAll('#wall .wall-triangle')].map(node => node.dataset.line)), await page.evaluate(() => state.lines.map(line => line.id)), 'Triangle order follows the state');
    assert.equal(await page.locator('#numbersOption').evaluate(node => node.hidden), true, 'The Prism number option is hidden for triangles');
    await page.waitForTimeout(1200);
    assert.deepEqual(writes, [], 'Switching devices and polling send no write');
    assert.equal(await runningAnimations(), 0, 'Triangles show static colours in Work');
    const placed = await page.evaluate(() => state.lines.filter(line => line.task));
    assert.ok(placed.length >= 4, 'The demo places tasks on the Panels');
    const fills = await page.evaluate(() => state.lines.filter(line => line.task).map(line => ({status: state.tasks.find(task => task.id === line.task).status, fill: getComputedStyle(document.querySelector(`#wall .wall-triangle[data-line="${line.id}"] .tri-face`)).fill})));
    const rgb = {working: 'rgb(0, 255, 0)', question: 'rgb(255, 255, 0)', blocked: 'rgb(255, 0, 0)', unread: 'rgb(155, 48, 255)'};
    for (const item of fills) assert.equal(item.fill, rgb[item.status], `A ${item.status} triangle uses its status colour`);
    const idle = await page.evaluate(() => getComputedStyle(document.querySelector(`#wall .wall-triangle[data-line="${state.lines.find(line => !line.task).id}"] .tri-face`)).fill);
    assert.equal(idle, 'rgb(10, 24, 102)', 'An unused triangle shows the Base colour');
    assert.match(await page.locator('#waiting').textContent(), /waiting for a triangle/);

    // Reload keeps the device.
    await page.reload(); await page.waitForSelector('#wall .wall-triangle[data-line]');
    assert.equal(await page.evaluate(() => state.device), 'panels', 'A reload stays on the Panels');
    assert.equal(await page.evaluate(() => window.wallAssembly.snapshot()), null, 'No renderer plays an assembly on the Panels');
    await page.evaluate(() => {try {localStorage.setItem('wall.numbers.showAll', '1')} catch {}});

    // AC4: pointer, modifier and keyboard selection; the context card names triangles.
    const ids = await page.evaluate(() => state.lines.map(line => line.id));
    const numbers = await page.evaluate(() => Object.fromEntries(state.lines.map(line => [line.id, line.number])));
    writes.length = 0;
    await triangle(ids[0]).click(); await settle();
    assert.equal(await page.locator('#selectionTitle').textContent(), `Triangle ${numbers[ids[0]]}`);
    assert.equal(await page.locator('#locate').textContent(), `Locate Triangle ${numbers[ids[0]]}`);
    assert.equal(await page.locator('#locate').isDisabled(), false);
    assert.equal(await triangle(ids[0]).getAttribute('aria-pressed'), 'true');
    assert.match(await page.locator('#taskDetail').textContent(), new RegExp(placed.some(line => line.id === ids[0]) ? '.' : 'No task on this triangle'));
    await triangle(ids[1]).click({modifiers: ['Control']}); await settle();
    assert.equal(await page.locator('#selectionTitle').textContent(), `Triangles ${numbers[ids[0]]}, ${numbers[ids[1]]}`);
    assert.equal(await page.locator('#locate').isDisabled(), true);
    assert.match(await page.locator('#selectionHint').textContent(), /2 triangles selected/);
    await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(() => selected.size), 0);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'wallTitle', 'Escape returns focus to the wall heading');
    assert.equal(await page.locator('#selectionTitle').textContent(), 'Select a triangle');
    await triangle(ids[2]).focus(); await page.keyboard.press('Enter'); await settle();
    assert.equal(await triangle(ids[2]).getAttribute('aria-pressed'), 'true', 'Enter selects a focused triangle');
    await page.waitForTimeout(1100);
    assert.equal(await page.evaluate(() => document.activeElement.dataset.line), ids[2], 'Polling keeps keyboard focus on a triangle');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    assert.deepEqual(writes, [], 'Selection sends no write');
    for (const selector of ['#reservation', '#swap', '#coverageOption']) assert.equal(await page.locator(selector).isVisible(), false, `${selector} is hidden in Classic`);

    // AC4 and AC2: reservation and Shared release address the Panels; the Lines are untouched.
    await options.open(page); await page.locator('#project').click();
    await page.waitForFunction(() => state.settings.style === 'project'); await settle();
    assert.equal(await page.locator('#coverageOption').isVisible(), false, 'Coverage stays hidden for triangles in Project layout');
    await options.close(page);
    await triangle(ids[0]).click(); await triangle(ids[1]).click({modifiers: ['Control']}); await settle();
    assert.equal(await page.locator('#reservation').isVisible(), true, 'Reserved for is offered for triangles');
    assert.equal(await page.locator('#swap').isVisible(), false, 'Swap halves is hidden for triangles');
    await page.locator('#assignProject').selectOption('a');
    await page.waitForFunction(() => state.lines.filter(line => line.project === 'a').length === 2);
    assert.equal(await page.locator('#wall .wall-triangle.reserved').count(), 2, 'Reserved triangles are marked');
    await page.screenshot({path: path.join(root, 'test-results/device-panels-project.png'), fullPage: true});
    await page.locator('#assignProject').selectOption('');
    await page.waitForFunction(() => state.lines.every(line => line.project === null));
    const assignments = writes.filter(item => item.path === '/api/assign');
    assert.equal(assignments.length, 2);
    assert.ok(assignments.every(item => item.body.device === 'panels' && Object.keys(item.body.lines).length === 2), 'Reservation requests name the Panels');
    assert.deepEqual((await readState()).lines.map(line => [line.id, line.project, line.signature]), linesBefore.lines.map(line => [line.id, line.project, line.signature]), 'The Lines keep their own reservations through the Panels edit');
    await page.keyboard.press('Escape');

    // AC4: Locate names the Panels and only an explicit Locate writes.
    writes.length = 0;
    await triangle(ids[3]).click(); await page.locator('#locate').click();
    await page.waitForFunction(() => !refreshing);
    assert.deepEqual(writes.map(item => [item.path, item.body.device, item.body.line]), [['/api/locate', 'panels', ids[3]]], 'Locate names the triangle and the Panels');
    assert.equal(await page.locator('#notice').isVisible(), false, 'The server accepted the Panels Locate');
    await page.keyboard.press('Escape');

    // AC5: orientation applies to the selected device only.
    writes.length = 0;
    await options.open(page); await page.locator('#rotate').click();
    await page.waitForFunction(() => state.settings.rotation === 90);
    await page.locator('#flipX').click(); await page.waitForFunction(() => state.settings.flip_x === 1);
    await options.close(page);
    assert.ok(writes.every(item => item.path === '/api/settings' && item.body.device === 'panels'), 'Orientation requests name the Panels');
    const lines = await readState();
    assert.equal(lines.settings.rotation, linesBefore.settings.rotation, 'The Lines keep their rotation');
    assert.equal(lines.settings.flip_x, linesBefore.settings.flip_x, 'The Lines keep their flip');
    await page.screenshot({path: path.join(root, 'test-results/device-panels-rotated.png'), fullPage: true});
    await page.evaluate(() => action('/api/settings', {rotation: 0, flip_x: 0}));
    await page.waitForFunction(() => state.settings.rotation === 0 && state.settings.flip_x === 0);

    // AC3: mode controls address the Panels; the Lines keep their mode.
    writes.length = 0;
    await page.locator('#quiet').click();
    await page.waitForFunction(() => state.mode === 'quiet' && document.body.dataset.mode === 'quiet');
    assert.deepEqual(writes, [{path: '/api/mode', body: {mode: 'quiet', device: 'panels'}}]);
    assert.match(await page.locator('#readout').textContent(), /Quiet · steady/);
    assert.equal((await readState()).mode, 'work', 'The Lines stay in Work');
    assert.equal((await readState('panels')).mode, 'quiet');
    await page.locator('#work').click(); await page.waitForFunction(() => state.mode === 'work');

    // AC7: reduced motion and the supported widths.
    await page.emulateMedia({reducedMotion: 'reduce'});
    try {
      await triangle(ids[0]).click(); await settle();
      assert.equal(await runningAnimations(), 0, 'Reduced motion runs no triangle animation, even with a selection');
    } finally {await page.emulateMedia({reducedMotion: null})}
    for (const [width, height] of [[1440, 1000], [800, 1000], [390, 844]]) {
      await page.setViewportSize({width, height}); await refresh(); await settle();
      const fit = await page.evaluate(() => {
        const rect = selector => document.querySelector(selector).getBoundingClientRect();
        return {overflow: document.documentElement.scrollWidth > innerWidth, headHeight: rect('.canvas-head').height, wallWidth: rect('#wallHost').width / innerWidth, wallHeight: rect('#wallHost').height, device: rect('#deviceControl').width};
      });
      assert.equal(fit.overflow, false, `${width}px: no horizontal overflow with the Panels`);
      assert.ok(fit.headHeight <= 40, `${width}px: the wall heading with the Device control takes one row (${fit.headHeight}px)`);
      assert.ok(fit.wallWidth >= .45 && fit.wallHeight >= 300, `${width}px: the triangle wall stays dominant`);
      assert.ok(fit.device > 0, `${width}px: the Device control is visible`);
      await page.screenshot({path: path.join(root, `test-results/device-panels-${width}.png`), fullPage: true});
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.keyboard.press('Escape');

    // Back to the Lines. This page load opened on the Panels, so the Lines' first appearance plays the opening assembly once, as on any first load.
    await page.selectOption('#device', 'wall');
    await page.waitForFunction(() => state?.device === 'wall' && document.querySelector('#wall.prism-scene'));
    // Whether it plays follows the browser-local opening preference that earlier modules may have left either way.
    const opening = await page.evaluate(() => {try {return localStorage.getItem('wall.assembly.opening') !== '0'} catch {return true}});
    assert.equal(await page.evaluate(() => window.wallAssembly.snapshot().playing), opening, `The Lines assemble the first time they appear in this page when the opening preference is on (${opening})`);
    await page.waitForFunction(() => {const s = window.wallAssembly.snapshot(); return s && !s.playing && s.progress === 1}, null, {timeout: 5000});
    await settle();
    assert.equal(urlDevice(), null, 'The Lines drop the URL parameter again');
    assert.equal(await page.locator('#wall .wall-line[data-line]').count(), 15);
    // A later round trip replays nothing: the Panels never assemble and the Lines return as they were.
    await page.selectOption('#device', 'panels'); await page.waitForSelector('#wall .wall-triangle[data-line]');
    assert.equal(await page.evaluate(() => window.wallAssembly.snapshot()), null, 'The Panels have no assembly');
    await page.selectOption('#device', 'wall');
    await page.waitForFunction(() => state?.device === 'wall' && document.querySelector('#wall.prism-scene'));
    assert.deepEqual(await page.evaluate(() => {const s = window.wallAssembly.snapshot(); return [s.playing, s.progress]}), [false, 1], 'Returning to the Lines replays no assembly');
    assert.equal(await page.locator('#lineCount').textContent(), '15 Lines');
    assert.equal(await page.locator('#selectionTitle').textContent(), 'Select a Line');
    assert.equal(await page.locator('#numbersOption').evaluate(node => node.hidden), false, 'The Prism number option returns with the Lines');

    // AC2: an unknown device in the URL is rejected, not mapped to the Lines, and the selector recovers.
    await page.goto(base + '/?device=nope');
    await page.waitForFunction(() => document.querySelector('#notice')?.textContent.includes('Unknown device'));
    assert.match(await page.locator('#connection').textContent(), /Disconnected/);
    assert.equal(await page.locator('#wall .wall-line').count(), 0, 'Nothing falls back to the Lines');
    assert.deepEqual(await page.locator('#device option:not([disabled])').evaluateAll(nodes => nodes.map(node => node.value)), ['wall', 'panels'], 'The rejection still lists the registered devices');
    await page.selectOption('#device', 'wall');
    await page.waitForFunction(() => state?.device === 'wall' && document.querySelector('#wall.prism-scene'));
    assert.equal(urlDevice(), null);
    await page.waitForFunction(() => !window.wallAssembly.snapshot()?.playing, null, {timeout: 5000});
    assert.equal(await page.locator('#notice').isVisible(), false, 'The notice clears once a registered device is shown');
    console.log('Device checks passed: selector, URL persistence, passive switching, triangle view, reservations, Locate, orientation, modes, reduced motion, widths and unknown-device recovery.');
  } finally {
    page.off('request', record);
    await page.setViewportSize(viewport);
    await page.emulateMedia({reducedMotion: null});
    await restore();
  }
};
