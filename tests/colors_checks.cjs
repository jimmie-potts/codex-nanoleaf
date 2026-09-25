const assert = require('node:assert/strict');
const path = require('node:path');
const options = require('./wall_options.cjs');

// Issue #139: the Options menu's Colors group edits the one task-light palette, and the wall,
// legend and status labels follow the effective colors.
const DEFAULTS = {base: '#0a1866', working: '#00ff00', question: '#ffff00', blocked: '#ff0000', unread: '#9b30ff'};
const SWATCHES = {base: 4, working: 1, question: 2, blocked: 1, unread: 4};

const channels = value => value.startsWith('#') ? [1, 3, 5].map(i => parseInt(value.slice(i, i + 2), 16)) : value.match(/\d+/g).slice(0, 3).map(Number);
const luminance = value => {
  const [r, g, b] = channels(value).map(c => (c /= 255) <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4);
  return .2126 * r + .7152 * g + .0722 * b;
};
const contrast = (a, b) => {const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p); return (x + .05) / (y + .05)};
const hex = value => '#' + channels(value).map(c => c.toString(16).padStart(2, '0')).join('');

module.exports = async function(page, root) {
  const writes = [];
  const record = request => {if (request.method() !== 'GET') writes.push({path: new URL(request.url()).pathname, body: request.postDataJSON()})};
  const palette = () => page.evaluate(() => state.palette);
  const until = expected => page.waitForFunction(value => JSON.stringify(state.palette) === JSON.stringify(value), expected);
  const row = role => page.locator(`#colorRows .color-row[data-role="${role}"]`);
  const pressed = role => row(role).locator('.swatch[aria-pressed="true"]').evaluateAll(nodes => nodes.map(node => node.getAttribute('aria-label')));
  const custom = role => row(role).locator('input[type="color"]');
  const setCustom = (role, value) => custom(role).evaluate((node, next) => {node.value = next; node.dispatchEvent(new Event('change', {bubbles: true}))}, value);
  const token = name => page.evaluate(name => getComputedStyle(document.documentElement).getPropertyValue(name).trim().toLowerCase(), name);
  const legend = label => page.locator('.legend span', {hasText: label}).locator('.dot').evaluate(node => getComputedStyle(node).backgroundColor);
  const tubes = () => page.evaluate(() => Object.fromEntries(state.lines.map(line => [line.id, {status: lineTask(line)?.status || null,
    colors: prism ? prism.layout.lines.find(item => item.id === line.id).colors.map(value => value.toLowerCase()) : null}])));
  const openColors = async () => {
    await options.open(page);
    if (!await page.locator('#colorOptions').evaluate(node => node.open)) await page.locator('#colorOptions > summary').click();
  };
  page.on('request', record);
  try {
    await page.evaluate(async () => {await action('/api/settings', {palette: 'default', style: 'classic'}); await action('/api/mode', {mode: 'work'})});
    await until(DEFAULTS);
    await options.close(page);

    // Structure: a closed Colors group inside Options; opening both sends no write.
    assert.equal(await page.locator('#wallOptions details#colorOptions').count(), 1, 'Colors sits inside the Options menu');
    assert.equal(await page.locator('#colorOptions').evaluate(node => node.open), false, 'Colors starts closed');
    writes.length = 0;
    await openColors();
    await page.waitForTimeout(1200);
    assert.deepEqual(writes, [], 'Opening Options and Colors sends no write');
    assert.deepEqual(await page.locator('#colorRows .role').allTextContents(), ['Base', 'Working', 'Question', 'Blocked', 'Unread']);
    for (const [role, count] of Object.entries(SWATCHES)) {
      assert.equal(await row(role).locator('.swatch').count(), count, `${role} offers its suggested swatches`);
      assert.equal(await row(role).locator('.swatch').first().getAttribute('data-color'), DEFAULTS[role], `${role} lists its default first`);
      assert.equal((await pressed(role)).length, 1, `${role} presses its default swatch`);
      assert.equal(await custom(role).getAttribute('aria-label'), (await row(role).locator('.role').textContent()) + ' custom color');
      assert.equal(await custom(role).inputValue(), DEFAULTS[role]);
    }
    assert.deepEqual(await pressed('unread'), ['Violet (default)']);
    assert.equal(await page.locator('#resetColors').isDisabled(), true, 'Reset is unavailable at the defaults');
    assert.equal(await page.locator('#colorWarning').isVisible(), false, 'The default palette has no similar colors');

    // The wall and legend use the defaults: unused Lines in Base, unread Lines in Unread.
    assert.equal(await token('--wall-base'), DEFAULTS.base);
    assert.equal(hex(await legend('Unread')), DEFAULTS.unread);
    assert.equal(hex(await legend('Unused or read')), DEFAULTS.base);
    let lines = await tubes();
    assert.ok(Object.values(lines).some(line => line.status === 'unread' && line.colors.every(color => color === DEFAULTS.unread)), 'Unread Lines are violet');
    assert.ok(Object.values(lines).filter(line => !line.status).every(line => line.colors.every(color => color === DEFAULTS.base)), 'Unused Lines are dim blue');
    await page.screenshot({path: path.join(root, 'test-results/colors-default.png'), fullPage: true});

    // A swatch sends one settings request, and the map follows the saved palette.
    writes.length = 0;
    await row('unread').locator('.swatch[aria-label="Magenta"]').click();
    await until({...DEFAULTS, unread: '#ff00c0'});
    assert.deepEqual(writes, [{path: '/api/settings', body: {palette: {unread: '#ff00c0'}}}], 'One settings request per choice');
    assert.equal(await page.locator('#colorOptions').evaluate(node => node.open), true, 'Colors stays open after a choice');
    assert.deepEqual(await pressed('unread'), ['Magenta']);
    assert.equal(hex(await legend('Unread')), '#ff00c0');
    lines = await tubes();
    assert.ok(Object.values(lines).some(line => line.status === 'unread' && line.colors.every(color => color === '#ff00c0')), 'Unread Lines turn magenta');

    // A custom Base color replaces every swatch choice and paints unused Lines.
    writes.length = 0;
    await setCustom('base', '#123456');
    await until({...DEFAULTS, unread: '#ff00c0', base: '#123456'});
    assert.deepEqual(writes.map(write => write.body), [{palette: {base: '#123456'}}]);
    assert.deepEqual(await pressed('base'), [], 'No Base swatch is pressed for a custom color');
    assert.equal(await row('base').locator('.custom-color').evaluate(node => node.classList.contains('chosen')), true, 'The custom control shows the choice');
    lines = await tubes();
    assert.ok(Object.values(lines).filter(line => !line.status).every(line => line.colors.every(color => color === '#123456')), 'Unused Lines use the custom Base');
    assert.equal(await page.locator('#resetColors').isDisabled(), false);

    // Similar colors warn without blocking the save, and the warning clears.
    await setCustom('unread', '#123456');
    await until({...DEFAULTS, unread: '#123456', base: '#123456'});
    await page.waitForFunction(() => !document.querySelector('#colorWarning').hidden);
    assert.match(await page.locator('#colorWarning').textContent(), /Base and Unread look alike/);
    await page.locator('#wallOptions').screenshot({path: path.join(root, 'test-results/colors-warning.png')});
    await row('unread').locator('.swatch[aria-label="Cyan"]').click();
    await until({...DEFAULTS, unread: '#00e5ff', base: '#123456'});
    await page.waitForFunction(() => document.querySelector('#colorWarning').hidden);

    // Choices survive a reload.
    await page.reload(); await page.waitForSelector('.wall-line');
    await page.waitForFunction(() => state && state.palette);
    assert.deepEqual(await palette(), {...DEFAULTS, unread: '#00e5ff', base: '#123456'});
    await openColors();
    assert.deepEqual(await pressed('unread'), ['Cyan']);
    assert.equal(await custom('base').inputValue(), '#123456');

    // Status labels stay readable whatever the palette, including black.
    await page.evaluate(() => action('/api/settings', {palette: {base: '#000000', working: '#000000', question: '#101010', blocked: '#200000', unread: '#000020'}}));
    await page.waitForFunction(() => state.palette.base === '#000000');
    const page_bg = await token('--bg');
    for (const chip of ['working', 'question', 'blocked', 'unread', 'idle']) {
      const value = await token('--chip-' + chip);
      assert.ok(contrast(value, page_bg) >= 4.5, `--chip-${chip} ${value} is readable`);
    }
    for (const badge of await page.locator('#taskList .badge[data-status]').evaluateAll(nodes => nodes.map(node => getComputedStyle(node).color))) {
      assert.ok(contrast(badge, page_bg) >= 4.5, `Badge color ${badge} is readable`);
    }
    assert.match(await page.locator('#colorWarning').textContent(), /Base and Working/);
    await options.close(page);
    await page.screenshot({path: path.join(root, 'test-results/colors-dark.png'), fullPage: true});

    // Reset colors restores the defaults with one request, and Escape still closes the menu.
    await openColors();
    writes.length = 0;
    await page.locator('#resetColors').click();
    await until(DEFAULTS);
    assert.deepEqual(writes, [{path: '/api/settings', body: {palette: 'default'}}]);
    assert.deepEqual(await pressed('unread'), ['Violet (default)']);
    assert.equal(await page.locator('#resetColors').isDisabled(), true);
    await row('working').locator('.swatch').first().focus();
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#wallOptions').evaluate(node => node.open), false, 'Escape closes Options from the Colors group');
    assert.equal(await page.evaluate(() => document.activeElement === document.querySelector('#wallOptions > summary')), true);
    console.log('Colors checks passed: Options group, swatches, custom colors, one request per choice, reload, similar-color warning, readable labels, wall and legend colors, and Reset.');
  } finally {
    page.off('request', record);
    await page.evaluate(() => action('/api/settings', {palette: 'default'})).catch(() => {});
    await options.close(page).catch(() => {});
  }
};
