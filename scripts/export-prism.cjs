// Export the same SVG component factories used by the live wall. No browser or device required.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),context={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,'bridge/prism.js'),'utf8'),context);
const M=context.window.Prism.materials,p='asset-',out=path.join(root,'bridge/assets/prism');
const svg=(view,body,style='')=>`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${view}"><defs>${M.defs(p)+M.beamDefs(p,0)}</defs>${style?`<style>${style}</style>`:''}${body}</svg>\n`;
const files={
 'connector.svg':svg('-62 -62 124 124',M.connector(p)),
 'tube-shell-back.svg':svg('-138 -30 276 60',M.shell(p)),
 'tube-shell-front.svg':svg('-138 -30 276 60',M.front(p)),
 'tube-crystal.svg':svg('-145 -38 290 76',M.shell(p)+M.front(p)),
 'line-two-zones.svg':svg('-185 -75 370 150',M.tube(p,0),'[data-packet]{display:none}'),
 'luminous-number.svg':svg('-28 -20 56 40',M.numeral(p,'07')),
 'center-spark.svg':svg('-30 -30 60 60',M.tube(p,0),'[data-part]:not([data-part="center-spark"]){display:none}[data-spark]{opacity:1}'),
};
for(let i=0;i<6;i++)files[`connector-rim-${i}.svg`]=svg('-32 -32 64 64',M.rimPiece(p,i));
for(let z=0;z<2;z++)files[`zone-${z?'b':'a'}-light.svg`]=svg('-185 -75 370 150',M.tube(p,0),`[data-part="tube-body"],[data-part="tube-facets"],[data-spark],[data-packet],[clip-path="url(#${p}zone${1-z})"]{display:none}`);
fs.mkdirSync(out,{recursive:true});for(const [name,source]of Object.entries(files))fs.writeFileSync(path.join(out,name),source);
console.log(`Exported ${Object.keys(files).length} Prism vector components.`);
