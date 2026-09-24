const assert = require('node:assert/strict');
module.exports = async function(page, root) {
  const path = require('node:path');
  const snapshot = await page.evaluate(() => structuredClone(state));
  snapshot.projects = Array.from({length:20}, (_, i) => ({id:'saved-'+i,name:'Saved '+String(i).padStart(2,'0'),color:'#aa55ff',active:0,waiting:0,assigned:0}));
  snapshot.tasks = [];
  snapshot.lines.forEach(line => {line.task=null;line.project='saved-0'});
  snapshot.settings.style = 'project';
  const route = request => request.fulfill({json:snapshot});
  await page.route('**/api/state', route);
  const refresh = () => page.evaluate(async () => {while(refreshing) await new Promise(resolve=>setTimeout(resolve,10));await refresh()});
  const rows=()=>page.locator('#projectList [data-project]').evaluateAll(nodes=>nodes.map(n=>n.dataset.project));
  const project=id=>page.locator(`#projectList [data-project="${id}"]`);
  const task=(id,project,status='working',line=null)=>({id,project,status,line,title:id,started:1000});
  const writes=[];
  const record=request=>{if(request.method()!=='GET')writes.push(request.url())};
  page.on('request',record);
  try {
    const catalog=snapshot.projects;snapshot.projects=[];
    await refresh();
    assert.deepEqual(await rows(),[]);
    assert.equal(await page.locator('#showSavedProjects').textContent(),'Show saved projects (0)');
    snapshot.projects=catalog;
    await refresh();
    assert.equal(await page.locator('#projectList [data-project]').count(),0,'Saved-only projects must be hidden by default, even with reservations');
    assert.match(await page.locator('#projectList').textContent(),/No current project/);
    const toggle=page.locator('#showSavedProjects');
    assert.equal(await toggle.textContent(),'Show saved projects (20)');
    await toggle.click();
    assert.equal(await toggle.getAttribute('aria-expanded'),'true');
    assert.equal(await page.locator('#projectList [data-project]').count(),20);
    await toggle.click();
    assert.equal(await page.locator('#projectList [data-project]').count(),0);
    await page.screenshot({path:path.join(root,'test-results/current-projects-empty.png'),fullPage:true});

    // Deliberately stale API counters: derive all presentation counts from tasks.
    snapshot.projects.forEach(p=>{p.active=99;p.waiting=99});
    snapshot.tasks=[task('one','saved-1'),task('two','saved-2','blocked'),task('three','saved-2','question'),
      task('four','saved-3','unread'),task('five','saved-4'),task('six','saved-4','unread'),
      task('seven','saved-5'),task('eight','saved-5'),task('unknown',null)];
    for(let i=0;i<9;i++)snapshot.tasks.push(task('unread-'+i,'saved-3','unread'));
    // Name order breaks activity ties; equal names then use stable IDs.
    snapshot.projects[2].name='Zulu';snapshot.projects[5].name='Alpha';
    snapshot.projects[1].name='Equal';snapshot.projects[6].name='Equal';
    snapshot.tasks.push(task('tie','saved-6'));
    await refresh();
    assert.deepEqual(await rows(),['saved-5','saved-2','saved-4','saved-1','saved-6','saved-3']);
    assert.match(await project('saved-3').locator('.project-stats').textContent(),/^10 tasks · 10 waiting$/);
    await page.setViewportSize({width:1440,height:1000});
    await page.screenshot({path:path.join(root,'test-results/current-projects-ranked.png'),fullPage:true});
    snapshot.projects.reverse();await refresh();
    assert.deepEqual(await rows(),['saved-5','saved-2','saved-4','saved-1','saved-6','saved-3'],'Poll input order cannot shuffle ties');
    snapshot.tasks.find(t=>t.id==='four').status='working';await refresh();
    assert.deepEqual(await rows(),['saved-5','saved-2','saved-3','saved-4','saved-1','saved-6'],'Status-only changes update rank');
    snapshot.tasks.find(t=>t.id==='four').status='unread';await refresh();

    await page.locator('.wall-line').first().click();
    await page.locator('#assignProject').selectOption('saved-9');
    snapshot.pending={settings:{style:'classic'},lines:{[snapshot.lines[0].id]:{project:'saved-2'}},tasks:{}};
    const color=project('saved-5').locator('input[type=color]');
    await color.focus();
    await color.evaluate(node=>{window.editingProjectColor=node;node.value='#123456';node.dispatchEvent(new Event('input',{bubbles:true}))});
    // Retained unread disappearance removes its contribution; no local age clock.
    snapshot.tasks=snapshot.tasks.filter(t=>!['saved-3','saved-5'].includes(t.project));
    await refresh();
    assert.equal(await project('saved-3').count(),0);
    assert.equal(await project('saved-5').count(),1,'An explicitly focused editor survives retirement');
    assert.equal(await color.evaluate(node=>node===window.editingProjectColor&&node===document.activeElement&&node.isConnected),true);
    assert.equal(await color.inputValue(),'#123456');
    assert.equal(await page.locator('#assignProject').inputValue(),'saved-9');
    assert.equal(await page.locator('.wall-line.selected').count(),1);
    assert.equal(await page.locator('#busy').textContent(),'After this comet: classic layout · Line 1 → Zulu');

    // Moving the editing project's rank must never detach the focused row.
    await page.evaluate(()=>{
      window.projectBlurCount=0;editingProjectColor.addEventListener('blur',()=>window.projectBlurCount++);
      window.projectDetachCount=0;
      const row=editingProjectColor.closest('[data-project]');
      window.projectObserver=new MutationObserver(records=>{for(const record of records)if([...record.removedNodes].includes(row))window.projectDetachCount++});
      projectObserver.observe($('projectList'),{childList:true});
    });
    snapshot.tasks.push(...Array.from({length:4},(_,i)=>task('new-'+i,'saved-5')));
    await refresh();
    assert.equal((await rows())[0],'saved-5');
    snapshot.tasks=snapshot.tasks.filter(t=>t.project!=='saved-5');
    await refresh();
    assert.equal(await page.evaluate(()=>projectBlurCount),0);
    assert.equal(await page.evaluate(()=>projectDetachCount),0);
    assert.equal(await color.inputValue(),'#123456');
    await page.evaluate(()=>projectObserver.disconnect());
    await toggle.focus();await refresh();
    assert.equal(await project('saved-5').count(),0,'Inactive editor leaves after blur');

    // Fresh recreation and no attribution from a different source.
    snapshot.tasks=[task('fresh','saved-3','unread',snapshot.lines[1].id)];
    snapshot.lines.forEach(l=>{l.task=null;l.project=null});
    snapshot.lines[0].project='saved-0';snapshot.lines[1].task='fresh';
    snapshot.pending=null;
    for(const style of ['classic','project']){
      snapshot.settings.style=style;await refresh();
      assert.deepEqual(await rows(),['saved-3']);
      assert.deepEqual(await project('saved-3').locator('[data-line-group="in-use"] button').evaluateAll(ns=>ns.map(n=>n.dataset.lineId)),[snapshot.lines[1].id]);
      assert.equal(await page.locator('.shared-pool').count(),style==='project'?1:0);
    }
    // The selected device's placement can differ while sharing the same catalog.
    await project('saved-3').locator('[data-line-group="in-use"] button').focus();
    snapshot.device='other-device';snapshot.tasks[0].line=null;snapshot.lines[1].task=null;
    await refresh();
    assert.match(await project('saved-3').locator('.project-stats').textContent(),/^1 task · 1 waiting$/);
    assert.equal(await project('saved-3').locator('[data-line-group="in-use"] button').count(),0);
    assert.equal(await project('saved-3').locator('input').evaluate(node=>node===document.activeElement),true,'A removed Line badge returns focus to its project color control');
    await toggle.focus();
    snapshot.tasks[0].project=null;await refresh();
    assert.deepEqual(await rows(),[]);
    await toggle.focus();await page.keyboard.press('Enter');
    assert.equal((await rows()).length,20);
    assert.equal(await project('saved-5').locator('input').inputValue(),'#aa55ff','Uncommitted input did not change the saved catalog');
    await page.keyboard.press('Enter');
    snapshot.tasks=[task('recreated','saved-3')];await refresh();
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(root,'test-results/current-projects-narrow.png'),fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Narrow layout must not overflow');
    await page.setViewportSize({width:1440,height:1000});
    await page.screenshot({path:path.join(root,'test-results/current-projects-active.png'),fullPage:true});
    assert.deepEqual(writes,[],'Filtering, polling and disclosure send no writes');
  } finally {
    page.off('request',record);
    await page.evaluate(()=>{showSavedProjects=false;document.activeElement.blur()});
    await page.setViewportSize({width:1440,height:1000});
    await page.unroute('**/api/state',route);await refresh();
  }
};
