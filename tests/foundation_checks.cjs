const assert = require('node:assert/strict');

// Issue #22: layout, status visibility, pending edits, focus, and mode foundations.
module.exports = async function(page, root) {
  const refresh = () => page.evaluate(async () => {while (refreshing) await new Promise(resolve => setTimeout(resolve, 10)); await refresh()});
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const rect = selector => page.evaluate(s => {const r = document.querySelector(s).getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height}}, selector);
  const rowsVisible = (rows, container) => page.evaluate(([r, c]) => {
    const limit = Math.min(document.querySelector(c).getBoundingClientRect().bottom, innerHeight);
    return [...document.querySelectorAll(r)].map(node => [node.textContent.trim().slice(0, 24), Math.round(node.getBoundingClientRect().bottom), Math.round(limit)]).filter(([, bottom, max]) => bottom > max + 1);
  }, [rows, container]);
  const failures = [];
  const check = async (name, fn) => {try {await fn()} catch (error) {failures.push(`${name} -> ${error.message.split('\n')[0]}`)}};
  await page.setViewportSize({width: 1440, height: 1000});
  await page.evaluate(async () => {await action('/api/settings', {style: 'project'}); await action('/api/mode', {mode: 'work'})});
  await page.waitForFunction(() => state.settings.style === 'project' && state.mode === 'work');
  await settle();

  await check('AC1: nothing clips at 1440x1000 with three projects and five tasks', async () => {
  assert.deepEqual(await rowsVisible('#projectList .project', '#projectList'), [], 'Every project row is visible without scrolling at 1440x1000');
  assert.deepEqual(await rowsVisible('#taskList .task', '#taskList'), [], 'Every task row is visible without scrolling at 1440x1000');

  });
  await check('AC2: status color carries into task rows from one token source', async () => {
  const badges = await page.locator('#taskList .badge[data-status]').evaluateAll(nodes => nodes.map(node => [node.dataset.status, getComputedStyle(node).color]));
  assert.deepEqual([...new Set(badges.map(([status]) => status))].sort(), ['blocked', 'question', 'unread', 'working'], 'Task rows carry data-status for every status');
  assert.equal(new Set(badges.map(([, color]) => color)).size, 4, 'Each status renders a distinct badge color');

  });
  await check('AC3: pending edits appear beside the wall, above the fold, with the same text', async () => {
  await page.evaluate(() => {state.pending = {settings: {}, lines: {[state.lines.find(l => l.number === 8).id]: {project: 'a'}}, tasks: {}}; render()});
  assert.equal(await page.locator('.canvas #busy').count(), 1, 'Pending text renders inside the wall canvas');
  assert.equal(await page.locator('#busy').isVisible(), true);
  assert.match(await page.locator('#busy').textContent(), /Line 8 → Notification Service/);
  assert.ok((await rect('#busy')).bottom <= 1000, 'Pending banner is visible without scrolling');
  await refresh();
  assert.equal(await page.locator('#busy').isVisible(), false, 'No banner without a pending edit');

  });
  await check('AC4: toggles announce state, focus differs from selection, disabled select looks disabled', async () => {
  for (const id of ['classic', 'project', 'work', 'quiet', 'free', 'flipX', 'flipY'])
    assert.ok(['true', 'false'].includes(await page.locator('#' + id).getAttribute('aria-pressed')), `#${id} exposes aria-pressed`);
  const ids = await page.locator('.wall-line').evaluateAll(nodes => nodes.map(node => node.dataset.line));
  await page.locator(`[data-line="${ids[0]}"]`).click();
  await page.locator(`[data-line="${ids[0]}"]`).click({modifiers: ['Control']});
  assert.equal(await page.locator('.wall-line.selected').count(), 0);
  await page.waitForTimeout(250); // let the 150 ms stroke transition settle
  const [deselected, selectionColor] = await page.evaluate(id => {
    const probe = document.createElement('span'); probe.style.color = 'var(--selection)'; document.body.append(probe);
    const color = getComputedStyle(probe).color; probe.remove();
    return [getComputedStyle(document.querySelector(`[data-line="${id}"] .outline`)).stroke, color];
  }, ids[0]);
  assert.notEqual(deselected, selectionColor, 'A focused but deselected Line shows no selection ring');
  await page.evaluate(() => action('/api/settings', {style: 'classic'}));
  await page.waitForFunction(() => state.settings.style === 'classic');
  assert.equal(await page.locator('#coverage').isDisabled(), true);
  assert.ok(parseFloat(await page.locator('#coverage').evaluate(node => getComputedStyle(node).opacity)) < 1, 'A disabled coverage select looks disabled');
  await page.evaluate(() => action('/api/settings', {style: 'project'}));
  await page.waitForFunction(() => state.settings.style === 'project');

  });
  await check('AC5: the mode reaches the wall', async () => {
  await page.locator('#free').click(); await page.waitForFunction(() => state.mode === 'free');
  assert.equal(await page.evaluate(() => document.body.dataset.mode), 'free');
  assert.notEqual(await page.locator('#wall').evaluate(node => getComputedStyle(node).filter), 'none', 'Free dims the wall');
  await page.locator('#work').click(); await page.waitForFunction(() => state.mode === 'work');
  assert.equal(await page.locator('#wall').evaluate(node => getComputedStyle(node).filter), 'none', 'Work shows the wall at full strength');

  });
  await check('AC6: one toolbar row holding Layout, Mode, and Animation coverage', async () => {
  assert.ok((await rect('header')).height <= 60, 'Header is a single toolbar row at 1440px');
  assert.equal(await page.locator('header #coverage').count(), 1, 'Animation coverage sits in the toolbar');

  });
  await check('AC7: number tags never overlap; Rotate and Flip stay on one row at 390px', async () => {
  for (const width of [1440, 800, 390]) {
    await page.setViewportSize({width, height: width === 1440 ? 1000 : 844}); await settle();
    const overlaps = await page.locator('#wall .number').evaluateAll(nodes => {
      const boxes = nodes.map(node => [node.textContent, node.getBoundingClientRect()]), hits = [];
      for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
        const [a, ra] = boxes[i], [b, rb] = boxes[j];
        if (ra.left < rb.right && rb.left < ra.right && ra.top < rb.bottom && rb.top < ra.bottom) hits.push(a + '/' + b);
      }
      return hits;
    });
    assert.deepEqual(overlaps, [], `No overlapping map numbers at ${width}px`);
  }
  const tops = await Promise.all(['#rotate', '#flipX', '#flipY'].map(async id => Math.round((await rect(id)).top)));
  assert.equal(new Set(tops).size, 1, 'Rotate, Flip H, and Flip V share one row at 390px');

  });
  await check('AC9: a rejected project override never lingers in the inspector select', async () => {
    await page.setViewportSize({width: 1440, height: 1000}); await settle();
    const snapshot = await page.evaluate(() => structuredClone(state));
    snapshot.tasks.forEach(task => {task.started = snapshot.now - 7200; task.manual = null});
    const stateRoute = request => request.fulfill({json: snapshot});
    const rejectRoute = request => request.fulfill({status: 400, json: {error: 'Unknown task.'}});
    await page.route('**/api/state', stateRoute); await page.route('**/api/task', rejectRoute);
    try {
      await refresh();
      const placed = snapshot.tasks.find(task => task.line);
      await page.locator(`[data-line="${placed.line}"]`).click();
      const override = page.locator('[aria-label="Task project override"]');
      await override.focus(); await override.selectOption('b');
      await page.waitForFunction(() => document.querySelector('#notice').textContent.includes('Unknown task'));
      await override.blur(); await refresh(); await refresh();
      assert.equal(await override.inputValue(), '', 'A rejected override returns the select to the saved assignment');
    } finally {await page.unroute('**/api/task', rejectRoute); await page.unroute('**/api/state', stateRoute); await page.evaluate(() => {errorUntil = 0}); await refresh()}
  });
  await check('AC8: the connection indicator holds still between unchanged polls', async () => {
  await page.setViewportSize({width: 1440, height: 1000}); await settle();
  const before = await page.locator('#connection').textContent();
  await page.waitForTimeout(1100);
  assert.equal(await page.locator('#connection').textContent(), before, 'Connection text does not churn between unchanged polls');
  });
  if (failures.length) throw Error('Foundation checks failed:\n' + failures.join('\n'));
  console.log('Foundation checks passed: clipping, status color, pending banner, toggles, focus, mode, toolbar, numbers, and connection text.');
};
