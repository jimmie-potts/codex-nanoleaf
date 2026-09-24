const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async function(page,root){
  const snapshot=await page.evaluate(()=>structuredClone(state));
  const task=snapshot.tasks[0],url='codex://threads/019a1234-5678-7123-8123-123456789abc';
  task.codexUrl=url;
  const route=request=>request.fulfill({json:snapshot});
  const refresh=()=>page.evaluate(async()=>{while(refreshing)await new Promise(resolve=>setTimeout(resolve,10));await refresh()});
  const viewport=page.viewportSize(),requests=[];
  const record=request=>requests.push([request.method(),request.url()]);
  await page.route('**/api/state',route);
  try{
    await page.setViewportSize({width:1440,height:1000});
    await refresh();
    await page.locator(`#taskList [data-task="${task.id}"] .task-title`).click();
    const link=page.getByRole('link',{name:'Open in Codex',exact:true});
    assert.equal(await link.count(),1,'Eligible task has a native link in its detail card');
    assert.equal(await link.getAttribute('href'),url);
    assert.equal(await link.getAttribute('target'),null);
    assert.equal(await page.locator('#taskList a').count(),0,'Task rows gain no navigation control');
    await page.getByLabel('Task project override').focus();
    await page.keyboard.press('Shift+Tab');
    assert.equal(await link.evaluate(n=>n===document.activeElement),true,'The link is in the normal keyboard order');
    page.on('request',record);
    // Exercise native activation. This headless Linux runner cannot verify the Windows protocol handler.
    await page.keyboard.press('Enter');
    await page.waitForTimeout(150);
    page.off('request',record);
    assert.ok(requests.every(([method,target])=>method==='GET'&&(target===url||new URL(target).pathname==='/api/state')),'Activation allows only the Codex navigation and normal state polling: '+JSON.stringify(requests));
    assert.equal(await link.getAttribute('href'),url);
    await link.evaluate(n=>n.blur());
    delete task.codexUrl;await refresh();
    assert.equal(await link.count(),0,'Polling removes a link whose eligibility disappears');
    task.codexUrl=url;await refresh();
    assert.equal(await link.getAttribute('href'),url,'Polling adds eligibility without reselection');
    task.codexUrl=url.replace('789abc','789def');await refresh();
    assert.equal(await link.getAttribute('href'),task.codexUrl,'URL changes refresh the card');
    assert.match(await page.locator('footer').textContent(),/Selecting here does not mark a task read/);
    assert.match(await page.locator('footer').textContent(),/Opening in Codex lets Codex mark it read/);
    await page.screenshot({path:path.join(root,'test-results/codex-link-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await link.scrollIntoViewIfNeeded();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Link fits narrow layout');
    assert.equal(await link.isVisible(),true);
    await page.screenshot({path:path.join(root,'test-results/codex-link-mobile.png'),fullPage:true});
  }finally{
    page.off('request',record);
    await page.unroute('**/api/state',route);
    await page.setViewportSize(viewport);
    await page.evaluate(()=>{selected.clear();taskFocus=null;document.activeElement.blur()});
    await refresh();
  }
};
