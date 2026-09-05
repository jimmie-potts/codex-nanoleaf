const assert = require('node:assert/strict');
const path = require('node:path');

module.exports = async function(page, root) {
  // Keep the real geometry/physical IDs, with deterministic API snapshots for UI scenarios.
  const snapshot = await page.evaluate(() => structuredClone(state));
  snapshot.settings = {...snapshot.settings, style: 'project', rotation: 0, flip_x: 0, flip_y: 0};
  snapshot.mode = 'work'; snapshot.pending = null;
  snapshot.lines.forEach(line => {line.project = null; line.task = null});
  const line = number => snapshot.lines.find(item => item.number === number);
  line(2).project = 'a'; line(8).project = 'a'; line(14).project = 'b';
  snapshot.tasks = [
    {id: 'reserved-task', title: 'Task on a reservation', project: 'a', status: 'working', line: line(8).id},
    {id: 'overflow-task', title: 'Task in Shared overflow', project: 'a', status: 'unread', line: line(11).id},
    {id: 'other-task', title: 'Another project task', project: 'b', status: 'blocked', line: line(14).id},
    {id: 'waiting-task', title: 'Waiting project task', project: 'c', status: 'question', line: null},
  ];
  for (const task of snapshot.tasks) {
    if (task.line) snapshot.lines.find(item => item.id === task.line).task = task.id;
  }
  for (const project of snapshot.projects) {
    const tasks = snapshot.tasks.filter(task => task.project === project.id);
    project.assigned = snapshot.lines.filter(item => item.project === project.id).length;
    project.active = tasks.length; project.waiting = tasks.filter(task => !task.line).length;
  }
  const route = request => request.fulfill({json: snapshot});
  await page.route('**/api/state', route);
  const refresh = () => page.evaluate(async () => {while (refreshing) await new Promise(resolve => setTimeout(resolve, 10)); await refresh()});
  const project = id => page.locator(`#projectList .project[data-project="${id}"]`);
  const taskRow = id => page.locator(`#taskList .task[data-task="${id}"]`);
  const mapNumber = number => page.locator(`#wall .number[data-line-id="${line(number).id}"]`);
  const wallLine = number => page.locator(`.wall-line[data-line="${line(number).id}"]`);
  const numbers = locator => locator.locator('.line-badge').evaluateAll(nodes => nodes.map(node => node.dataset.lineNumber));
  try {
    await refresh();
    assert.deepEqual(await numbers(project('a').locator('[data-line-group="reserved"]')), ['2', '8'], 'Reserved badges identify physical Lines, not a count');
    assert.deepEqual(await numbers(project('a').locator('[data-line-group="in-use"]')), ['8', '11'], 'In-use badges follow the project tasks');
    const overflow = project('a').locator(`.line-badge[data-line-id="${line(11).id}"]`);
    assert.match(await overflow.textContent(), /11.*Shared/, 'Overflow is visibly labeled Shared');
    assert.deepEqual(await numbers(page.locator('#projectList .shared-pool').locator('[data-line-group="in-use"]')), ['11']);
    assert.ok((await numbers(page.locator('#projectList .shared-pool').locator('[data-line-group="available"]'))).includes('12'));
    assert.match(await page.locator('#projectList .shared-pool').locator('[data-line-group="in-use"] button').getAttribute('aria-label'), /Notification Service.*Task in Shared overflow/);
    await overflow.click();
    assert.equal(await page.locator('.wall-line.selected').getAttribute('data-line'), line(11).id);

    snapshot.settings.style = 'classic';
    line(8).project = 'b'; // Classic can use a Line saved for a different project.
    await refresh();
    assert.equal(await page.locator('[data-line-group="reserved"]').count(), 0);
    assert.equal(await page.locator('#projectList .shared-pool').count(), 0);
    assert.deepEqual(await numbers(project('a').locator('[data-line-group="in-use"]')), ['8', '11']);
    assert.deepEqual(await numbers(project('b').locator('[data-line-group="in-use"]')), ['14']);
    console.log('Line identification: reserved, occupied, Shared, and Classic badges passed.');

    const writes = [];
    const recordWrite = request => {if (request.method() !== 'GET') writes.push(request.url())};
    page.on('request', recordWrite);
    try {
      assert.deepEqual(await numbers(taskRow('reserved-task')), ['8'], 'Task rows identify their physical Line');
      assert.match(await taskRow('waiting-task').textContent(), /Waiting for a Line/);
      await wallLine(8).click();
      assert.equal(await project('a').evaluate(node => node.classList.contains('selected')), true);
      assert.equal(await project('b').evaluate(node => node.classList.contains('selected')), false, 'Classic selection follows usage, not saved ownership');
      assert.equal(await taskRow('reserved-task').evaluate(node => node.classList.contains('selected')), true);

      snapshot.settings.style = 'project'; line(8).project = 'a'; await refresh();
      await taskRow('overflow-task').locator('.line-badge').press('Enter');
      assert.equal(await wallLine(11).getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('#projectList .shared-pool').evaluate(node => node.classList.contains('selected')), true);
      assert.equal(await project('a').evaluate(node => node.classList.contains('selected')), true);
      assert.equal(await taskRow('overflow-task').evaluate(node => node.classList.contains('selected')), true);
      assert.equal(await taskRow('reserved-task').evaluate(node => node.classList.contains('selected')), false);
      await project('b').locator('[data-line-group="reserved"] button').click({modifiers: ['Control']});
      assert.equal(await page.locator('.wall-line.selected').count(), 2);
      assert.equal(await taskRow('other-task').evaluate(node => node.classList.contains('selected')), true);
      await project('b').locator('[data-line-group="reserved"] button').click({modifiers: ['Control']});
      assert.equal(await page.locator('.wall-line.selected').count(), 1);

      await taskRow('waiting-task').locator('.task-title').click();
      assert.equal(await page.locator('.wall-line.selected').count(), 0, 'A waiting task must clear stale Line selection');
      assert.equal(await project('c').evaluate(node => node.classList.contains('selected')), true);
      assert.equal(await taskRow('waiting-task').evaluate(node => node.classList.contains('selected')), true);
      await wallLine(2).press('Enter');
      assert.equal(await project('a').evaluate(node => node.classList.contains('selected')), true, 'An idle reserved Line selects its owner');
      assert.equal(await page.locator('#taskList .task.selected').count(), 0);
      await page.locator('#clear').click();
      assert.equal(await page.locator('.line-badge.selected, .project.selected, .task.selected').count(), 0);
      assert.deepEqual(writes, [], 'Selecting Lines and tasks must not issue write requests');
      assert.deepEqual(await page.evaluate(() => state.tasks), snapshot.tasks, 'Selection preserves task state, including unread status');
    } finally {page.off('request', recordWrite)}
    console.log('Line identification: task placement, waiting, local selection, and associations passed.');

    await wallLine(8).click();
    assert.equal(await page.locator('#locate').textContent(), 'Locate Line 8', 'Locate names the selected physical Line');
    await wallLine(2).click({modifiers: ['Shift']});
    await wallLine(11).click({modifiers: ['Control']});
    assert.equal(await page.locator('#selectionTitle').textContent(), 'Lines 2, 8, 11');
    assert.equal(await page.locator('#locate').isDisabled(), true);
    snapshot.pending = {lines: {[line(8).id]: {project: 'a'}, [line(2).id]: {signature: 1}}, tasks: {'overflow-task': 'b'}, settings: {}};
    await refresh();
    assert.match(await page.locator('#busy').textContent(), /Line 8 → Notification Service/);
    assert.match(await page.locator('#busy').textContent(), /Line 2.*half swap/);
    assert.match(await page.locator('#busy').textContent(), /Line 11.*Task in Shared overflow → Daily Trader/);
    snapshot.pending.tasks = {'waiting-task': 'a', 'reserved-task': null}; await refresh();
    assert.match(await page.locator('#busy').textContent(), /Waiting project task.*Waiting for a Line.*→ Notification Service/);
    assert.match(await page.locator('#busy').textContent(), /Line 8.*Task on a reservation → Use Codex assignment/);
    snapshot.pending = null;

    const locateRequests = [];
    const locateRoute = request => {locateRequests.push(request.request().postDataJSON());return request.fulfill({json: {ok: true}})};
    await page.route('**/api/locate', locateRoute);
    try {
      for (const mode of ['free', 'quiet', 'work']) {
        snapshot.mode = mode; await refresh(); await wallLine(8).click();
        assert.equal(await page.locator('#locate').textContent(), 'Locate Line 8');
        assert.equal(await page.locator('#locate').isDisabled(), mode === 'free');
        if (mode !== 'free') {
          const request = page.waitForRequest('**/api/locate');
          await page.locator('#locate').click(); await request;
        }
      }
      assert.deepEqual(locateRequests, [{line: line(8).id}, {line: line(8).id}], 'Only explicit Work/Quiet Locate clicks target the physical ID');
    } finally {await page.unroute('**/api/locate', locateRoute)}
    snapshot.settings.style = 'classic'; line(8).project = 'b'; await refresh();
    assert.match(await wallLine(8).getAttribute('aria-label'), /Notification Service/);
    assert.doesNotMatch(await wallLine(8).getAttribute('aria-label'), /Daily Trader/, 'Classic Line labels use its current task project');
    console.log('Line identification: inspector, numbered pending edits, and explicit Locate passed.');

    const identity = Object.fromEntries(snapshot.lines.map(item => [item.id, String(item.number)]));
    const checkNumbers = async () => {
      assert.deepEqual(await page.locator('#wall .number').evaluateAll(nodes => Object.fromEntries(nodes.map(node => [node.dataset.lineId, node.textContent]))), identity);
      for (const badge of await page.locator('.line-badge').evaluateAll(nodes => nodes.map(node => ({id: node.dataset.lineId, number: node.dataset.lineNumber, text: node.textContent})))) {
        assert.equal(badge.number, identity[badge.id]);
        assert.match(badge.text, new RegExp('^(Line )?' + identity[badge.id] + '( · Shared)?$'));
      }
    };
    const settingsRoute = request => {Object.assign(snapshot.settings, request.request().postDataJSON());return request.fulfill({json: {ok: true}})};
    await page.route('**/api/settings', settingsRoute);
    try {
      for (const id of ['rotate', 'rotate', 'rotate', 'rotate', 'flipX', 'flipY', 'project', 'classic']) {
        const response = page.waitForResponse('**/api/settings');
        await page.locator('#'+id).click(); await response; await refresh(); await checkNumbers();
        assert.equal(await wallLine(8).getAttribute('aria-pressed'), 'true');
      }
    } finally {await page.unroute('**/api/settings', settingsRoute)}
    snapshot.settings = {...snapshot.settings, style: 'project', rotation: 0, flip_x: 0, flip_y: 0};
    line(8).project = 'a'; await refresh();
    const reservedBadge = project('a').locator(`[data-line-group="reserved"] [data-line-id="${line(8).id}"]`);
    await reservedBadge.focus(); await page.waitForTimeout(1100);
    assert.equal(await reservedBadge.evaluate(node => document.activeElement === node), true, 'Unchanged polling preserves badge focus');
    snapshot.projects.find(item => item.id === 'b').name = 'Daily Trader & research'; await refresh();
    assert.equal(await reservedBadge.evaluate(node => document.activeElement === node), true, 'A project update must not drop focus from another numbered badge');
    assert.match(await wallLine(14).getAttribute('aria-label'), /Daily Trader & research/, 'Map association labels refresh when a project is renamed');

    await taskRow('reserved-task').locator('.line-badge').focus();
    snapshot.tasks[0].line = line(12).id; line(8).task = null; line(12).task = 'reserved-task'; await refresh();
    assert.deepEqual(await numbers(taskRow('reserved-task')), ['12']);
    assert.equal(await taskRow('reserved-task').locator('.line-badge').evaluate(node => document.activeElement === node), true, 'Task placement updates preserve its badge focus');
    assert.equal(await taskRow('reserved-task').evaluate(node => node.classList.contains('selected')), false, 'Line selection follows the current occupant');
    assert.equal(await project('a').evaluate(node => node.classList.contains('selected')), true, 'The now idle reservation stays associated');
    await wallLine(11).click();
    snapshot.tasks[1].project = 'b'; await refresh();
    assert.equal(await project('a').evaluate(node => node.classList.contains('selected')), false);
    assert.equal(await project('b').evaluate(node => node.classList.contains('selected')), true);
    await taskRow('waiting-task').locator('.task-title').click();
    snapshot.tasks[3].line = line(13).id; line(13).task = 'waiting-task'; await refresh();
    assert.equal(await wallLine(13).getAttribute('aria-pressed'), 'true', 'A focused waiting task can receive a Line');
    assert.deepEqual(await numbers(taskRow('waiting-task')), ['13']);
    snapshot.tasks[3].line = null; line(13).task = null; await refresh();
    assert.match(await taskRow('waiting-task').textContent(), /Waiting for a Line/);
    await page.locator('#waiting .task[data-task="waiting-task"] .task-title').press('Enter');
    snapshot.tasks[3].line = line(13).id; line(13).task = 'waiting-task'; await refresh();
    assert.equal(await taskRow('waiting-task').locator('.task-title').evaluate(node => document.activeElement === node), true, 'A placed task carries focus from Waiting to its title in Tasks');
    await taskRow('waiting-task').locator('.task-title').press('Enter');
    assert.equal(await wallLine(13).getAttribute('aria-pressed'), 'true');
    snapshot.tasks[3].line = null; line(13).task = null; await refresh();
    await checkNumbers();

    const color = project('a').locator('input[type=color]'); await color.focus();
    const colorNode = await color.elementHandle();
    snapshot.tasks[0].line = line(2).id; line(12).task = null; line(2).task = 'reserved-task'; await refresh();
    assert.deepEqual(await numbers(project('a').locator('[data-line-group="in-use"]')), ['2'], 'Color focus must not freeze project placements');
    assert.deepEqual(await numbers(page.locator('.shared-pool [data-line-group="in-use"]')), ['11']);
    assert.equal(await colorNode.evaluate(node => node.isConnected && document.activeElement === node), true, 'Keep the active color control itself while updating its badges');
    await refresh();
    assert.deepEqual(await numbers(project('a').locator('[data-line-group="in-use"]')), ['2']);
    await colorNode.dispose();
    const sharedBadge = page.locator(`.shared-pool .line-badge[data-line-id="${line(12).id}"]`);
    await sharedBadge.focus();
    snapshot.tasks[0].line = line(12).id; line(2).task = null; line(12).task = 'reserved-task'; await refresh();
    assert.equal(await sharedBadge.evaluate(node => document.activeElement === node), true, 'Shared focus follows the physical Line from Available to In use');
    snapshot.tasks[0].line = line(2).id; line(12).task = null; line(2).task = 'reserved-task'; await refresh();
    assert.equal(await sharedBadge.evaluate(node => document.activeElement === node), true, 'Shared focus follows the physical Line back to Available');
    await sharedBadge.press('Enter');
    assert.equal(await wallLine(12).getAttribute('aria-pressed'), 'true');

    await wallLine(11).click();
    snapshot.pending = {lines: {[line(8).id]: {project: 'a'}}, tasks: {}, settings: {}}; await refresh();
    for (const [name, width, height] of [['desktop', 1440, 1000], ['compact', 800, 1000], ['mobile', 390, 844]]) {
      await page.setViewportSize({width, height});
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'No horizontal page overflow at '+width+'px');
      assert.ok(await page.locator('.number').first().evaluate(node => parseFloat(getComputedStyle(node).fontSize) * node.getScreenCTM().a >= 11), 'Physical numbers stay legible when the map shrinks');
      await mapNumber(8).click({timeout: 2000});
      assert.equal(await wallLine(8).getAttribute('aria-pressed'), 'true', 'The displayed map number is clickable');
      await page.locator('#projectList').evaluate(node => {node.scrollTop = 0});
      await page.screenshot({path: path.join(root, `test-results/line-identification-${name}.png`), fullPage: true});
    }
    const numberWrites = [];
    const recordNumberWrite = request => {if (request.method() !== 'GET') numberWrites.push(request.url())};
    page.on('request', recordNumberWrite);
    try {
      for (const width of [1440, 800, 390]) {
        await page.setViewportSize({width, height: 844});
        for (const rotation of [0, 90, 180, 270]) for (const flip of [0, 1]) {
          // Four rotations with/without reflection cover all eight orientations,
          // including those produced by Flip V or by combining both flips.
          snapshot.settings = {...snapshot.settings, rotation, flip_x: flip, flip_y: 0}; await refresh();
          for (const item of snapshot.lines) {
            const number = mapNumber(item.number); await number.scrollIntoViewIfNeeded();
            const box = await number.boundingBox();
            await page.mouse.click(box.x+box.width/2, box.y+box.height/2);
            assert.equal(await page.locator('.wall-line.selected').getAttribute('data-line'), item.id, `Clicking number ${item.number} at ${width}px, rotation ${rotation}, flip ${flip} selects that physical Line`);
          }
        }
      }
      assert.deepEqual(numberWrites, [], 'Every map-number click remains local');
    } finally {page.off('request', recordNumberWrite)}
    console.log('Line identification: all 360 map-number clicks across sizes and orientations passed.');
    console.log('Line identification: stable numbers, polling, moved/waiting tasks, and responsive layout passed.');
  } finally {
    await page.unroute('**/api/state', route);
    await refresh();
  }
};
