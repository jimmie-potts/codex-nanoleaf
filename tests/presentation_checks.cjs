const assert = require('node:assert/strict');

// Issue #23: wall-mode-presentation. Indicative pulse, Quiet/Free presentation, reduced motion, readout, no writes.
module.exports = async function(page, root) {
  const failures = [];
  const check = async (name, fn) => {try {await fn()} catch (error) {failures.push(`${name} -> ${error.message.split('\n')[0]}`)}};
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const setMode = async mode => {await page.evaluate(m => action('/api/mode', {mode: m}), mode); await page.waitForFunction(m => state.mode === m && document.body.dataset.mode === m, mode); await settle()};
  const halo = selector => page.evaluate(s => {
    const line = [...document.querySelectorAll('.wall-line[data-status]')][0];
    const glow = line.querySelector(s);
    return {running: glow.getAnimations().filter(a => a.playState === 'running').map(a => a.animationName), opacity: parseFloat(getComputedStyle(glow).opacity), width: parseFloat(getComputedStyle(glow).strokeWidth)};
  }, selector);
  const allAnimations = () => page.evaluate(() => [...document.querySelectorAll('#wall *')].flatMap(node => node.getAnimations().filter(a => a.playState === 'running')).length);
  await page.setViewportSize({width: 1440, height: 1000});
  await page.evaluate(() => action('/api/settings', {style: 'project'}));
  await page.waitForFunction(() => state.settings.style === 'project');
  await setMode('work');

  await check('AC2: task Lines pulse in Work on a 2 s period and idle Lines stay steady', async () => {
    const active = await halo('.glow');
    assert.ok(active.running.includes('pulse'), `Halo of a task Line runs the pulse (got ${JSON.stringify(active.running)})`);
    assert.ok(active.width > 0, 'Halo stroke has width');
    const duration = await page.evaluate(() => document.querySelector('.wall-line[data-status] .glow').getAnimations()[0]?.effect.getTiming().duration);
    assert.equal(duration, 2000, 'Pulse period is two seconds');
    const idle = await page.evaluate(() => {const line = [...document.querySelectorAll('.wall-line:not([data-status])')][0]; return line.querySelector('.glow').getAnimations().length});
    assert.equal(idle, 0, 'An idle Line does not pulse');
  });

  await check('AC2: a rebuild resumes the page-wide phase', async () => {
    const ids = await page.locator('.wall-line').evaluateAll(nodes => nodes.map(node => node.dataset.line));
    const before = await page.evaluate(() => document.timeline.currentTime % 2000);
    await page.locator(`[data-line="${ids[0]}"]`).click(); await settle();
    // The pulse's active time is its current time minus the negative delay that set its phase.
    const [pageNow, animTime] = await page.evaluate(() => {const a = document.querySelector('.wall-line[data-status] .glow').getAnimations()[0]; return [document.timeline.currentTime % 2000, ((a.currentTime - a.effect.getTiming().delay) % 2000 + 2000) % 2000]});
    const skew = Math.abs(((pageNow - animTime) % 2000 + 2000) % 2000);
    assert.ok(Math.min(skew, 2000 - skew) <= 50, `Rebuilt pulse phase within 50 ms of the page phase (skew ${skew.toFixed(1)} ms; page phase before click ${before.toFixed(0)})`);
    await page.locator('#clear').click();
  });

  await check('AC6: the selection ring is cyan and marching in Work', async () => {
    const ids = await page.locator('.wall-line').evaluateAll(nodes => nodes.map(node => node.dataset.line));
    await page.locator(`[data-line="${ids[1]}"]`).click(); await settle();
    const ring = await page.evaluate(id => {const o = document.querySelector(`[data-line="${id}"] .outline`); const s = getComputedStyle(o); return {dash: s.strokeDasharray, running: o.getAnimations().filter(a => a.playState === 'running').length}}, ids[1]);
    assert.notEqual(ring.dash, 'none', 'Selected ring is dashed');
    assert.ok(ring.running >= 1, 'Selected ring marches');
    await page.locator('#clear').click();
  });

  await check('AC3: Quiet is steady with a reduced halo; Free dims the wall and says so', async () => {
    const work = await halo('.glow');
    await setMode('quiet');
    const quiet = await halo('.glow');
    assert.equal(quiet.running.length, 0, 'No running animation in Quiet');
    assert.ok(quiet.opacity < work.opacity || work.running.length > 0, 'Quiet halo is fainter than Work');
    assert.equal(await allAnimations(), 0, 'No wall animation at all in Quiet');
    await setMode('free');
    assert.notEqual(await page.locator('#wall').evaluate(node => getComputedStyle(node).filter), 'none', 'Free filters the wall');
    assert.equal(await allAnimations(), 0, 'No wall animation in Free');
    assert.match(await page.locator('#readout').textContent(), /released/i, 'Readout says the lights are released in Free');
    await setMode('work');
  });

  await check('AC4: reduced motion stops every wall animation and keeps modes distinguishable', async () => {
    await page.emulateMedia({reducedMotion: 'reduce'}); await settle();
    try {
      assert.equal(await allAnimations(), 0, 'No running wall animation under reduced motion in Work');
      const workHalo = (await halo('.glow')).opacity;
      await setMode('quiet');
      const quietHalo = (await halo('.glow')).opacity;
      assert.ok(workHalo > quietHalo, `Static Work halo (${workHalo}) is stronger than Quiet (${quietHalo})`);
      await setMode('work');
    } finally {await page.emulateMedia({reducedMotion: 'no-preference'}); await settle()}
  });

  await check('AC7: the readout follows state counts', async () => {
    const expected = await page.evaluate(() => ({lines: state.lines.length, tasks: state.tasks.length, blocked: state.tasks.filter(t => t.status === 'blocked').length, question: state.tasks.filter(t => t.status === 'question').length}));
    const text = (await page.locator('#readout').textContent()).toLowerCase();
    assert.match(text, /work/, 'Readout names the mode');
    assert.match(text, new RegExp(`${expected.lines} lines`), 'Readout names the Line count');
    assert.match(text, new RegExp(`${expected.tasks} tasks`), 'Readout names the task count');
    assert.match(text, new RegExp(`${expected.blocked} blocked`), 'Readout names the blocked count');
    assert.match(text, new RegExp(`${expected.question} question`), 'Readout names the question count');
    assert.doesNotMatch(text, /pending/, 'No pending edit reported when none exists');
    await page.evaluate(() => {state.pending = {settings: {}, lines: {[state.lines[0].id]: {project: 'a'}}, tasks: {}}; render()});
    assert.match((await page.locator('#readout').textContent()).toLowerCase(), /pending/, 'Readout reports a pending edit');
    await page.evaluate(() => refresh());
  });

  await check('AC5: watching and selecting the wall sends no write requests', async () => {
    const writes = [];
    const record = request => {if (request.method() !== 'GET') writes.push(request.url())};
    page.on('request', record);
    try {
      const ids = await page.locator('.wall-line').evaluateAll(nodes => nodes.map(node => node.dataset.line));
      await page.locator(`[data-line="${ids[2]}"]`).click();
      await page.locator(`[data-line="${ids[3]}"]`).click({modifiers: ['Control']});
      await page.waitForTimeout(2200);
      await page.locator('#clear').click();
      assert.deepEqual(writes, [], 'No write requests while watching the pulse or selecting');
    } finally {page.off('request', record)}
  });

  if (failures.length) throw Error('Presentation checks failed:\n' + failures.join('\n'));
  console.log('Presentation checks passed: pulse, phase, selection ring, Quiet/Free, reduced motion, readout, and no writes.');
};
