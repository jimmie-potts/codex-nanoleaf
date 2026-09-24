const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async function(page,root){
  const snapshot=await page.evaluate(()=>structuredClone(state));
  snapshot.tasks=Array.from({length:72},(_,i)=>({id:'task-'+String(i).padStart(2,'0'),title:'Task '+i,project:null,status:i<2?'blocked':i<5?'question':i<9?'working':'unread',line:i<15?snapshot.lines[i].id:null,started:1000}));
  snapshot.lines.forEach((line,i)=>{line.task=snapshot.tasks[i]?.id||null;line.project=null});
  snapshot.pending=null;
  const route=request=>request.fulfill({json:snapshot});
  const refresh=()=>page.evaluate(async()=>{while(refreshing)await new Promise(resolve=>setTimeout(resolve,10));await refresh()});
  const rows=()=>page.locator('#taskList .task').evaluateAll(ns=>ns.map(n=>n.dataset.task));
  const row=id=>page.locator(`#taskList [data-task="${id}"]`);
  const writes=[];const record=request=>{if(request.method()!=='GET')writes.push(request.url())};
  page.on('request',record);
  await page.route('**/api/state',route);
  const viewport=page.viewportSize();
  try{
    await page.setViewportSize({width:1440,height:1000});
    await page.evaluate(()=>{selected.clear();taskFocus=null});
    await refresh();
    assert.equal(await page.locator('#inspector .task').count(),8,'72 tracked tasks must render at most eight rows by default, without duplicate waiting rows');
    assert.equal(await page.locator('#taskCount').textContent(),'72');
    assert.match(await page.locator('#taskSummary').textContent(),/Showing 8 of 72 tasks/);
    assert.match(await page.locator('#taskStatusCounts').textContent(),/2 blocked.*3 question.*4 working.*63 unread/);
    assert.match(await page.locator('#waiting').textContent(),/57 waiting for a Line/);
    assert.equal(await page.locator('#waiting .task').count(),0);
    snapshot.tasks.reverse();await refresh();
    assert.deepEqual(await rows(),Array.from({length:8},(_,i)=>'task-0'+i),'Priority and identity ties cannot depend on snapshot order');
    await page.screenshot({path:path.join(root,'test-results/compact-tasks-72.png'),fullPage:true});
    await page.getByRole('button',{name:'Show all tasks'}).click();
    assert.equal(await page.locator('#taskList .task').count(),72);
    assert.equal(await page.evaluate(()=>state.tasks.length),72);
    for(const [filter,count] of [['blocked',2],['question',3],['working',4],['unread',63],['waiting',57],['all',72]]){
      await page.getByLabel('Filter tasks').selectOption(filter);
      assert.equal(await page.locator('#taskList .task').count(),count);
      assert.equal(await page.locator('#taskCount').textContent(),'72');
      assert.match(await page.locator('#taskSummary').textContent(),new RegExp(`Showing ${count} of 72 tasks`));
    }
    await page.getByLabel('Search tasks').fill('task-71');
    assert.deepEqual(await rows(),['task-71'],'Search makes an unknown-project/fallback task reachable by full identity');
    await row('task-71').locator('.task-title').click();
    assert.match(await page.locator('#taskDetail').textContent(),/Task 71/);
    await page.getByLabel('Search tasks').fill('not present');
    assert.equal(await page.locator('#taskList .task').count(),0);
    assert.match(await page.locator('#taskList').textContent(),/No tasks match/);
    await page.getByRole('button',{name:'Show selected tasks'}).click();
    assert.equal(await page.locator('#taskList .task').count(),72);
    assert.equal((await rows())[0],'task-71');
    assert.equal(await row('task-71').locator('.task-title').evaluate(n=>n===document.activeElement),true);
    await page.getByRole('button',{name:'Show fewer tasks'}).click();
    assert.equal((await rows())[0],'task-71');
    assert.equal(await page.locator('#inspector .task').count(),8);
    assert.equal(await page.getByLabel('Filter tasks').isVisible(),false);

    const moving=snapshot.tasks.find(t=>t.id==='task-71'),destination=snapshot.lines[0];
    const override=page.getByRole('combobox',{name:'Task project override'});
    await override.focus();
    for(const line of [destination.id,null,snapshot.lines[1].id]){
      snapshot.lines.forEach(l=>{if(l.task===moving.id)l.task=null});
      moving.line=line;if(line)snapshot.lines.find(l=>l.id===line).task=moving.id;
      await refresh();
      assert.equal(await page.evaluate(()=>taskFocus),'task-71','Task selection follows its identity across placement changes');
      assert.deepEqual(await page.evaluate(()=>[...selected]),line?[line]:[]);
      assert.equal(await override.evaluate(n=>n===document.activeElement),true);
      assert.match(await page.locator('#taskDetail').textContent(),/Task 71/);
    }
    snapshot.tasks=snapshot.tasks.filter(t=>t!==moving);
    snapshot.lines.forEach(l=>{if(l.task===moving.id)l.task=null});await refresh();
    assert.equal(await override.count(),0,'Owner retirement removes a focused stale override');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'tasksTitle');
    assert.equal(await page.evaluate(()=>taskFocus),null);
    assert.match(await page.locator('#taskSummary').textContent(),/of 71 tasks/);
    snapshot.tasks.push(moving);moving.line=null;await refresh();
    assert.equal(await page.evaluate(()=>taskFocus),null,'Recreated identity does not resurrect retired selection');

    await page.getByRole('button',{name:'Show all tasks'}).click();
    await page.getByLabel('Filter tasks').selectOption('blocked');
    const focused=snapshot.tasks.find(t=>t.id==='task-00');
    await row(focused.id).locator('.task-title').focus();
    focused.status='unread';await refresh();
    assert.equal(await row(focused.id).locator('.task-title').evaluate(n=>n===document.activeElement),true,'A retained focused row survives leaving its filter');
    assert.match(await page.locator('#taskSummary').textContent(),/1 match filter.*1 focused task outside filter/);
    await page.getByLabel('Search tasks').focus();await refresh();
    assert.deepEqual(await rows(),['task-01'],'Filter applies after focus leaves the retained exception');
    await page.getByLabel('Filter tasks').selectOption('all');
    await page.getByRole('button',{name:'Show fewer tasks'}).click();
    await row('task-01').locator('.task-title').focus();
    snapshot.tasks.find(t=>t.id==='task-01').status='unread';
    focused.status='blocked';
    const scroll=await page.evaluate(()=>{const p=document.querySelector('#inspector');p.scrollTop=150;return p.scrollTop});
    await refresh();await page.waitForTimeout(1100);
    assert.equal(await row('task-01').locator('.task-title').evaluate(n=>n===document.activeElement),true,'Priority updates retain the focused compact row');
    assert.equal(await page.locator('#taskList .task').count(),8);
    assert.equal(await page.locator('#inspector').evaluate(n=>n.scrollTop),scroll,'Polling preserves inspector scroll');

    snapshot.tasks=snapshot.tasks.filter(t=>t.id!=='task-01');await refresh();
    assert.equal(await page.evaluate(()=>document.activeElement.id),'tasksTitle','A retired focused row returns focus to a surviving heading');
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.setViewportSize({width:390,height:844});
    snapshot.tasks.find(t=>t.id==='task-00').title='A long task title with unknown project metadata '.repeat(8);
    await refresh();
    await row('task-00').locator('.task-title').press('Enter');
    assert.match(await page.locator('#taskDetail').textContent(),/A long task title/);
    const pageScroll=await page.evaluate(()=>{window.scrollTo(0,document.querySelector('#tasksTitle').getBoundingClientRect().top+window.scrollY);return window.scrollY});
    snapshot.tasks.find(t=>t.id==='task-00').status='working';await refresh();await page.waitForTimeout(1100);
    assert.equal(await page.evaluate(()=>window.scrollY),pageScroll,'Narrow-page polling does not jump to reordered content');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Long labels fit the narrow page');
    await page.screenshot({path:path.join(root,'test-results/compact-tasks-narrow.png'),fullPage:true});
    await page.getByRole('button',{name:'Show all tasks'}).press('Enter');
    await page.getByLabel('Filter tasks').selectOption('waiting');
    assert.equal(await page.locator('#taskList .task').count(),57);
    await page.getByRole('button',{name:'Show fewer tasks'}).press('Enter');
    await page.setViewportSize({width:1440,height:1000});

    const all=snapshot.tasks;
    for(const count of [0,8]){
      snapshot.tasks=all.slice(0,count);snapshot.lines.forEach(l=>l.task=null);await refresh();
      assert.equal(await page.locator('#taskList .task').count(),count);
      assert.equal(await page.locator('#taskCount').textContent(),String(count));
      assert.equal(await page.locator('#taskStatusCounts').textContent(),`0 blocked · 0 question · 0 working · ${count} unread`,'Empty and eight-unread snapshots have truthful per-status counts');
      assert.equal(await page.locator('#waiting').textContent(),`${count} waiting for a Line`,'All tasks in these small fixtures are waiting');
      assert.equal(await page.locator('#taskSummary').textContent(),`Showing ${count} of ${count} tasks`);
      await page.screenshot({path:path.join(root,`test-results/compact-tasks-${count}.png`),fullPage:true});
    }
    assert.deepEqual(writes,[],'List controls and selection must remain read-only');
  }finally{
    page.off('request',record);
    await page.evaluate(()=>{showAllTasks=false;selected.clear();taskFocus=null;$('taskFilter').value='all';$('taskSearch').value='';document.activeElement.blur()});
    await page.unroute('**/api/state',route);
    await page.setViewportSize(viewport);
    await page.emulateMedia({reducedMotion:null});
    await refresh();
  }
};
