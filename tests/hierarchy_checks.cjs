const assert = require('node:assert/strict');
const path = require('node:path');
const options = require('./wall_options.cjs');

// Issue #78: the default screen leads with the wall and live status; secondary
// controls sit under one labelled Options menu; each count and hint has one home.
module.exports = async function(page, root) {
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const refresh = () => page.evaluate(async () => {while (refreshing) await new Promise(resolve => setTimeout(resolve, 10)); await refresh()});
  const isOpen = () => page.locator('#wallOptions').evaluate(node => node.open);
  const original = await page.evaluate(() => structuredClone(state));
  // Dense data: 20 current projects with long names, 72 tasks with long titles, Project layout with reservations.
  const dense = structuredClone(original);
  dense.settings = {...dense.settings, style: 'project', rotation: 0, flip_x: 0, flip_y: 0};
  dense.mode = 'work'; dense.pending = null; dense.mode_pending = false;
  dense.projects = Array.from({length: 20}, (_, i) => ({id: 'proj-' + i, name: (i % 3 ? 'Project ' : 'A very long project name that keeps going ') + String(i).padStart(2, '0'), color: '#' + ((i * 40 + 60) % 256).toString(16).padStart(2, '0') + '88ff', active: 0, waiting: 0, assigned: 0}));
  dense.tasks = Array.from({length: 72}, (_, i) => ({id: 'task-' + String(i).padStart(2, '0'), title: (i % 4 ? 'Task ' : 'A long retained task title with project context that truncates in the compact grid ') + i, project: 'proj-' + (i % 20), status: i < 2 ? 'blocked' : i < 5 ? 'question' : i < 9 ? 'working' : 'unread', line: i < 15 ? dense.lines[i].id : null, started: 1000}));
  dense.lines.forEach((line, i) => {line.task = dense.tasks[i]?.id || null; line.project = i < 4 ? 'proj-' + i : null});
  const empty = structuredClone(dense);
  empty.projects = []; empty.tasks = []; empty.lines.forEach(line => {line.task = null; line.project = null});
  let current = dense;
  const route = request => request.fulfill({json: current});
  const writes = [];
  const record = request => {if (request.method() !== 'GET') writes.push(new URL(request.url()).pathname)};
  const viewport = page.viewportSize();
  const summary = page.locator('#wallOptions > summary');
  const menuControls = ['classic', 'project', 'coverage', 'showNumbers', 'rotate', 'flipX', 'flipY', 'replay', 'assemblyOnOpen', 'assemblyOnEntry']; // the dense fixture is Project layout, so Coverage is in the tab order
  const geometry = () => page.evaluate(() => {
    const rect = selector => document.querySelector(selector).getBoundingClientRect();
    const head = rect('.canvas-head'), wall = rect('#wallHost');
    return {overflow: document.documentElement.scrollWidth > innerWidth, headHeight: head.height, wallWidth: wall.width / innerWidth, wallHeight: wall.height, wallTop: wall.top,
      readoutBottom: rect('#readout').bottom, connectionBottom: rect('#connection').bottom, workBottom: rect('#work').bottom, menuOpen: document.querySelector('#wallOptions').open};
  });
  await page.route('**/api/state', route);
  page.on('request', record);
  try {
    await page.setViewportSize({width: 1440, height: 1000});
    await page.evaluate(() => {
      selected.clear(); taskFocus = null; showAllTasks = false; showSavedProjects = false; document.activeElement.blur();
      try {localStorage.removeItem('wall.numbers.showAll'); localStorage.removeItem('wall.assembly.opening'); localStorage.removeItem('wall.assembly.entry')} catch {}
      showAllNumbers = false; syncNumberControl(); $('assemblyOnOpen').checked = true; $('assemblyOnEntry').checked = true;
    });
    await refresh(); await settle();

    // Structure: one labelled Options menu holds every secondary control and starts closed.
    assert.equal(await page.locator('details#wallOptions').count(), 1, 'One Options menu sits above the wall');
    assert.equal((await summary.textContent()).trim(), 'Options', 'The menu control is labelled Options');
    assert.equal(await isOpen(), false, 'Options starts closed');
    for (const id of menuControls) {
      assert.equal(await page.locator('#wallOptions #' + id).count(), 1, `#${id} lives inside the Options menu`);
      assert.equal(await page.locator('#' + id).isVisible(), false, `#${id} is hidden while Options is closed`);
    }
    assert.doesNotMatch(await page.locator('.canvas-head').textContent(), /Click to select|Ctrl/, 'The wall heading carries no selection hint');
    assert.equal(await page.locator('#projects .aside-head .hint').count(), 0, 'The Projects heading carries no hint');
    assert.match(await page.locator('#selectionHint').textContent(), /Ctrl\/⌘ or Shift/, 'The selection card owns the multi-select instruction');
    assert.match(await page.locator('footer').textContent(), /does not mark a task read/, 'The footer keeps the read-ownership note');

    // One home for each count.
    assert.equal(await page.locator('#lineCount').textContent(), '15 Lines');
    assert.equal(await page.locator('#taskCount').textContent(), '72');
    assert.equal(await page.locator('#readout').textContent(), 'Work · indicators on · 2 blocked · 3 question', 'The readout names the mode note and the alerts only');
    assert.equal(await page.locator('#readout #wallNote').count(), 1, 'The mode note lives in the readout');
    assert.match(await page.locator('#wallNote').getAttribute('title'), /inward light flow/, 'The mode note keeps its explanation');
    assert.equal(await page.locator('#taskStatusCounts').textContent(), '2 blocked · 3 question · 4 working · 63 unread');
    assert.equal(await page.locator('#waiting').textContent(), '57 waiting for a Line');
    assert.equal(await page.locator('#taskSummary').textContent(), '15 shown');
    assert.equal(await page.locator('#taskCard .card-head #showAllTasks').count(), 1, 'The full-list control sits beside the Tasks heading');

    // Keyboard journey through the menu, passive throughout.
    writes.length = 0;
    await summary.focus(); await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Tab');
    const ring = await summary.evaluate(node => ({focused: node === document.activeElement, ...(({outlineStyle, outlineColor}) => ({outlineStyle, outlineColor}))(getComputedStyle(node))}));
    assert.deepEqual(ring, {focused: true, outlineStyle: 'solid', outlineColor: 'rgb(255, 255, 255)'}, 'Tab reaches Options with the shared focus ring');
    await page.keyboard.press('Enter');
    assert.equal(await isOpen(), true, 'Enter opens Options');
    for (const name of ['Layout', 'Numbers', 'Orientation', 'Assembly']) assert.equal(await page.getByRole('group', {name}).count(), 1, `The ${name} group is labelled`);
    const focused = [];
    for (const _ of menuControls) {await page.keyboard.press('Tab'); focused.push(await page.evaluate(() => document.activeElement.id))}
    assert.deepEqual(focused, menuControls, 'Tab reaches every secondary control in order');
    await page.locator('#showNumbers').focus(); await page.keyboard.press('Space');
    assert.equal(await page.locator('#showNumbers').getAttribute('aria-pressed'), 'true', 'Space toggles Show all numbers');
    assert.equal(await page.evaluate(() => localStorage.getItem('wall.numbers.showAll')), '1', 'Show-all persists in this browser');
    await page.locator('#assemblyOnOpen').focus(); await page.keyboard.press('Space');
    assert.equal(await page.locator('#assemblyOnOpen').isChecked(), false, 'Space toggles Play on opening');
    assert.equal(await page.evaluate(() => localStorage.getItem('wall.assembly.opening')), '0', 'Opening playback persists in this browser');
    await page.keyboard.press('Escape');
    assert.equal(await isOpen(), false, 'Escape closes Options');
    assert.equal(await page.evaluate(() => document.activeElement === document.querySelector('#wallOptions > summary')), true, 'Escape returns focus to Options');
    await page.keyboard.press('Space');
    assert.equal(await isOpen(), true, 'Space reopens Options');
    assert.equal(await page.locator('#showNumbers').getAttribute('aria-pressed'), 'true', 'Number display keeps its setting');
    assert.equal(await page.locator('#assemblyOnOpen').isChecked(), false, 'Playback keeps its setting');
    await page.locator('#assemblyOnOpen').click(); await page.locator('#showNumbers').click();
    assert.equal(await page.evaluate(() => localStorage.getItem('wall.assembly.opening')), null);
    assert.equal(await page.evaluate(() => localStorage.getItem('wall.numbers.showAll')), null);
    await page.locator('#projects h2').click();
    assert.equal(await isOpen(), false, 'A press outside closes Options');
    assert.deepEqual(writes, [], 'Opening, toggling and closing Options send no write');

    // Orientation from the menu keeps its existing request and focus behavior.
    writes.length = 0;
    const settingsRoute = request => {Object.assign(current.settings, request.request().postDataJSON()); return request.fulfill({json: {ok: true}})};
    await page.route('**/api/settings', settingsRoute);
    try {
      await options.open(page);
      await page.locator('#rotate').focus();
      for (const rotation of [90, 180, 270, 0]) {await page.keyboard.press('Enter'); await page.waitForFunction(value => state.settings.rotation === value, rotation)}
    } finally {await page.unroute('**/api/settings', settingsRoute)}
    assert.deepEqual(writes, ['/api/settings', '/api/settings', '/api/settings', '/api/settings'], 'Rotate sends only the existing settings request');
    assert.equal(await isOpen(), true, 'The menu stays open after rotating');
    await page.waitForTimeout(1100);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'rotate', 'Polling keeps focus on Rotate');
    await page.screenshot({path: path.join(root, 'test-results/hierarchy-options-open.png'), fullPage: true});
    await page.keyboard.press('Escape');
    assert.equal(await isOpen(), false);

    // Dense and empty data at every supported width.
    for (const [name, snapshot] of [['dense', dense], ['empty', empty]]) {
      current = snapshot;
      for (const [width, height] of [[1440, 1000], [800, 1000], [390, 844]]) {
        await page.setViewportSize({width, height}); await refresh(); await settle();
        const fit = await geometry();
        assert.equal(fit.overflow, false, `${name} ${width}px: no horizontal overflow`);
        assert.ok(fit.headHeight <= 40, `${name} ${width}px: the wall heading takes one row (${fit.headHeight}px)`);
        assert.ok(fit.wallWidth >= .45, `${name} ${width}px: the wall spans at least 45% of the width (${(fit.wallWidth * 100).toFixed(0)}%)`);
        assert.ok(fit.wallHeight >= 300, `${name} ${width}px: the wall is at least 300px tall (${fit.wallHeight}px)`);
        assert.ok(fit.wallTop < height * .4, `${name} ${width}px: the wall starts within the first screen (${fit.wallTop}px)`);
        assert.ok(fit.readoutBottom <= height && fit.connectionBottom <= height && fit.workBottom <= height, `${name} ${width}px: readout, connection and mode controls sit on the first screen`);
        assert.equal(fit.menuOpen, false);
        await page.screenshot({path: path.join(root, `test-results/hierarchy-${width}-${name}.png`), fullPage: true});
      }
      if (name === 'empty') {
        assert.equal(await page.locator('#readout').textContent(), 'Work · scene playing · no alerts', 'Empty state: the readout says scene playing and no alerts');
        assert.match(await page.locator('#taskList').textContent(), /No tracked tasks/);
        assert.match(await page.locator('#projectList').textContent(), /No current project/);
        assert.equal(await page.locator('#taskSummary').textContent(), '0 shown');
      }
    }

    // Pending edits and connection failure stay visible with the menu closed at the narrowest width.
    current = structuredClone(dense); current.pending = {settings: {}, lines: {[current.lines[0].id]: {project: 'proj-1'}}, tasks: {}};
    await page.setViewportSize({width: 390, height: 844}); await refresh(); await settle();
    assert.equal(await page.locator('#readout').textContent(), 'Work · indicators on · pending edit · 2 blocked · 3 question', 'The readout flags the pending edit');
    assert.equal(await page.locator('#busy').isVisible(), true, 'The pending banner is visible');
    assert.ok((await page.locator('#busy').boundingBox()).y < 844, 'The pending banner sits on the first screen at 390px');
    assert.equal(await isOpen(), false);
    await page.screenshot({path: path.join(root, 'test-results/hierarchy-390-pending.png'), fullPage: true});
    const failing = request => request.fulfill({status: 503, json: {error: 'Local map status unavailable. Retrying shortly.'}});
    await page.unroute('**/api/state', route); await page.route('**/api/state', failing);
    try {
      await refresh(); await settle();
      assert.match(await page.locator('#connection').textContent(), /Disconnected/, 'The connection pill reports the failure');
      assert.ok((await page.locator('#connection').boundingBox()).y < 844, 'The disconnected state sits on the first screen at 390px');
      assert.match(await page.locator('#notice').textContent(), /unavailable/, 'The notice shows the error');
      await page.screenshot({path: path.join(root, 'test-results/hierarchy-390-disconnected.png'), fullPage: true});
    } finally {await page.unroute('**/api/state', failing); await page.route('**/api/state', route); await page.evaluate(() => {errorUntil = 0})}

    // Reduced motion keeps Work, Quiet and Free distinguishable in the readout.
    await page.setViewportSize({width: 1440, height: 1000});
    await page.emulateMedia({reducedMotion: 'reduce'});
    try {
      const notes = {};
      for (const mode of ['work', 'quiet', 'free']) {
        current = structuredClone(dense); current.mode = mode; await refresh(); await settle();
        await page.waitForFunction(value => document.body.dataset.mode === value, mode);
        await page.waitForTimeout(250); // let the 150 ms button transition finish before the screenshot
        notes[mode] = await page.locator('#readout').textContent();
        await page.screenshot({path: path.join(root, `test-results/hierarchy-reduced-${mode}.png`)});
      }
      assert.match(notes.work, /indicators on/); assert.match(notes.quiet, /steady/); assert.match(notes.free, /released/);
      assert.equal(new Set(Object.values(notes)).size, 3, 'Each mode has a distinct readout under reduced motion');
      assert.equal(await page.evaluate(() => document.getElementById('wall').getAnimations({subtree: true}).filter(animation => animation.playState === 'running').length), 0, 'Reduced motion runs no wall animation');
    } finally {await page.emulateMedia({reducedMotion: null})}

    // The #76 and #77 lists fit: a long-titled selected task and its override stay usable.
    for (const [width, height] of [[1440, 1000], [390, 844]]) {
      current = dense; await page.setViewportSize({width, height}); await refresh(); await settle();
      await page.locator('#taskList [data-task="task-00"] .task-title').click(); await refresh();
      assert.match(await page.locator('#taskDetail').textContent(), /A long retained task title/, `${width}px: the selected task shows its details`);
      const reservation = page.locator('#assignProject');
      await reservation.scrollIntoViewIfNeeded();
      assert.equal(await reservation.isVisible(), true, `${width}px: the reservation control is usable in Project layout`);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${width}px: long labels do not overflow`);
      if (width === 1440) assert.equal(await page.evaluate(() => new Set([...document.querySelectorAll('#taskList .task')].map(node => Math.round(node.getBoundingClientRect().left))).size), 2, 'The compact grid keeps two desktop columns');
      await page.evaluate(() => {selected.clear(); taskFocus = null; document.activeElement.blur(); render()});
    }
    console.log('Hierarchy checks passed: Options menu, live status readout, single count locations, dense/empty widths, pending, disconnected, reduced motion, and long labels.');
  } finally {
    page.off('request', record);
    await page.unroute('**/api/state', route);
    await options.close(page);
    await page.emulateMedia({reducedMotion: null});
    await page.setViewportSize(viewport);
    await page.evaluate(() => {
      selected.clear(); taskFocus = null; showAllTasks = false; showSavedProjects = false; document.activeElement.blur();
      try {localStorage.removeItem('wall.numbers.showAll'); localStorage.removeItem('wall.assembly.opening'); localStorage.removeItem('wall.assembly.entry')} catch {}
      showAllNumbers = false; syncNumberControl(); $('assemblyOnOpen').checked = true; $('assemblyOnEntry').checked = true;
    });
    await refresh();
  }
};
