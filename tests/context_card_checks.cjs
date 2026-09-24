const assert = require('node:assert/strict');
const path = require('node:path');
const options = require('./wall_options.cjs');

// Issue #135: one context card, a Mode-only header, Layout in Options,
// Project-only editing controls, Escape and empty-canvas clearing, Free-only Locate hint.
module.exports = async function(page, root) {
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const refresh = () => page.evaluate(async () => {while (refreshing) await new Promise(resolve => setTimeout(resolve, 10)); await refresh()});
  const snapshot = await page.evaluate(() => structuredClone(state));
  snapshot.settings = {...snapshot.settings, style: 'classic', coverage: 'whole', rotation: 0, flip_x: 0, flip_y: 0};
  snapshot.mode = 'work'; snapshot.pending = null; snapshot.mode_pending = false;
  snapshot.lines.forEach(line => {line.project = null; line.task = null; line.signature = 0});
  const lines = [...snapshot.lines].sort((a, b) => a.number - b.number);
  const [placed, second, third, waiting] = snapshot.tasks;
  assert.ok(waiting, 'The demo fixture supplies at least four tasks');
  placed.line = lines[0].id; lines[0].task = placed.id; placed.project = snapshot.projects[0].id;
  second.line = lines[1].id; lines[1].task = second.id;
  third.line = lines[2].id; lines[2].task = third.id;
  waiting.line = null;
  snapshot.tasks.slice(4).forEach(task => {task.line = null});
  lines[3].project = snapshot.projects[0].id; // a reservation that only Project layout shows
  const reservedName = snapshot.projects[0].name;
  let current = snapshot;
  const route = request => request.fulfill({json: current});
  const settingsRoute = request => {Object.assign(current.settings, request.request().postDataJSON()); return request.fulfill({json: {ok: true}})};
  const assigned = [];
  const assignRoute = request => {const body = request.request().postDataJSON(); assigned.push(body); for (const [id, edit] of Object.entries(body.lines || {})) Object.assign(current.lines.find(line => line.id === id), edit); return request.fulfill({json: {ok: true}})};
  const writes = [];
  const record = request => {if (request.method() !== 'GET') writes.push(new URL(request.url()).pathname)};
  const viewport = page.viewportSize();
  const wallLine = line => page.locator(`#wall .wall-line[data-line="${line.id}"]`);
  const isOpen = () => page.locator('#wallOptions').evaluate(node => node.open);
  const card = page.locator('#contextCard');
  const visible = selector => page.locator(selector).isVisible();
  const titleCount = title => card.evaluate((node, text) => node.textContent.split(text).length - 1, title);
  await page.route('**/api/state', route);
  await page.route('**/api/settings', settingsRoute);
  await page.route('**/api/assign', assignRoute);
  page.on('request', record);
  try {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.evaluate(() => {selected.clear(); taskFocus = null; showAllTasks = false; document.activeElement.blur()});
    await options.close(page);
    await refresh(); await settle();

    // Header composition and the Layout group.
    assert.equal(await page.locator('header #classic, header #project, header #coverage').count(), 0, 'Layout and Coverage have left the header');
    assert.equal(await page.locator('header .control').count(), 1, 'The header keeps the Mode group only');
    assert.equal(await page.locator('#wallOptions #classic, #wallOptions #project, #wallOptions #coverage').count(), 3, 'Layout and Coverage live in Options');
    assert.equal(await page.locator('#inspector > .card').count(), 2, 'The inspector holds one context card and the task card');
    assert.equal(await page.getByRole('button', {name: 'Clear selection'}).count(), 0, 'No Clear selection button');

    // Classic: one card, task once, Locate only.
    await wallLine(lines[0]).click(); await refresh(); await settle();
    assert.equal(await page.locator('#selectionTitle').textContent(), `Line ${lines[0].number}`);
    assert.equal(await titleCount(placed.title), 1, 'The task title appears once in the context card');
    assert.equal(await visible('#selectionHint'), false, 'A Classic Line with a task needs no hint');
    assert.match(await card.textContent(), new RegExp(reservedName), 'The task project is shown');
    for (const selector of ['#assignProject', '#assign', '#swap', '#locateHint']) assert.equal(await visible(selector), false, `${selector} is hidden in Classic`);
    assert.equal(await page.getByRole('combobox', {name: 'Task project override'}).count(), 0, 'No override in Classic');
    assert.equal(await page.locator('#locate').isVisible(), true);
    assert.equal(await page.locator('#locate').isDisabled(), false);
    assert.equal(await page.locator('#locate').textContent(), `Locate Line ${lines[0].number}`);
    await wallLine(lines[3]).click(); await refresh(); await settle();
    assert.match(await page.locator('#taskDetail').textContent(), /No task on this Line/, 'A Line without a task says so');
    assert.equal(await visible('#selectionHint'), false, 'Classic shows no reservation hint for an idle Line');

    // Escape clears; Options takes Escape first.
    await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(() => selected.size), 0, 'Escape clears the selection');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'wallTitle', 'Focus returns to the wall heading');
    assert.equal(await page.locator('#selectionTitle').textContent(), 'Select a Line');
    assert.equal(await visible('#selectionHint'), true, 'With nothing selected the card explains how to select');
    await wallLine(lines[0]).click();
    await options.open(page);
    await page.keyboard.press('Escape');
    assert.equal(await isOpen(), false, 'Escape closes Options first');
    assert.equal(await page.evaluate(() => selected.size), 1, 'The selection survives the menu closing');
    await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(() => selected.size), 0, 'The next Escape clears the selection');

    // Empty canvas click clears.
    await wallLine(lines[0]).click();
    const host = await page.locator('#wallHost').boundingBox();
    await page.mouse.click(host.x + 12, host.y + host.height - 12);
    assert.equal(await page.evaluate(() => selected.size), 0, 'A click on empty canvas clears the selection');

    // Several Lines and a waiting task.
    await wallLine(lines[0]).click(); await wallLine(lines[1]).click({modifiers: ['Control']});
    assert.equal(await page.locator('#selectionTitle').textContent(), `Lines ${lines[0].number}, ${lines[1].number}`);
    assert.equal(await page.locator('#locate').isDisabled(), true);
    assert.match(await page.locator('#taskDetail').textContent(), /Select one Line/);
    await page.locator(`#taskList [data-task="${waiting.id}"] .task-title`).click(); await refresh();
    assert.equal(await page.locator('#selectionTitle').textContent(), 'Waiting for a Line');
    assert.equal(await visible('#selectionBody'), false, 'A waiting task has no Line actions');
    assert.equal(await titleCount(waiting.title), 1);
    await page.keyboard.press('Escape');

    // Free: Locate disabled with its explanation; Work hides it.
    current.mode = 'free'; await refresh(); await settle(); await wallLine(lines[0]).click();
    assert.equal(await page.locator('#locate').isDisabled(), true);
    assert.equal(await visible('#locateHint'), true);
    assert.match(await page.locator('#locateHint').textContent(), /Switch to Work or Quiet/);
    current.mode = 'work'; await refresh(); await settle();
    assert.equal(await visible('#locateHint'), false);
    await page.screenshot({path: path.join(root, 'test-results/context-card-classic.png'), fullPage: true});

    // Project layout from Options reveals the editing controls.
    writes.length = 0;
    await options.open(page);
    assert.equal(await page.getByRole('group', {name: 'Layout'}).count(), 1, 'The Layout group is labelled');
    assert.equal(await visible('#coverage'), false, 'Coverage is hidden in Classic');
    await page.locator('#project').click();
    await page.waitForFunction(() => state.settings.style === 'project'); await settle();
    assert.deepEqual(writes, ['/api/settings'], 'Choosing a layout sends only the settings request');
    assert.equal(await visible('#coverage'), true, 'Coverage appears in Project layout');
    await options.close(page);
    await wallLine(lines[0]).click(); await refresh(); await settle();
    assert.equal(await page.locator('#selectionHint').textContent(), 'Shared pool');
    for (const selector of ['#assignProject', '#assign', '#swap']) assert.equal(await visible(selector), true, `${selector} shows in Project layout`);
    assert.equal(await page.locator('#assign').textContent(), 'Reserve');
    assert.equal(await page.getByRole('combobox', {name: 'Task project override'}).count(), 1, 'The override shows in Project layout');
    await wallLine(lines[3]).click();
    assert.equal(await page.locator('#selectionHint').textContent(), `Reserved for ${reservedName}`);
    await wallLine(lines[0]).click();
    await page.locator('#assignProject').selectOption(snapshot.projects[1].id);
    await page.locator('#assign').click(); await page.waitForFunction(id => state.lines.find(line => line.id === id)?.project, lines[0].id);
    assert.deepEqual(assigned.at(-1), {lines: {[lines[0].id]: {project: snapshot.projects[1].id}}}, 'Reserve sends the existing assignment request');
    await page.screenshot({path: path.join(root, 'test-results/context-card-project.png'), fullPage: true});
    await options.open(page); await page.locator('#classic').click();
    await page.waitForFunction(() => state.settings.style === 'classic'); await settle();
    await options.close(page);
    for (const selector of ['#assignProject', '#assign', '#swap']) assert.equal(await visible(selector), false, `${selector} hides again in Classic`);
    assert.equal(await page.getByRole('combobox', {name: 'Task project override'}).count(), 0);
    assert.deepEqual(writes, ['/api/settings', '/api/assign', '/api/settings'], 'Only layout changes and Reserve wrote');

    for (const [width, height] of [[800, 1000], [390, 844]]) {
      await page.setViewportSize({width, height}); await refresh(); await settle();
      assert.equal(await page.locator('header #classic, header #project, header #coverage').count(), 0, `${width}px: the header holds no layout control`);
      assert.equal(await page.locator('header .control').count(), 1, `${width}px: the header keeps Mode only`);
      await wallLine(lines[0]).click();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${width}px: the context card fits the page`);
      if (width === 800) await page.keyboard.press('Escape');
    }
    await page.screenshot({path: path.join(root, 'test-results/context-card-narrow.png'), fullPage: true});
    await page.keyboard.press('Escape');
    console.log('Context card checks passed: Mode-only header, Layout in Options, one card, Project-only editing, Escape and canvas clearing, Free-only Locate hint.');
  } finally {
    page.off('request', record);
    await page.unroute('**/api/assign', assignRoute);
    await page.unroute('**/api/settings', settingsRoute);
    await page.unroute('**/api/state', route);
    await options.close(page);
    await page.setViewportSize(viewport);
    await page.evaluate(() => {selected.clear(); taskFocus = null; document.activeElement.blur()});
    await refresh();
  }
};
