const assert=require('node:assert/strict');
module.exports=async function(page){
  assert.equal(await page.locator('#wall.prism-scene').count(),1,'The live map uses the approved crystal renderer');
  const structure=await page.evaluate(()=>({
    graph:state.connector_layout,
    lines:[...document.querySelectorAll('#wall [data-edge]')].map(n=>n.dataset.lineId),
    nodes:[...document.querySelectorAll('#wall [data-node-id]')].map(n=>n.dataset.nodeId),
    rims:document.querySelectorAll('#wall [data-rim]').length,
    regions:document.querySelectorAll('#wall .wall-line[role=button]').length,
  }));
  assert.equal(structure.lines.length,15);
  assert.deepEqual(structure.lines.slice().sort(),structure.graph.lines.map(l=>l.id).sort());
  assert.deepEqual(structure.nodes.slice().sort(),structure.graph.nodes.map(n=>n.id).sort());
  assert.equal(structure.rims,structure.nodes.length*6,'Each connector has six permanent border sections');
  assert.equal(structure.regions,15,'Every physical Line retains its local selection target');
};
