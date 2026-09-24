const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async function(page,root){
  const snapshot=await page.evaluate(()=>structuredClone(state));
  const task=snapshot.tasks[0],line=snapshot.lines.find(line=>line.task===task.id);
  task.status='idle';task.evictionToken='a'.repeat(64);
  const requests=[],viewport=page.viewportSize();let fail=true;
  const feed=route=>route.fulfill({json:snapshot});
  const evict=async route=>{
    requests.push(route.request().postDataJSON());
    if(fail)return route.fulfill({status:409,json:{error:'Task changed. Refresh before evicting.'}});
    snapshot.tasks=snapshot.tasks.filter(item=>item.id!==task.id);
    for(const item of snapshot.lines)if(item.task===task.id)item.task=null;
    await route.fulfill({json:{ok:true}});
  };
  const refresh=()=>page.evaluate(async()=>{while(refreshing)await new Promise(resolve=>setTimeout(resolve,10));await refresh()});
  await page.route('**/api/state',feed);await page.route('**/api/evict',evict);
  try{
    await page.setViewportSize({width:1440,height:1000});await refresh();
    await page.locator(`#taskList [data-task="${task.id}"] .task-title`).click();
    const button=page.getByRole('button',{name:'Evict task',exact:true});
    assert.equal(await button.count(),1,'A shared task has an Evict action');
    assert.match(await page.locator('#taskDetail').textContent(),/this device only/i);
    assert.match(await page.locator('#taskStatusCounts').textContent(),/1 idle/);
    assert.ok(!await page.evaluate(id=>prism.snapshot().activity.includes(id),line.id),'Idle task keeps its Line without animation');
    await button.focus();await refresh();
    assert.equal(await button.evaluate(node=>node===document.activeElement),true,'Polling preserves keyboard focus');
    await page.screenshot({path:path.join(root,'test-results/task-eviction-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await button.scrollIntoViewIfNeeded();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(root,'test-results/task-eviction-mobile.png'),fullPage:true});
    await button.click();
    await page.waitForFunction(()=>document.body.textContent.includes('Task changed. Refresh before evicting.'));
    assert.equal(await page.locator(`#taskList [data-task="${task.id}"]`).count(),1,'Failure retains the task');
    assert.deepEqual(requests,[{id:task.id,evictionToken:task.evictionToken}]);
    fail=false;await button.focus();await page.keyboard.press('Enter');
    await page.waitForFunction(id=>!state.tasks.some(task=>task.id===id),task.id);
    assert.equal(await button.count(),0);
    assert.equal(await page.locator('#tasksTitle').evaluate(node=>node===document.activeElement),true,'Eviction restores focus to a surviving control');
    assert.equal(await page.evaluate(id=>state.lines.find(line=>line.id===id).task,line.id),null);
    snapshot.tasks.push({...task,evictionToken:'b'.repeat(64)});line.task=task.id;await refresh();
    await page.locator(`#taskList [data-task="${task.id}"] .task-title`).click();
    delete snapshot.tasks.at(-1).evictionToken;await refresh();
    assert.equal(await button.count(),0,'Legacy tasks without eviction capability have no button');
  }finally{
    await page.unroute('**/api/state',feed);await page.unroute('**/api/evict',evict);
    await page.setViewportSize(viewport);
    await page.evaluate(()=>{selected.clear();taskFocus=null;document.activeElement.blur()});await refresh();
  }
};
