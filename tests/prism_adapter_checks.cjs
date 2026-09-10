const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function adapter() {
  const context = {window:{}};
  const source = path.join(__dirname,'../bridge/prism-adapters.js');
  if (fs.existsSync(source)) vm.runInNewContext(fs.readFileSync(source,'utf8'),context);
  assert.equal(typeof context.window.PrismAdapters?.fromState,'function','The packaged wall exposes the sanitized graph adapter');
  return context.window.PrismAdapters;
}
function fixture() {
  return {connector_layout:{version:1,nodes:[{id:'left',x:-180,y:0},{id:'hub',x:0,y:0},{id:'right',x:180,y:0}],lines:[
    {id:'1:2',number:7,a:'left',b:'hub',zoneIds:[2,1]},
    {id:'3:4',number:2,a:'hub',b:'right',zoneIds:[3,4]}]},
    lines:[{id:'1:2',number:7},{id:'3:4',number:2}],settings:{rotation:0,flip_x:0,flip_y:0}};
}
const colors=()=>['#33aaff','#ffee33'];
test('sanitized graph adapter applies presentation transforms exactly once and retains identities',()=>{
  const api=adapter();
  for(const rotation of [0,90,180,270])for(const flip_x of [0,1])for(const flip_y of [0,1]){
    const state=fixture();Object.assign(state.settings,{rotation,flip_x,flip_y});
    const before=JSON.stringify(state),layout=api.fromState(state,colors),angle=rotation*Math.PI/180;
    assert.equal(JSON.stringify(state),before,'Adapter is read-only');
    assert.equal(JSON.stringify(layout.lines.map(l=>[l.id,l.number,l.zoneIds,l.colors])),JSON.stringify([
      ['1:2',7,[2,1],colors()],['3:4',2,[3,4],colors()]]));
    const left=layout.nodes.find(n=>n.id==='left');
    assert(Math.abs(left.x-(-180*Math.cos(angle)*(flip_x?-1:1)))<1e-8);
    assert(Math.abs(left.y-(-180*Math.sin(angle)*(flip_y?-1:1)))<1e-8);
    assert(Math.abs(Math.hypot(left.x,left.y)-180)<1e-8);
    assert.equal(layout.rootId,undefined,'No controller-root override');
  }
});
test('adapter rejects partial identity/color/geometry updates before they can replace the current layout',()=>{
  const api=adapter();
  for(const mutate of [s=>s.lines.pop(),s=>s.connector_layout.version=9,s=>s.connector_layout.lines[0].a='missing',s=>s.connector_layout.nodes[0].x=NaN,s=>s.lines[0].number=99,s=>s.connector_layout.lines[0].zoneIds=[1,1]]){
    const state=fixture();mutate(state);assert.throws(()=>api.fromState(state,colors));
  }
  assert.throws(()=>api.fromState(fixture(),()=>['url(secret)','red']));
});
test('packaged components expose independent two-second assembly and flow with stable graph roots',()=>{
  const context={window:{}};
  const source=path.join(__dirname,'../bridge/prism.js');
  if(fs.existsSync(source))vm.runInNewContext(fs.readFileSync(source,'utf8'),context);
  assert.equal(typeof context.window.Prism?.validate,'function','The packaged crystal components expose validated graph rendering');
  const api=context.window.Prism,layout=api.validate(adapter().fromState(fixture(),colors));
  assert.equal(api.constants.assemblySeconds,2);
  assert.equal(api.constants.flowSeconds,2);
  assert.equal(JSON.stringify(layout.rootIds),JSON.stringify(['hub']));
  assert.equal(JSON.stringify(layout.lines.map(l=>l.zoneIds)),JSON.stringify([[2,1],[3,4]]));
  assert.equal(layout.lines[0].start,layout.lines[1].start,'Hub Lines start together');
  assert.throws(()=>api.validate({...fixture().connector_layout,nodes:[...fixture().connector_layout.nodes,{id:'unused',x:30,y:40}]}));
});
test('the saved 15-Line graph retains topology, length and zone ownership through every presentation transform',()=>{
  const context={window:{}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../bridge/prism.js'),'utf8'),context);
  const graph=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/lines-connectors.json'),'utf8'));
  const api=adapter();let baseline;
  for(const rotation of [0,90,180,270])for(const flip_x of [0,1])for(const flip_y of [0,1]){
    const state={connector_layout:graph,lines:graph.lines,settings:{rotation,flip_x,flip_y}};
    const layout=context.window.Prism.validate(api.fromState(state,colors));
    assert.equal(layout.lines.length,15);assert.equal(layout.nodes.length,12);
    const topology=layout.lines.map(l=>[l.id,l.number,layout.nodes[l.a].id,layout.nodes[l.b].id,l.zoneIds]);
    assert.equal(JSON.stringify(topology),JSON.stringify(graph.lines.map(l=>[l.id,l.number,l.a,l.b,l.zoneIds])));
    baseline??=layout.lines.map(l=>l.length);
    layout.lines.forEach((l,i)=>{assert(Math.abs(l.length-baseline[i])<1e-7);assert(l.da>=context.window.Prism.constants.faceDistance-1e-7);assert(l.db>=context.window.Prism.constants.faceDistance-1e-7)});
  }
});
test('equally connected roots use junction spread, box center, and stable identity regardless of input order',()=>{
 const context={window:{}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../bridge/prism.js'),'utf8'),context);
 const shape={version:1,nodes:[{id:'z',x:0,y:0},{id:'a',x:200,y:0},{id:'b',x:100,y:Math.sqrt(3)*100}],lines:[{id:'za',a:'z',b:'a'},{id:'ab',a:'a',b:'b'},{id:'bz',a:'b',b:'z'}]};
 const expected=context.window.Prism.validate(shape).rootIds[0];
 for(const nodes of [[...shape.nodes].reverse(),[shape.nodes[1],shape.nodes[2],shape.nodes[0]]])assert.equal(context.window.Prism.validate({...shape,nodes}).rootIds[0],expected);
 // A symmetric hexagon has equal degree, spread and distance to center. Identity breaks the final tie.
 const nodes=Array.from({length:6},(_,i)=>({id:['z','f','e','d','c','a'][i],x:200*Math.cos(i*Math.PI/3),y:200*Math.sin(i*Math.PI/3)}));
 const lines=nodes.map((node,i)=>({id:'edge'+i,a:node.id,b:nodes[(i+1)%6].id}));
 assert.equal(context.window.Prism.validate({version:1,nodes,lines}).rootIds[0],'a');
});
