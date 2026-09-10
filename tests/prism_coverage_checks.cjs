const assert = require('node:assert/strict');

/*
 * Proposed additive browser acceptance checks for issue #53.
 *
 * This module targets the live wall's existing lexical `state`, `prism`,
 * `refresh`, and `zoneColors` bindings. It performs no unmocked writes.
 */
module.exports = async function prismCoverageChecks(page) {
  const failures = [];
  const check = async (name, fn) => {
    try { await fn(); }
    catch (error) { failures.push(`${name} -> ${error.message.split('\n')[0]}`); }
  };
  const refresh = () => page.evaluate(async () => {
    while (refreshing) await new Promise(resolve => setTimeout(resolve, 10));
    await refresh();
  });
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const circularError = (actual, expected) => {
    const raw = Math.abs(actual - expected) % 1;
    return Math.min(raw, 1 - raw);
  };
  const samplePhase = () => page.evaluate(() => {
    const now = performance.now();
    prism.light(now);
    return {phase: prism.snapshot().lightPhase, now};
  });
  const waitForPhase = () => page.waitForFunction(() => {
    const phase = window.wallAssembly?.snapshot?.().lightPhase;
    return Number.isFinite(phase) && phase >= .18 && phase <= .55;
  }, null, {timeout: 4500});
  const visibleColors = id => page.evaluate(lineId => {
    const line = prism.layout.lines.find(item => item.id === lineId);
    const edge = document.querySelector(`#wall [data-edge][data-line-id="${CSS.escape(lineId)}"]`);
    const zones = [0, 1].map(zone => {
      const solid = edge.querySelector(`[data-part="zone-core"] [data-solid="${line.index}-${zone}"]:not([data-hot-solid])`);
      const stops = [...document.querySelectorAll(`#wall [data-paint="${line.index}-${zone}"]:not([data-hot])`)]
        .map(node => node.getAttribute('stop-color').toLowerCase());
      return {solid: solid.getAttribute('fill').toLowerCase(), stops: [...new Set(stops)]};
    });
    const point = element => new DOMPoint(0, 0).matrixTransform(element.getCTM());
    const packets = [0, 1].map(zone => point(edge.querySelector(`[data-part="zone-core"] [data-packet][data-zone="${zone}"]`)));
    const a = point(prism.parts.node[line.a]);
    const b = point(prism.parts.node[line.b]);
    const distance = (left, right) => Math.hypot(left.x - right.x, left.y - right.y);
    return {
      zones,
      layoutColors: [...line.colors].map(value => value.toLowerCase()),
      endpointOwnership: [
        {own: distance(packets[0], a), other: distance(packets[0], b)},
        {own: distance(packets[1], b), other: distance(packets[1], a)},
      ],
    };
  }, id);

  await check('exact DOM zone colors retain endpoint ownership and reverse on a half swap', async () => {
    const original = await page.evaluate(() => structuredClone(state));
    const served = structuredClone(original);
    const target = served.lines[0];
    const project = served.projects[0];
    const task = served.tasks[0];
    assert.ok(target && project && task, 'The demo fixture needs a Line, project, and task');
    for (const line of served.lines) if (line.task === task.id) line.task = null;
    const displaced = served.tasks.find(item => item.id === target.task && item.id !== task.id);
    if (displaced) displaced.line = null;
    served.settings = {...served.settings, style: 'project', rotation: 0, flip_x: 0, flip_y: 0};
    served.mode = 'work';
    target.project = project.id; target.task = task.id; target.signature = 0;
    task.line = target.id; task.project = project.id; task.status = 'blocked';
    project.color = '#12abef';
    let assignPayload;
    const stateRoute = request => request.fulfill({json: served});
    const assignRoute = request => {
      assignPayload = request.request().postDataJSON();
      for (const [id, edit] of Object.entries(assignPayload.lines || {})) {
        const line = served.lines.find(item => item.id === id);
        if (line && Object.hasOwn(edit, 'signature')) line.signature = edit.signature;
      }
      return request.fulfill({json: {ok: true}});
    };
    await page.route('**/api/state', stateRoute);
    await page.route('**/api/assign', assignRoute);
    try {
      await refresh();
      await page.locator(`#wall .wall-line[data-line="${target.id}"]`).click();
      await waitForPhase();
      const blocked = await visibleColors(target.id);
      assert.deepEqual(blocked.layoutColors, ['#12abef', '#ff0000']);
      assert.deepEqual(blocked.zones.map(zone => zone.solid), ['#12abef', '#ff0000']);
      assert.ok(blocked.zones.every((zone, index) => zone.stops.length > 0 && zone.stops.every(value => value === blocked.layoutColors[index])), 'Packet gradients use their own zone color');
      assert.ok(blocked.endpointOwnership.every(pair => pair.own < pair.other), 'Zone 0 starts at endpoint a and zone 1 at endpoint b');

      const response = page.waitForResponse('**/api/assign');
      await page.locator('#swap').click(); await response;
      await page.waitForFunction(id => state.lines.find(line => line.id === id)?.signature === 1, target.id);
      await settle();
      assert.deepEqual(assignPayload.lines[target.id], {signature: 1}, 'Swap targets the selected physical Line');
      await waitForPhase();
      const swapped = await visibleColors(target.id);
      assert.deepEqual(swapped.layoutColors, ['#ff0000', '#12abef']);
      assert.deepEqual(swapped.zones.map(zone => zone.solid), ['#ff0000', '#12abef']);
      assert.ok(swapped.endpointOwnership.every(pair => pair.own < pair.other), 'A half swap changes color ownership without reversing physical endpoints');

      task.status = 'question';
      await refresh(); await settle();
      const question = await visibleColors(target.id);
      assert.deepEqual(question.layoutColors, ['#ffff00', '#12abef'], 'Question yellow replaces blocked red on the status-owned half');

      served.settings = {...served.settings, rotation: 90, flip_x: 1, flip_y: 0};
      await refresh(); await waitForPhase();
      const transformed = await visibleColors(target.id);
      assert.deepEqual(transformed.layoutColors, ['#ffff00', '#12abef']);
      assert.ok(transformed.endpointOwnership.every(pair => pair.own < pair.other), 'Rotation and reflection preserve ordered endpoint ownership');
    } finally {
      await page.unroute('**/api/assign', assignRoute);
      await page.unroute('**/api/state', stateRoute);
      await refresh();
    }
  });

  await check('valid and invalid live geometry preserve identity, colors, focus, and the 50 ms flow clock', async () => {
    const original = await page.evaluate(() => structuredClone(state));
    let served = structuredClone(original);
    served.settings = {...served.settings, style: 'project', rotation: 0, flip_x: 0, flip_y: 0};
    served.mode = 'work';
    const active = served.lines.find(line => served.tasks.some(task => task.id === line.task)) || served.lines[0];
    assert.ok(active, 'The demo fixture needs a physical Line');
    const stateRoute = request => request.fulfill({json: served});
    await page.route('**/api/state', stateRoute);
    try {
      await refresh();
      const control = page.locator(`#wall .wall-line[data-line="${active.id}"]`);
      await control.click(); await control.focus();
      await waitForPhase();
      const beforeColors = await visibleColors(active.id);
      const beforeTransform = await control.getAttribute('transform');
      await page.evaluate(() => { window.__prismCoverageOldSvg = prism.svg; window.__prismCoverageRenderer = prism; });

      const angle = Math.PI / 3, c = Math.cos(angle), s = Math.sin(angle);
      served = structuredClone(served);
      served.connector_layout.nodes = served.connector_layout.nodes.map(node => ({...node, x: node.x * c - node.y * s, y: node.x * s + node.y * c}));
      const before = await samplePhase();
      await refresh();
      const after = await samplePhase();
      const expected = (before.phase + (after.now - before.now) / 2000) % 1;
      assert.ok(circularError(after.phase, expected) <= .025, `Valid setLayout rebuild exceeded 50 ms: expected ${expected}, got ${after.phase}`);
      assert.equal(await page.evaluate(() => prism === window.__prismCoverageRenderer), true, 'Geometry replacement reuses the renderer');
      assert.equal(await page.evaluate(() => !window.__prismCoverageOldSvg.isConnected && prism.svg !== window.__prismCoverageOldSvg), true, 'Valid replacement installs a fresh SVG tree');
      assert.notEqual(await control.getAttribute('transform'), beforeTransform, 'Connector geometry changed the visible Line transform');
      assert.equal(await control.getAttribute('aria-pressed'), 'true', 'Selection survives geometry replacement');
      assert.equal(await control.evaluate(node => document.activeElement === node), true, 'Keyboard focus returns to the surviving physical ID');
      assert.deepEqual((await visibleColors(active.id)).layoutColors, beforeColors.layoutColors, 'Current colors survive geometry replacement');

      const acceptedIds = await page.evaluate(() => prism.layout.lines.map(line => line.id));
      await page.evaluate(() => { window.__prismCoverageAcceptedSvg = prism.svg; errorUntil = 0; });
      served = structuredClone(served); served.connector_layout.version = 99;
      const invalidBefore = await samplePhase();
      await refresh();
      const invalidAfter = await samplePhase();
      const invalidExpected = (invalidBefore.phase + (invalidAfter.now - invalidBefore.now) / 2000) % 1;
      assert.ok(circularError(invalidAfter.phase, invalidExpected) <= .025, 'Rejected geometry reset or offset the flow clock');
      assert.equal(await page.evaluate(() => prism.svg === window.__prismCoverageAcceptedSvg && prism.svg.isConnected), true, 'Malformed geometry keeps the accepted SVG');
      assert.deepEqual(await page.evaluate(() => prism.layout.lines.map(line => line.id)), acceptedIds);
      assert.equal(await control.getAttribute('aria-pressed'), 'true');
      assert.equal(await control.evaluate(node => document.activeElement === node), true);
      assert.deepEqual((await visibleColors(active.id)).layoutColors, beforeColors.layoutColors);
      assert.match(await page.locator('#notice').textContent(), /keeping the last valid wall/i);

      served.connector_layout.version = 1;
      served.connector_layout.lines[0].a = 'missing-connector';
      await refresh();
      assert.equal(await page.evaluate(() => prism.svg === window.__prismCoverageAcceptedSvg), true, 'An invalid endpoint also retains the accepted SVG');
      assert.equal(await control.evaluate(node => document.activeElement === node), true);

      served = structuredClone(original);
      served.settings = {...served.settings, style: 'project', rotation: 0, flip_x: 0, flip_y: 0};
      served.mode = 'work';
      const reconnectBefore = await samplePhase();
      await refresh();
      const reconnectAfter = await samplePhase();
      const reconnectExpected = (reconnectBefore.phase + (reconnectAfter.now - reconnectBefore.now) / 2000) % 1;
      assert.ok(circularError(reconnectAfter.phase, reconnectExpected) <= .025, 'Recovery to current valid geometry exceeded the 50 ms phase boundary');
      assert.equal(await page.locator('#connection').textContent(), 'Live');
    } finally {
      await page.evaluate(() => { delete window.__prismCoverageOldSvg; delete window.__prismCoverageAcceptedSvg; delete window.__prismCoverageRenderer; errorUntil = 0; });
      await page.unroute('**/api/state', stateRoute);
      await refresh();
    }
  });

  await check('a first load without valid connector geometry retains the usable standard map', async () => {
    const served = await page.evaluate(() => structuredClone(state));
    served.connector_layout = null;
    const context = await page.context().browser().newContext();
    const fallback = await context.newPage();
    const writes = [];
    fallback.on('request', request => {if (request.method() !== 'GET') writes.push(request.url());});
    await fallback.addInitScript(() => localStorage.setItem('wall.assembly.opening', '0'));
    await fallback.route('**/api/state', request => request.fulfill({json: served}));
    try {
      await fallback.goto(page.url());
      await fallback.waitForSelector('#wall .wall-line');
      assert.equal(await fallback.locator('#wall.prism-scene').count(), 0);
      assert.equal(await fallback.locator('#wall .wall-line').count(), served.lines.length);
      assert.match(await fallback.locator('#notice').textContent(), /showing standard Lines/i);
      const id = served.lines[0].id;
      const control = fallback.locator(`#wall .wall-line[data-line="${id}"]`);
      await control.press('Enter');
      assert.equal(await control.getAttribute('aria-pressed'), 'true');
      assert.deepEqual(writes, [], 'Fallback selection stays local');
    } finally {await context.close();}
  });

  await check('document and host visibility pause in place; repeated renderers release every acquired resource', async () => {
    const visibility = await page.evaluate(async () => {
      const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
      const until = async predicate => { for (let i = 0; i < 100; i++) { if (predicate()) return; await wait(10); } throw Error('Visibility transition timed out'); };
      const layout = PrismAdapters.fromState(state, zoneColors);
      const host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:10px;top:10px;width:600px;height:400px;z-index:-1';
      document.body.append(host);
      const renderer = new Prism.Renderer(host, layout, {animate: true});
      renderer.setActivity(layout.lines.map(line => line.id));
      const prior = Object.getOwnPropertyDescriptor(document, 'hidden');
      let hidden = false;
      Object.defineProperty(document, 'hidden', {configurable: true, get: () => hidden});
      try {
        await until(() => renderer.progress > .08);
        hidden = true; document.dispatchEvent(new Event('visibilitychange'));
        await until(() => renderer.pauseReasons.has('document-hidden'));
        const assemblyBefore = renderer.progress; await wait(180); const assemblyAfter = renderer.progress;
        hidden = false; document.dispatchEvent(new Event('visibilitychange'));
        await until(() => !renderer.pauseReasons.has('document-hidden') && renderer.progress > assemblyAfter);
        renderer.finish('finish'); renderer.setMode('work');
        await until(() => renderer.lightPhase > .06);
        host.style.display = 'none';
        await until(() => renderer.pauseReasons.has('host-hidden'));
        const flowBefore = renderer.lightPhase; await wait(180); const flowAfter = renderer.lightPhase;
        host.style.display = 'block';
        await until(() => !renderer.pauseReasons.has('host-hidden'));
        const resumeStart = renderer.lightPhase;
        await until(() => renderer.lightPhase !== resumeStart);
        return {assemblyBefore, assemblyAfter, flowBefore, flowAfter, resumedProgress: renderer.progress, resumedPhase: renderer.lightPhase};
      } finally {
        renderer.destroy(); host.remove();
        if (prior) Object.defineProperty(document, 'hidden', prior); else delete document.hidden;
        document.dispatchEvent(new Event('visibilitychange'));
      }
    });
    assert.equal(visibility.assemblyAfter, visibility.assemblyBefore, 'Document-hidden assembly position is fixed');
    assert.equal(visibility.flowAfter, visibility.flowBefore, 'A hidden host retains the current flow position');
    assert.ok(visibility.resumedProgress > visibility.assemblyAfter && visibility.resumedPhase !== visibility.flowAfter, 'Visible motion resumes from the retained position');

    const resources = await page.evaluate(async () => {
      const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
      const mainWasPaused = prism.pauseReasons.has('manual'); prism.pause();
      const native = {
        add: document.addEventListener, remove: document.removeEventListener,
        intersection: window.IntersectionObserver, mutation: window.MutationObserver,
        matchMedia: window.matchMedia, raf: window.requestAnimationFrame, caf: window.cancelAnimationFrame,
      };
      const counts = {visibilityAdds: 0, visibilityRemoves: 0, mediaAdds: 0, mediaRemoves: 0, intersectionCreated: 0, intersectionDisconnected: 0, mutationCreated: 0, mutationDisconnected: 0};
      const pending = new Set();
      try {
        document.addEventListener = function(type, listener, options) { if (type === 'visibilitychange') counts.visibilityAdds++; return native.add.call(this, type, listener, options); };
        document.removeEventListener = function(type, listener, options) { if (type === 'visibilitychange') counts.visibilityRemoves++; return native.remove.call(this, type, listener, options); };
        window.matchMedia = query => {
          const inner = native.matchMedia.call(window, query);
          return {get matches() { return inner.matches; }, addEventListener(type, listener) { if (type === 'change') counts.mediaAdds++; inner.addEventListener(type, listener); }, removeEventListener(type, listener) { if (type === 'change') counts.mediaRemoves++; inner.removeEventListener(type, listener); }};
        };
        window.IntersectionObserver = class {
          constructor(callback, options) { counts.intersectionCreated++; this.inner = new native.intersection(callback, options); this.closed = false; }
          observe(target) { this.inner.observe(target); }
          unobserve(target) { this.inner.unobserve(target); }
          disconnect() { if (!this.closed) counts.intersectionDisconnected++; this.closed = true; this.inner.disconnect(); }
          takeRecords() { return this.inner.takeRecords(); }
        };
        window.MutationObserver = class {
          constructor(callback) { counts.mutationCreated++; this.inner = new native.mutation(callback); this.closed = false; }
          observe(target, options) { this.inner.observe(target, options); }
          disconnect() { if (!this.closed) counts.mutationDisconnected++; this.closed = true; this.inner.disconnect(); }
          takeRecords() { return this.inner.takeRecords(); }
        };
        window.requestAnimationFrame = callback => { let id; id = native.raf.call(window, now => { pending.delete(id); callback(now); }); pending.add(id); return id; };
        window.cancelAnimationFrame = id => { pending.delete(id); return native.caf.call(window, id); };
        const layout = PrismAdapters.fromState(state, zoneColors);
        let obsoleteActivations = 0;
        for (let pass = 0; pass < 3; pass++) {
          const host = document.createElement('div'); host.style.cssText = 'position:fixed;inset:0;z-index:-1'; document.body.append(host);
          const renderer = new Prism.Renderer(host, layout, {animate: false, onSelect(){obsoleteActivations++;}});
          renderer.setActivity(layout.lines.map(line => line.id));
          const oldControl = renderer.parts.control[0], oldLabel = renderer.parts.label[0];
          renderer.setLayout(layout); renderer.setLayout(layout); renderer.setLayout(layout);
          oldControl.dispatchEvent(new MouseEvent('click')); oldLabel.dispatchEvent(new MouseEvent('click'));
          const finalControl = renderer.parts.control[0];
          await wait(30); renderer.destroy(); host.remove();
          finalControl.dispatchEvent(new MouseEvent('click'));
        }
        const removedHost = document.createElement('div'); removedHost.style.cssText = 'position:fixed;inset:0;z-index:-1'; document.body.append(removedHost);
        const removed = new Prism.Renderer(removedHost, layout, {animate: false}); removed.setActivity(layout.lines.map(line => line.id));
        removedHost.remove();
        for (let i = 0; i < 50 && !removed.destroyed; i++) await wait(10);
        await wait(30);
        return {...counts, obsoleteActivations, pendingFrames: pending.size, removedDestroyed: removed.destroyed, removedFrame: removed.frameId};
      } finally {
        document.addEventListener = native.add; document.removeEventListener = native.remove;
        window.IntersectionObserver = native.intersection; window.MutationObserver = native.mutation;
        window.matchMedia = native.matchMedia; window.requestAnimationFrame = native.raf; window.cancelAnimationFrame = native.caf;
        if (!mainWasPaused) prism.resume();
      }
    });
    assert.equal(resources.visibilityAdds, resources.visibilityRemoves, 'Every visibility listener is removed');
    assert.equal(resources.mediaAdds, resources.mediaRemoves, 'Every reduced-motion listener is removed');
    assert.equal(resources.intersectionCreated, resources.intersectionDisconnected, 'Every host observer is disconnected');
    assert.equal(resources.mutationCreated, resources.mutationDisconnected, 'Every removal observer is disconnected');
    assert.equal(resources.pendingFrames, 0, 'Destroyed renderers retain no scheduled frame');
    assert.equal(resources.obsoleteActivations, 0, 'Replaced and destroyed controls cannot trigger selection');
    assert.equal(resources.removedDestroyed, true, 'Removing a mounted host destroys its renderer');
    assert.equal(resources.removedFrame, 0);
  });

  await check('the same material nodes move, connectors grow from tips, and branch/cycle endpoints finish exactly', async () => {
    const result = await page.evaluate(() => {
      const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
      const point = (element, x = 0, y = 0) => new DOMPoint(x, y).matrixTransform(element.getCTM());
      const layout = PrismAdapters.fromState(state, zoneColors);
      const host = document.createElement('div'); host.style.cssText = 'position:fixed;inset:0;z-index:-1'; document.body.append(host);
      const renderer = new Prism.Renderer(host, layout, {animate: false});
      const bodies = renderer.layout.lines.map(line => renderer.parts.edge[line.index].querySelector('[data-part="tube-body"]'));
      const connectors = renderer.layout.nodes.map(node => renderer.parts.node[node.index]);
      const controls = renderer.layout.lines.map(line => renderer.parts.control[line.index]);
      const stable = () => bodies.every((node, index) => node === renderer.parts.edge[index].querySelector('[data-part="tube-body"]'))
        && connectors.every((node, index) => node === renderer.parts.node[index])
        && controls.every((node, index) => node === renderer.parts.control[index]);
      const ancestryFailures = [], tipErrors = [], depthSamples = [];
      renderer.replay();
      for (const progress of [.18, .30, .44, .58, .72]) {
        renderer.seek(progress);
        const visible = new Set(renderer.layout.lines.filter(line => getComputedStyle(renderer.parts.edge[line.index]).visibility !== 'hidden').map(line => line.index));
        const depths = renderer.layout.lines.filter(line => visible.has(line.index)).map(line => renderer.layout.nodes[line.child].depth);
        depthSamples.push({progress, maxDepth: depths.length ? Math.max(...depths) : -1});
        for (const line of renderer.layout.lines.filter(item => item.tree && visible.has(item.index))) {
          let node = renderer.layout.nodes[line.parent];
          while (node.parent !== null) {
            if (!visible.has(node.incoming)) ancestryFailures.push({progress, line: line.id, missing: renderer.layout.lines[node.incoming].id});
            node = renderer.layout.nodes[node.parent];
          }
        }
        for (const node of renderer.layout.nodes.filter(item => item.parent !== null && item.growth > .05 && item.growth < .95)) {
          const line = renderer.layout.lines[node.incoming];
          const body = renderer.parts.edge[line.index].querySelector('[data-part="tube-body"]');
          const ends = [point(body, -128, 0), point(body, 128, 0)];
          const center = point(renderer.parts.node[node.index]);
          const parent = point(renderer.parts.node[node.parent]);
          const direction = {x: center.x - parent.x, y: center.y - parent.y};
          const length = Math.hypot(direction.x, direction.y);
          const scale = +(renderer.parts.housing[node.index].getAttribute('transform').match(/scale\(([-\d.]+)/) || [0, 0])[1];
          const matrix = renderer.parts.node[node.index].getCTM();
          const far = (line.reverse ? line.da : line.db) * Math.hypot(matrix.a, matrix.b);
          const face = {x: center.x - direction.x / length * far * scale, y: center.y - direction.y / length * far * scale};
          tipErrors.push(Math.min(...ends.map(end => distance(end, face))));
        }
        if (!stable()) throw Error('Material or interaction nodes were replaced during a moving pose');
      }
      renderer.seek(1);
      const finalErrors = renderer.layout.lines.map(line => {
        const body = renderer.parts.edge[line.index].querySelector('[data-part="tube-body"]');
        const ends = [point(body, -128, 0), point(body, 128, 0)];
        const a = point(renderer.parts.node[line.a]), b = point(renderer.parts.node[line.b]);
        const length = distance(a, b), ux = (b.x - a.x) / length, uy = (b.y - a.y) / length;
        const matrix = renderer.parts.node[line.a].getCTM(), scale = Math.hypot(matrix.a, matrix.b);
        const expected = [{x: a.x + ux * line.da * scale, y: a.y + uy * line.da * scale}, {x: b.x - ux * line.db * scale, y: b.y - uy * line.db * scale}];
        return Math.min(
          Math.max(distance(ends[0], expected[0]), distance(ends[1], expected[1])),
          Math.max(distance(ends[0], expected[1]), distance(ends[1], expected[0])),
        );
      });
      const summary = {
        stable: stable(), ancestryFailures, tipErrors, finalErrors, depthSamples,
        loops: renderer.layout.lines.filter(line => !line.tree).length,
        branchConnectors: renderer.layout.nodes.filter(node => node.adj.length >= 3).length,
      };
      renderer.destroy(); host.remove();
      return summary;
    });
    assert.equal(result.stable, true, 'Final pose uses the same tube, connector, and control nodes');
    assert.equal(result.ancestryFailures.length, 0, `A descendant appeared before its path: ${JSON.stringify(result.ancestryFailures)}`);
    assert.ok(result.tipErrors.length > 0, 'At least one partly grown connector was sampled');
    assert.ok(Math.max(...result.tipErrors) < .8, `Connector near faces must remain at arriving tube tips: ${Math.max(...result.tipErrors)}`);
    assert.ok(Math.max(...result.finalErrors) < .8, `Final tube ends must meet connector faces, including cycles: ${Math.max(...result.finalErrors)}`);
    assert.ok(result.loops > 0, 'The actual layout exercises cycle-closing Lines');
    assert.ok(result.branchConnectors > 0, 'The actual layout exercises branch connectors');
    assert.ok(result.depthSamples.every((item, index, all) => !index || item.maxDepth >= all[index - 1].maxDepth), `Visible assembly depth must proceed outward: ${JSON.stringify(result.depthSamples)}`);
  });

  if (failures.length) throw Error('Prism coverage checks failed:\n' + failures.join('\n'));
  console.log('Prism coverage checks passed: exact zones, live replacement/fallback phase, visibility/lifecycle, and material mechanics.');
};
