// Same packaged geometry and route solver as the map; no browser device overrides.
'use strict';
const path = require('node:path');
const base = path.join(__dirname, '../web/static/campus3d');
const data = require(path.join(base, 'campus-data.js'));
const models = require(path.join(base, 'campus-footprints.js'));
const layout = require(path.join(base, 'campus-layout.js'));
const routing = require(path.join(base, 'campus-routing.js'));
layout.calibrate(data, models);
for (const file of ['teaching-trace.js','dorm-trace.js','academic-trace.js']) require(path.join(base,file)).apply(data,models);
require(path.join(base,'special-trace.js')).apply(data,models,layout);
const obstacles=[];
const places=[...data.buildings,...(data.regions||[])].map(b=>{
    const t=data.defaultTransforms[b.id]||{};
    const x=b.x+(t.dx||0),z=b.z+(t.dz||0),r=(t.rot||0)*Math.PI/180;
    const transform=([a,c])=>[x+a*Math.cos(r)+c*Math.sin(r),z-a*Math.sin(r)+c*Math.cos(r)];
    if(models[b.id]) for(const outline of [models[b.id].outer,...(models[b.id].links||[]).map(l=>l.outline)]) obstacles.push({id:b.id,polygon:outline.map(transform)});
    if(b.kind==='lake'&&b.outline) obstacles.push({id:b.id,polygon:b.outline.map(([a,c])=>[b.x+(t.dx||0)+(a-b.x)*Math.cos(r)+(c-b.z)*Math.sin(r),b.z+(t.dz||0)-(a-b.x)*Math.sin(r)+(c-b.z)*Math.cos(r)])});
    return {id:b.id,name:b.name,kind:b.kind,point:[x,z]};
});
function run(from,to){
    if(from==='--places') return {places:places.map(({id,name,kind})=>({id,name,kind}))};
    const a=places.find(p=>p.id===from),b=places.find(p=>p.id===to);
    if(!a||!b)return {status:'not_found',message:'起点或终点不在保存的地图中。'};
    // Lake access needs a bank endpoint, not its centre; do not route through water.
    if(a.kind==='lake'||b.kind==='lake')return {status:'no-access',message:'湖泊需指定岸边入口，当前不从水面中心规划路线。'};
    const roads=layout.roads.map(r=>({...r,points:r.points.map(layout.world)}));
    const result=routing.findRoute(roads,a,b,{obstacles});
    // World units are schematic. Do not convert them to real metres/minutes.
    return {status:result.status,points:result.points||[],from_id:a.id,to_id:b.id,from_name:a.name,to_name:b.name,
            map_basis:'项目保存的默认示意路网，不含浏览器自定义布局或实时路况'};
}
if(require.main===module) process.stdout.write(JSON.stringify(run(process.argv[2],process.argv[3])));
module.exports={run};
