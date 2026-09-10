'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {performance}=require('node:perf_hooks');
const labels=require('../bridge/prism-labels.js');

function runtimeValidate(){
  const sandbox={window:{}};
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../bridge/prism.js'),'utf8'),sandbox,{filename:'bridge/prism.js'});
  return sandbox.window.Prism.validate;
}
function poseGraph(fixture,rotation,flipX,flipY){
  const radians=rotation*Math.PI/180,c=Math.cos(radians),s=Math.sin(radians);
  return {...fixture,nodes:fixture.nodes.map(node=>({...node,x:(node.x*c-node.y*s)*(flipX?-1:1),y:(node.x*s+node.y*c)*(flipY?-1:1)}))};
}
function screenGeometry(layout,canvas){
  const xs=layout.nodes.map(node=>node.x),ys=layout.nodes.map(node=>node.y),margin=95;
  let x=Math.min(...xs)-margin,y=Math.min(...ys)-margin;
  for(const rootIndex of layout.roots){
    const root=layout.nodes[rootIndex],members=layout.nodes.filter(node=>node.root===rootIndex);
    const reach=Math.max(...members.map(node=>Math.hypot(node.x-root.x,node.y-root.y)));
    x=Math.min(x,root.x-reach*.28-margin);y=Math.min(y,root.y-reach*.28-margin);
  }
  const width=Math.max(...xs)+margin-x,height=Math.max(...ys)+margin-y;
  const scale=Math.min(canvas.width/width,canvas.height/height);
  const offsetX=(canvas.width-width*scale)/2-x*scale,offsetY=(canvas.height-height*scale)/2-y*scale;
  const point=value=>({x:value.x*scale+offsetX,y:value.y*scale+offsetY});
  return {scale,canvas:{width:canvas.width,height:canvas.height},nodes:layout.nodes.map(node=>({id:node.id,...point(node)})),lines:layout.lines.map(line=>{
    const node=layout.nodes[line.a],angle=line.angle*Math.PI/180;
    const start={x:node.x+Math.cos(angle)*line.da,y:node.y+Math.sin(angle)*line.da};
    const end={x:start.x+Math.cos(angle)*line.tubeLength,y:start.y+Math.sin(angle)*line.tubeLength};
    // Model measured multi-digit luminous numerals wider than the 24 px minimum.
    const measuredWidth=line.number>=10?30:24;
    return {id:line.id,number:line.number,start:point(start),end:point(end),width:measuredWidth,height:24,fontSizePx:11};
  })};
}

const validate=runtimeValidate();
const fixture=JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'fixtures/lines-connectors.json'),'utf8'));
const canvases=[{browserWidth:1440,width:816,height:800},{browserWidth:800,width:524,height:340},{browserWidth:390,width:362,height:340}];
const settings=[];
for(const rotation of [0,90,180,270])for(const flipX of [0,1])for(const flipY of [0,1])settings.push({rotation,flipX,flipY});
const runs=[];
for(const canvas of canvases)for(const setting of settings){
  const layout=validate(poseGraph(fixture,setting.rotation,setting.flipX,setting.flipY));
  assert.equal(layout.lines.length,15);assert.equal(layout.nodes.length,12);
  assert.ok(Math.abs([...layout.lines].sort((a,b)=>a.length-b.length)[7].length-200)<1e-9,'Uses Prism runtime normalization.');
  const geometry=screenGeometry(layout,canvas),start=performance.now(),result=labels.placeLabels(geometry),elapsedMs=performance.now()-start;
  assert.equal(result.ok,true,`${canvas.browserWidth}px ${JSON.stringify(setting)} ${JSON.stringify(result.unsolved)}`);
  assert.equal(result.placements.length,15);assert.deepEqual(labels.validatePlacement(result),[]);
  assert.deepEqual(result.placements.map(item=>item.id),fixture.lines.map(item=>item.id),'Keeps saved Line IDs and order.');
  assert.ok(result.placements.every(item=>item.width>=24&&item.height>=24&&item.fontSizePx>=11));
  assert.deepEqual(labels.placeLabels(geometry).placements,result.placements,'Same geometry has stable placements.');
  runs.push({elapsedMs,...result.metrics,worstRank:Math.max(...result.placements.map(item=>item.rank))});
}
assert.equal(settings.length,16);assert.equal(runs.length,48);
const base=validate(poseGraph(fixture,0,0,0));
const impossible=labels.placeLabels(screenGeometry(base,{width:30,height:30}));
assert.equal(impossible.ok,false);assert.equal(impossible.failureReason,'static-exhaustion');assert.deepEqual(labels.validatePlacement(impossible),[]);
const limited=labels.placeLabels(screenGeometry(base,canvases[2]),{maxSearchNodes:1});
assert.equal(limited.ok,false);assert.equal(limited.failureReason,'search-limit');assert.deepEqual(labels.validatePlacement(limited),[]);
const arbitrary={scale:1,canvas:{width:200,height:200},nodes:[{id:'shared',x:20,y:20}],lines:[{id:'shared',number:1,start:{x:60,y:100},end:{x:140,y:100},width:24,height:24,fontSizePx:11}]};
assert.doesNotThrow(()=>labels.placeLabels(arbitrary),'Connector and Line identity namespaces are independent.');
assert.throws(()=>labels.placeLabels({...arbitrary,nodes:[...arbitrary.nodes,...arbitrary.nodes]}),/Invalid screen connector/);
const elapsed=runs.map(run=>run.elapsedMs).sort((a,b)=>a-b);
console.log(JSON.stringify({result:'pass',cases:runs.length,labels:runs.length*15,settings:settings.length,canvasWidths:canvases.map(item=>item.browserWidth),maxSearchNodesUsed:Math.max(...runs.map(run=>run.searchNodes)),maxCandidatesPerLine:Math.max(...runs.map(run=>run.maxCandidatesPerLine)),maxStaticCandidateChecks:Math.max(...runs.map(run=>run.staticCandidateChecks)),maxCompatibilityCandidateChecks:Math.max(...runs.map(run=>run.compatibilityCandidateChecks)),maxLabelComparisons:Math.max(...runs.map(run=>run.labelComparisons)),worstRank:Math.max(...runs.map(run=>run.worstRank)),elapsedMs:{median:elapsed[Math.floor(elapsed.length/2)],max:Math.max(...elapsed)},fallbacks:{impossible:{reason:impossible.failureReason,safe:impossible.placements.length,unsolved:impossible.unsolved.length},limited:{reason:limited.failureReason,safe:limited.placements.length,unsolved:limited.unsolved.length}}},null,2));
