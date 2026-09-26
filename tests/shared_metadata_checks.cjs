const assert=require('node:assert/strict');
const path=require('node:path');
module.exports=async function(page,root){
  const snapshot=await page.evaluate(()=>structuredClone(state));
  snapshot.tasks=[
    {id:'shared-local',title:'Shared hub task title',project:'a',status:'working'},
    {id:'shared-fallback-a',title:'Codex 5b1e07c2',project:null,status:'working'},
    {id:'shared-fallback-b',title:'Codex 4227761b',project:null,status:'unread'},
    {id:'shared-claude',title:'Claude shared title',project:null,status:'question'},
  ].map((task,i)=>({...task,line:snapshot.lines[i].id,statusEvidence:'current'}));
  snapshot.lines.forEach((line,i)=>{line.task=snapshot.tasks[i]?.id||null;line.project=null});
  snapshot.pending=null;
  const route=request=>request.fulfill({json:snapshot});
  const refresh=()=>page.evaluate(async()=>{while(refreshing)await new Promise(resolve=>setTimeout(resolve,10));await refresh()});
  const viewport=page.viewportSize();
  await page.route('**/api/state',route);
  try{
    await page.setViewportSize({width:1440,height:1000});
    await page.evaluate(()=>{selected.clear();taskFocus=null});
    await refresh();
    for(const task of snapshot.tasks){
      const row=page.locator(`#taskList [data-task="${task.id}"]`);
      assert.equal(await row.locator('.task-title').textContent(),task.title);
    }
    assert.match(await page.locator('#taskList [data-task="shared-local"]').textContent(),/Notification Service/);
    await page.locator('#taskList [data-task="shared-local"] .task-title').click();
    assert.match(await page.locator('#contextCard').textContent(),/Shared hub task title/);
    assert.match(await page.locator('#contextCard').textContent(),/Notification Service/);
    await page.screenshot({path:path.join(root,'test-results/shared-task-metadata.png'),fullPage:true});
    console.log('Shared metadata: shared titles and projects displayed on the context card; distinct provider/session fallback names retained.');
  }finally{
    await page.unroute('**/api/state',route);await page.setViewportSize(viewport);await refresh();
  }
};
