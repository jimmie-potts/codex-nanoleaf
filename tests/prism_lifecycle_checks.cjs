const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
module.exports=async function(page,root){
 const wasPaused=await page.evaluate(()=>{const paused=prism.pauseReasons.has('manual');prism.pause();return paused});
 try {
 const result=await page.evaluate(async()=>{
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const actual=PrismAdapters.fromState(state,zoneColors),host=document.createElement('div');
  host.style.cssText='position:fixed;inset:0;background:#071019;z-index:9999';document.body.append(host);
  let callbacks=0;
  const renderer=new Prism.Renderer(host,actual,{animate:false,onFrame(){callbacks++}});
  renderer.setActivity(actual.lines.map(line=>line.id));await wait(120);
  const moving=callbacks;renderer.setMode('quiet');await wait(80);const quietStart=callbacks;await wait(100);const quietEnd=callbacks;
  renderer.setMode('work');await wait(100);const resumed=callbacks;
  renderer.pause();await wait(50);const pauseStart=callbacks;await wait(100);const pauseEnd=callbacks;renderer.resume();
  host.remove();await wait(50);const removedStart=callbacks;await wait(100);const removedEnd=callbacks;
  const removed={destroyed:renderer.destroyed,frame:renderer.frameId};
  const invalidHost=document.createElement('div');document.body.append(invalidHost);let invalidError=false;
  try{new Prism.Renderer(invalidHost,{version:99})}catch{invalidError=true}invalidHost.remove();
  return {moving,quietStart,quietEnd,resumed,pauseStart,pauseEnd,removedStart,removedEnd,removed,invalidError};
 });
 assert(result.moving>0,'Active visible Work draws frames');
 assert.equal(result.quietEnd,result.quietStart,'Quiet stops scheduling frames');
 assert(result.resumed>result.quietEnd,'Work resumes the same renderer');
 assert.equal(result.pauseEnd,result.pauseStart,'Pause has no animation callbacks');
 assert.equal(result.removedEnd,result.removedStart,'Removal disposes animation callbacks');
 assert.equal(result.removed.destroyed,true);assert.equal(result.removed.frame,0);assert(result.invalidError);
 const frames=await page.evaluate(async()=>{
  const measure=async(layout)=>{
   const host=document.createElement('div');host.style.cssText='position:fixed;inset:0;background:#071019;z-index:9999';document.body.append(host);
   const renderer=new Prism.Renderer(host,layout,{animate:false});renderer.setActivity(layout.lines.map(line=>line.id));
   const times=[];let previous;
   await new Promise(resolve=>{let count=0;const tick=now=>{if(previous!==undefined)times.push(now-previous);previous=now;if(++count>=121)resolve();else requestAnimationFrame(tick)};requestAnimationFrame(tick)});
   renderer.destroy();host.remove();times.sort((a,b)=>a-b);
   return {lines:layout.lines.length,nodes:layout.nodes.length,frames:times.length,medianMs:times[Math.floor(times.length*.5)],p95Ms:times[Math.floor(times.length*.95)],maxMs:times.at(-1)};
  };
  const actual=PrismAdapters.fromState(state,zoneColors),nodes=[],lines=[];
  for(let row=0;row<5;row++)for(let col=0;col<5;col++)nodes.push({id:`${row}:${col}`,x:col*200+row*100,y:row*Math.sqrt(3)*100});
  for(let row=0;row<5;row++)for(let col=0;col<5;col++)for(const [dr,dc]of[[0,1],[1,0],[1,-1]]){const nr=row+dr,nc=col+dc;if(nr<5&&nc>=0&&nc<5)lines.push({id:'synthetic-'+lines.length,number:lines.length+1,a:`${row}:${col}`,b:`${nr}:${nc}`,colors:['#33aaff','#ffcc44']})}
  return {browser:navigator.userAgent,viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},actual:await measure(actual),synthetic:await measure({version:1,nodes,lines}),note:'Visible active Work, upper glow, 120 RAF intervals. Synthetic fixture is a 5 by 5 triangular lattice, 56 Lines. Measurements describe this runner, not a 300-Line guarantee.'};
 });
 fs.writeFileSync(path.join(root,'test-results/prism-frame-measurements.json'),JSON.stringify(frames,null,2)+'\n');
 assert.equal(frames.actual.lines,15);assert.equal(frames.synthetic.lines,56);
 console.log('Prism frame measurements: '+JSON.stringify(frames));
 } finally {if(!wasPaused)await page.evaluate(()=>prism.resume())}
};
