'use strict';
const assert=require('node:assert/strict');

// Issue #26: labels are a browser-local identification layer. This module
// measures rendered DOM geometry independently of the placement solver.
module.exports=async function(page){
  const settle=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const refresh=()=>page.evaluate(async()=>{while(refreshing)await new Promise(resolve=>setTimeout(resolve,10));await refresh()});
  await page.evaluate(()=>{try{localStorage.removeItem('wall.numbers.showAll');localStorage.setItem('wall.assembly.opening','0');localStorage.setItem('wall.assembly.entry','0')}catch{}});
  await page.reload();await page.waitForSelector('#wall.prism-scene .wall-line[data-line]');await settle();
  assert.equal(await page.locator('#showNumbers').getAttribute('aria-pressed'),'false','Show-all defaults off in this browser.');
  assert.equal(await page.locator('.number-tag:visible').count(),0,'Idle number labels start hidden.');

  const missingAsset=route=>route.abort();await page.route('**/assets/prism-labels.js',missingAsset);
  try{
    await page.reload();await page.waitForSelector('#wall.prism-scene .wall-line[data-line]');await settle();
    assert.equal(await page.locator('#showNumbers').isDisabled(),true,'A missing solver disables show-all.');
    assert.match(await page.locator('#notice').textContent(),/Line controls remain available/);
    assert.equal(await page.locator('.number-tag:visible').count(),0,'A missing solver never exposes stale or overlapping labels.');
    assert.equal(await page.locator('.wall-line[role="button"]').count(),15,'Every accessible Line control remains available.');
  }finally{await page.unroute('**/assets/prism-labels.js',missingAsset)}
  await page.reload();await page.waitForSelector('#wall.prism-scene .wall-line[data-line]');await settle();

  await page.evaluate(()=>{$('wallHost').style.display='none';sizePrismNumbers()});await settle();
  await page.evaluate(()=>{$('wallHost').style.display='';sizePrismNumbers()});await settle();
  assert.equal(await page.locator('.number-tag[data-label-layout="placed"]').count(),15,'A hidden zero-size host defers placement and resumes safely when visible.');

  const first=page.locator('.wall-line[data-line]').first(),id=await first.getAttribute('data-line');
  const tag=page.locator(`.number-tag[data-line-id="${id}"]`);
  await first.click();assert.equal(await tag.isVisible(),true,'Selection reveals its number.');
  await page.evaluate(()=>highlightAssociations());
  assert.ok(await page.locator(`.line-badge[data-line-id="${id}"].selected`).count(),'The existing association highlighter remains connected to Line identity.');
  await page.locator('#selectionTitle').focus();await page.evaluate(()=>{selected.clear();drawWall();prism.setHighlights([])});assert.equal(await tag.isVisible(),true,'Removing selection retains the number while pointer hover still applies.');
  await page.mouse.move(0,0);assert.equal(await tag.isVisible(),false,'Removing the final visibility reason hides an idle number.');
  await page.evaluate(value=>prism.setHighlights([value]),id);assert.equal(await tag.isVisible(),true,'External highlights reveal their numbers.');
  await page.evaluate(()=>prism.setHighlights([]));assert.equal(await tag.isVisible(),false,'Clearing an external highlight restores idle visibility.');
  await first.hover();assert.equal(await tag.isVisible(),true,'Hover reveals its number.');
  await page.mouse.move(0,0);assert.equal(await tag.isVisible(),false,'Pointer exit hides an otherwise idle number.');
  await first.focus();assert.equal(await tag.isVisible(),true,'Keyboard focus reveals its number.');
  await page.locator('#selectionTitle').focus();assert.equal(await tag.isVisible(),false,'Blur restores idle visibility.');

  await first.focus();await page.evaluate(value=>prism.setHighlights([value]),id);
  await page.locator('#selectionTitle').focus();assert.equal(await tag.isVisible(),true,'Highlight retains the number after keyboard blur.');
  await first.focus();await page.evaluate(()=>prism.setHighlights([]));assert.equal(await tag.isVisible(),true,'Focus retains the number after highlight clears.');
  await page.locator('#selectionTitle').focus();assert.equal(await tag.isVisible(),false,'Removing both reasons hides the number.');

  const touchContext=await page.context().browser().newContext({hasTouch:true,viewport:{width:390,height:844}});
  try{
    const touch=await touchContext.newPage(),touchWrites=[];
    touch.on('request',request=>{if(request.method()!=='GET')touchWrites.push(request.url())});
    await touch.addInitScript(()=>localStorage.setItem('wall.assembly.opening','0'));
    await touch.goto(page.url());await touch.waitForSelector('#wall.prism-scene .wall-line');
    const target=touch.locator('.wall-line[data-line]').first(),touchId=await target.getAttribute('data-line');
    await target.tap();
    assert.equal(await target.getAttribute('aria-pressed'),'true','An actual touch-capable browser tap selects the physical Line.');
    assert.equal(await touch.locator(`.number-tag[data-line-id="${touchId}"]`).isVisible(),true,'Touch selection retains the number without pointer hover.');
    assert.deepEqual(touchWrites,[],'A touch selection sends no write request.');
  }finally{await touchContext.close()}

  const writes=[],record=request=>{if(request.method()!=='GET')writes.push(request.url())};page.on('request',record);
  try{
    await first.dispatchEvent('pointerdown',{pointerType:'touch',isPrimary:true});await first.dispatchEvent('click',{pointerType:'touch'});
    assert.equal(await tag.isVisible(),true,'Touch selection keeps the number visible after the gesture.');
    await page.locator('#showNumbers').click();
    assert.equal(await page.locator('#showNumbers').getAttribute('aria-pressed'),'true');
    assert.equal(await page.evaluate(()=>localStorage.getItem('wall.numbers.showAll')),'1','Show-all preference stays browser-local.');
    assert.equal(await page.locator('.number-tag:visible').count(),15,'Show-all reveals all saved numbers.');
    assert.deepEqual(writes,[],'Selection and label visibility do not make write requests.');
  }finally{page.off('request',record)}

  await page.reload();await page.waitForSelector('#wall.prism-scene .wall-line');await settle();
  assert.equal(await page.locator('#showNumbers').getAttribute('aria-pressed'),'true','Show-all survives reload in the same browser.');
  assert.equal(await page.locator('.number-tag:visible').count(),15);
  const original=await page.evaluate(()=>structuredClone(state)),snapshot=structuredClone(original);
  const route=request=>request.fulfill({json:snapshot});await page.route('**/api/state',route);
  const stable=new Map();
  try{
    for(const mode of ['work','quiet','free'])for(const reduced of ['no-preference','reduce']){
      snapshot.mode=mode;await page.emulateMedia({reducedMotion:reduced});await refresh();await settle();
      const labels=await page.locator('.number-tag').evaluateAll(nodes=>nodes.map(tag=>({fill:getComputedStyle(tag.querySelector('.number')).fill,number:tag.querySelector('.number').textContent,visible:getComputedStyle(tag).visibility})));
      assert.ok(labels.every(label=>label.fill==='rgb(231, 245, 255)'&&label.visible==='visible'),'Neutral readable numeral cores persist across mode and reduced-motion settings.');
      for(const line of snapshot.lines)assert.match(await page.locator(`.wall-line[data-line="${line.id}"]`).getAttribute('aria-label'),new RegExp('^Line '+line.number+' ·'));
    }
    snapshot.mode=original.mode;await page.emulateMedia({reducedMotion:'no-preference'});
    for(const width of [1440,800,390])for(const rotation of [0,90,180,270])for(const flipX of [0,1])for(const flipY of [0,1]){
      await page.setViewportSize({width,height:width===1440?1000:844});
      snapshot.settings={...snapshot.settings,rotation,flip_x:flipX,flip_y:flipY};await refresh();await settle();
      const layout=await page.evaluate(()=>{const canvas=document.querySelector('.canvas').getBoundingClientRect(),legend=document.querySelector('.legend').getBoundingClientRect(),inspector=document.querySelector('#inspector').getBoundingClientRect();return{canvasBottom:canvas.bottom,legendBottom:legend.bottom,inspectorTop:inspector.top}});
      assert.ok(layout.legendBottom<=layout.canvasBottom+1,`${width}px legend remains inside its canvas section`);
      if(width<=1049)assert.ok(layout.legendBottom<=layout.inspectorTop,`${width}px legend does not overlap the inspector`);
      const measured=await page.evaluate(()=>{
        const canvas=document.querySelector('#wallHost').getBoundingClientRect(),clearance=1;
        const rectShape=r=>[{x:r.left,y:r.top},{x:r.right,y:r.top},{x:r.right,y:r.bottom},{x:r.left,y:r.bottom}];
        const quad=element=>{
          const box=element.getBBox(),style=getComputedStyle(element),stroke=(parseFloat(style.strokeWidth)||0)/2,matrix=element.getScreenCTM();
          return [[box.x-stroke,box.y-stroke],[box.x+box.width+stroke,box.y-stroke],[box.x+box.width+stroke,box.y+box.height+stroke],[box.x-stroke,box.y+box.height+stroke]].map(([x,y])=>{const p=new DOMPoint(x,y).matrixTransform(matrix);return{x:p.x,y:p.y}});
        };
        const project=(shape,axis)=>{const values=shape.map(point=>point.x*axis.x+point.y*axis.y);return[Math.min(...values),Math.max(...values)]};
        const intersects=(a,b)=>{for(const shape of [a,b])for(let i=0;i<shape.length;i++){const next=shape[(i+1)%shape.length],edge={x:next.x-shape[i].x,y:next.y-shape[i].y},length=Math.hypot(edge.x,edge.y),axis={x:-edge.y/length,y:edge.x/length},pa=project(a,axis),pb=project(b,axis);if(pa[1]+clearance<pb[0]||pb[1]+clearance<pa[0])return false}return true};
        const obstacleElements=[...document.querySelectorAll('#wall [data-part="tube-body"],#wall [data-part="connector-rim"] [data-rim] > polygon:first-child,#wall [data-part="connector-pane"] > polygon,#wall [data-selection],#wall [data-highlight-ring],#wall [data-pending-ring]')];
        const obstacles=obstacleElements.map(element=>({name:element.getAttribute('data-part')||element.className.baseVal||element.tagName,shape:element.tagName==='polygon'?[...element.points].map(point=>{const p=new DOMPoint(point.x,point.y).matrixTransform(element.getScreenCTM());return{x:p.x,y:p.y}}):quad(element)}));
        const labels=[...document.querySelectorAll('#wall .number-tag')].map(tag=>{
          const hit=tag.querySelector('.number-hit').getBoundingClientRect(),texts=[...tag.querySelectorAll('[data-part="luminous-numeral"] text')].map(text=>{const box=text.getBoundingClientRect(),matrix=text.getScreenCTM();return{box:{left:box.left,right:box.right,top:box.top,bottom:box.bottom},font:parseFloat(getComputedStyle(text).fontSize)*Math.hypot(matrix.a,matrix.b)}});
          return{id:tag.dataset.lineId,layout:tag.dataset.labelLayout,transform:tag.getAttribute('transform'),hit:{left:hit.left,right:hit.right,top:hit.top,bottom:hit.bottom,width:hit.width,height:hit.height},texts};
        });
        const failures=[];
        for(const label of labels){
          const shape=rectShape(label.hit);
          if(label.layout!=='placed')failures.push(label.id+': '+label.layout);
          if(label.hit.width<24-.1||label.hit.height<24-.1)failures.push(label.id+': hit below 24px');
          if(label.hit.left<canvas.left+1||label.hit.right>canvas.right-1||label.hit.top<canvas.top+1||label.hit.bottom>canvas.bottom-1)failures.push(label.id+': outside canvas');
          if(label.texts.length!==2)failures.push(label.id+': missing shadow/core pair');
          for(const text of label.texts){if(text.font<11-.05)failures.push(label.id+': text below 11px');if(text.box.left<label.hit.left-.1||text.box.right>label.hit.right+.1||text.box.top<label.hit.top-.1||text.box.bottom>label.hit.bottom+.1)failures.push(label.id+': text outside hit envelope')}
          for(const obstacle of obstacles)if(intersects(shape,obstacle.shape))failures.push(label.id+': intersects '+obstacle.name);
        }
        for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++)if(intersects(rectShape(labels[i].hit),rectShape(labels[j].hit)))failures.push(labels[i].id+'/'+labels[j].id+': label overlap');
        return{failures,transforms:Object.fromEntries(labels.map(label=>[label.id,label.transform])),labels:labels.length};
      });
      assert.equal(measured.labels,15);assert.deepEqual(measured.failures,[],`${width}px rotation ${rotation} flip ${flipX}/${flipY}`);
      const key=[width,rotation,flipX,flipY].join(':');stable.set(key,measured.transforms);
      await page.locator('#showNumbers').click();await first.focus();await page.evaluate(value=>prism.setHighlights([value]),id);await settle();
      assert.deepEqual(await page.locator('.number-tag').evaluateAll(nodes=>Object.fromEntries(nodes.map(node=>[node.dataset.lineId,node.getAttribute('transform')]))),stable.get(key),'Visibility reasons do not move labels.');
      await page.evaluate(()=>prism.setHighlights([]));await page.locator('#selectionTitle').focus();await page.locator('#showNumbers').click();
    }
  }finally{await page.unroute('**/api/state',route);await page.evaluate(()=>{try{localStorage.removeItem('wall.numbers.showAll')}catch{}});await refresh()}
  console.log('Label clearance: 720 DOM labels across 48 canvas/transform cases passed independent hit, text, body, ring, connector, and edge checks.');
};
