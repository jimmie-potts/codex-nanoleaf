module.exports=async function(page,port,root){
const path=require("node:path");const errors=[];page.on("pageerror",e=>errors.push(e.message));
await page.goto('http://127.0.0.1:'+port);await page.waitForSelector('.wall-line');if(await page.locator('.wall-line').count()!==15)throw Error('Expected 15 Lines');
await page.evaluate(async()=>{await action('/api/assign',{lines:Object.fromEntries(state.lines.map(l=>[l.id,{project:null,signature:0}]))});await action('/api/settings',{style:'classic',coverage:'whole',rotation:0,flip_x:0,flip_y:0});await action('/api/mode',{mode:'work'})});
await page.locator('#project').click();await page.waitForFunction(()=>document.querySelector('#project').classList.contains('active'));
const ids=await page.locator('.wall-line').evaluateAll(nodes=>nodes.map(n=>n.dataset.line));
await page.locator(`[data-line="${ids[0]}"]`).click();await page.locator(`[data-line="${ids[1]}"]`).click({modifiers:['Control']});
await page.locator('#assignProject').selectOption('a');await page.locator('#assign').click();await page.waitForFunction(()=>state.lines.filter(l=>l.project==='a').length===2);
await page.locator('[aria-label="Notification Service color"]').evaluate(n=>{n.value='#9966ff';n.dispatchEvent(new Event('change',{bubbles:true}))});await page.waitForFunction(()=>state.projects.find(p=>p.id==='a').color==='#9966ff');
await page.locator('#swap').click();await page.waitForFunction(()=>state.lines.filter(l=>l.project==='a').every(l=>l.signature===1));
await page.locator('#coverage').selectOption('status');await page.waitForFunction(()=>state.settings.coverage==='status');
await page.locator('#rotate').click();await page.waitForFunction(()=>state.settings.rotation===90);await page.locator('#rotate').click();await page.waitForFunction(()=>state.settings.rotation===180);await page.locator('#rotate').click();await page.waitForFunction(()=>state.settings.rotation===270);await page.locator('#rotate').click();await page.waitForFunction(()=>state.settings.rotation===0);
await page.locator('#flipX').click();await page.waitForFunction(()=>state.settings.flip_x===1);await page.locator('#flipX').click();await page.waitForFunction(()=>state.settings.flip_x===0);
await page.locator(`[data-line="${ids[0]}"]`).click();await page.locator('#locate').click();
await page.locator('#free').click();await page.waitForFunction(()=>state.mode==='free');if(!await page.locator('#locate').isDisabled())throw Error('Locate must be disabled in Free');
await page.locator('#work').click();await page.waitForFunction(()=>state.mode==='work');await page.locator('#classic').click();await page.waitForFunction(()=>state.settings.style==='classic');await page.locator('#project').click();await page.waitForFunction(()=>state.settings.style==='project');
await page.locator('#taskList .task').first().click();await page.locator('[aria-label="Task project override"]').selectOption('b');await page.waitForFunction(()=>state.tasks[0].manual==='b');await page.locator('[aria-label="Task project override"]').selectOption('');await page.waitForFunction(()=>!state.tasks[0].manual);
await page.locator(`[data-line="${ids[0]}"]`).focus();await page.waitForTimeout(1100);if(await page.evaluate(()=>document.activeElement.dataset.line)!==ids[0])throw Error('Map polling lost keyboard focus');
await page.evaluate(()=>{state.pending={settings:{style:'classic'},lines:{[state.lines[0].id]:{project:'a'}},tasks:{}};render()});if(!await page.locator('#busy').textContent().then(t=>t.includes('classic layout')&&t.includes('Notification Service')))throw Error('Pending change details missing');if(await page.locator('.wall-line.pending').count()!==1)throw Error('Pending Line highlight missing');await page.evaluate(()=>refresh());
if(await page.locator('#taskList b').count())throw Error('Task title interpreted as HTML');
await page.screenshot({path:path.join(root,'test-results/wall-map-desktop.png'),fullPage:true});
await page.setViewportSize({width:800,height:1000});await page.screenshot({path:path.join(root,'test-results/wall-map-compact.png'),fullPage:true});
if(errors.length)throw Error(errors.join('\n'));console.log('Browser checks passed: map geometry, multi-select, assignments, colors, half swaps, coverage, rotation, flip, Locate, modes, profiles, and title escaping.');

};
