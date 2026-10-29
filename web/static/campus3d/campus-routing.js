(function(root){'use strict';
const EPS=1e-7;
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const cross=(a,b)=>a[0]*b[1]-a[1]*b[0];
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]];
const lerp=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
function project(p,a,b){const v=sub(b,a),len=v[0]*v[0]+v[1]*v[1];const t=len?Math.max(0,Math.min(1,((p[0]-a[0])*v[0]+(p[1]-a[1])*v[1])/len)):0;return {t,point:lerp(a,b,t)};}
function intersection(a,b,c,d){const v=sub(b,a),w=sub(d,c),den=cross(v,w);if(Math.abs(den)<EPS)return null;const q=sub(c,a),t=cross(q,w)/den,u=cross(q,v)/den;return t>=-EPS&&t<=1+EPS&&u>=-EPS&&u<=1+EPS?{t:Math.max(0,Math.min(1,t)),u:Math.max(0,Math.min(1,u))}:null;}
function inside(p,poly){let yes=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
function blocked(a,b,obstacles,ignore){
 return obstacles.some(o=>{
  if(o.id===ignore)return false;
  const poly=o.polygon,ts=[0,1];
  for(let i=0;i<poly.length;i++){const hit=intersection(a,b,poly[i],poly[(i+1)%poly.length]);if(hit)ts.push(hit.t);}
  ts.sort((x,y)=>x-y);
  for(let i=1;i<ts.length;i++)if(ts[i]-ts[i-1]>EPS&&inside(lerp(a,b,(ts[i]+ts[i-1])/2),poly))return true;
  return false;
 });
}
function findRoute(roads,start,end,{obstacles=[],maxAccess=35}={}){
 if(start.id===end.id)return {status:'same-place'};
 const segments=[];
 for(const road of roads)for(let i=1;i<road.points.length;i++){
  const a=road.points[i-1],b=road.points[i];
  if(a.every(Number.isFinite)&&b.every(Number.isFinite)&&distance(a,b)>EPS)segments.push({a,b,width:road.width||3,cuts:[0,1]});
 }
 if(!segments.length)return {status:'no-roads'};
 for(const s of segments)for(const o of obstacles)for(let i=0;i<o.polygon.length;i++){
  const hit=intersection(s.a,s.b,o.polygon[i],o.polygon[(i+1)%o.polygon.length]);if(hit)s.cuts.push(hit.t);
 }
 const bridges=[];
 for(let i=0;i<segments.length;i++)for(let j=i+1;j<segments.length;j++){
  const s=segments[i],t=segments[j],hit=intersection(s.a,s.b,t.a,t.b);
  if(hit){s.cuts.push(hit.t);t.cuts.push(hit.u);}
  // Join hand drawn endpoint gaps only when the visible road widths overlap.
  for(const [one,two] of [[s,t],[t,s]])for(const p of [one.a,one.b]){
   const q=project(p,two.a,two.b),gap=distance(p,q.point),limit=Math.min(2.1,(one.width+two.width)/2);
   if(gap<=limit&&!blocked(p,q.point,obstacles)){two.cuts.push(q.t);bridges.push([p,q.point]);}
  }
 }
 const access=[];
 for(const place of [start,end]){
  const candidates=segments.map((s,index)=>{const q=project(place.point,s.a,s.b);return {...q,index,d:distance(place.point,q.point)};})
   .filter(q=>q.d<=maxAccess&&!obstacles.some(o=>inside(q.point,o.polygon))&&!blocked(place.point,q.point,obstacles,place.id))
   .sort((a,b)=>a.d-b.d);
  if(!candidates.length)return {status:'no-access'};
  // Access is explicit and obstacle checked; consider nearby alternatives when
  // the closest hand drawn road is a dead end. Never bridge distant networks.
  const nearby=candidates.slice(0,24);
  for(const q of nearby)segments[q.index].cuts.push(q.t);
  access.push(nearby);
 }
 const nodes=[],adj=[],lookup=new Map();
 function node(p){const key=p.map(v=>Math.round(v*10000)).join(',');if(!lookup.has(key)){lookup.set(key,nodes.length);nodes.push(p);adj.push([]);}return lookup.get(key);}
 function edge(a,b){if(blocked(a,b,obstacles))return;const x=node(a),y=node(b),d=distance(a,b);if(x!==y){adj[x].push([y,d]);adj[y].push([x,d]);}}
 for(const s of segments){const cuts=[...new Set(s.cuts)].sort((a,b)=>a-b);for(let i=1;i<cuts.length;i++)edge(lerp(s.a,s.b,cuts[i-1]),lerp(s.a,s.b,cuts[i]));}
 for(const [a,b] of bridges)edge(a,b);
 const source=nodes.length;nodes.push(start.point);adj.push([]);
 const sink=nodes.length;nodes.push(end.point);adj.push([]);
 for(let side=0;side<2;side++)for(const q of access[side]){
  const id=node(q.point),endpoint=side?sink:source;adj[endpoint].push([id,q.d]);adj[id].push([endpoint,q.d]);
 }
 const dist=nodes.map(()=>Infinity),prev=nodes.map(()=>-1),done=new Set();dist[source]=0;
 for(let count=0;count<nodes.length;count++){
  let u=-1;for(let i=0;i<nodes.length;i++)if(!done.has(i)&&(u<0||dist[i]<dist[u]))u=i;
  if(u<0||!Number.isFinite(dist[u]))break;if(u===sink)break;done.add(u);
  for(const [v,w] of adj[u])if(dist[u]+w<dist[v]){dist[v]=dist[u]+w;prev[v]=u;}
 }
 if(!Number.isFinite(dist[sink]))return {status:'disconnected'};
 const ids=[];for(let u=sink;u>=0;u=prev[u])ids.push(u);ids.reverse();
 const points=ids.map(i=>nodes[i]);
 return {status:'ok',points,roadPoints:points.slice(1,-1),access:[points.slice(0,2),points.slice(-2)],distance:dist[sink]};
}
const api={findRoute,blocked,project,inside};
if(typeof module!=='undefined')module.exports=api;else root.CampusRouting=api;
})(typeof window!=='undefined'?window:globalThis);
