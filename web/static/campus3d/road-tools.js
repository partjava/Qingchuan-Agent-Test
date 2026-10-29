(function(root){
 const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
 function project(p,a,b){const dx=b[0]-a[0],dz=b[1]-a[1],d=dx*dx+dz*dz,t=d?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dz)/d)):0;return [a[0]+t*dx,a[1]+t*dz];}
 function segments(roads){return roads.flatMap((r,id)=>r.points.slice(1).map((b,i)=>({a:r.points[i],b,id,width:r.width}))).filter(s=>distance(s.a,s.b)>.001);}
 function snapPoint(p,roads,tolerance=10){const segs=segments(roads);let best=null,min=tolerance;
  for(const s of segs)for(const q of [s.a,s.b]){const d=distance(p,q);if(d<=min){best=q;min=d;}}
  if(best)return {point:[...best],kind:'endpoint'};
  for(const s of segs){const q=project(p,s.a,s.b),d=distance(p,q);if(d<=min){best=q;min=d;}}
  return best?{point:best,kind:'segment'}:{point:[...p],kind:null};
 }
 function intersects(s,t){const ax=s.b[0]-s.a[0],ay=s.b[1]-s.a[1],bx=t.b[0]-t.a[0],by=t.b[1]-t.a[1],dx=t.a[0]-s.a[0],dy=t.a[1]-s.a[1],den=ax*by-ay*bx;if(Math.abs(den)<1e-8)return false;const u=(dx*by-dy*bx)/den,v=(dx*ay-dy*ax)/den;return u>=0&&u<=1&&v>=0&&v<=1;}
 function analyze(roads){const segs=segments(roads),parents=roads.map((_,i)=>i),active=new Set(segs.map(s=>s.id));const find=i=>parents[i]===i?i:(parents[i]=find(parents[i]));const join=(a,b)=>{parents[find(a)]=find(b);};
  for(let i=0;i<segs.length;i++)for(let j=i+1;j<segs.length;j++){const s=segs[i],t=segs[j];if(s.id===t.id)continue;const limit=Math.min(8.4,(s.width+t.width)*2);if(intersects(s,t)||Math.min(distance(s.a,project(s.a,t.a,t.b)),distance(s.b,project(s.b,t.a,t.b)),distance(t.a,project(t.a,s.a,s.b)),distance(t.b,project(t.b,s.a,s.b)))<=limit)join(s.id,t.id);}
  const components=new Map();for(const id of active){const key=find(id);if(!components.has(key))components.set(key,[]);components.get(key).push(id);}
  const sorted=[...components.values()].sort((a,b)=>b.length-a.length),isolated=sorted.slice(1).flat(),deadEnds=[],gaps=[];
  for(const id of active){const r=roads[id];if(distance(r.points[0],r.points[r.points.length-1])<.01)continue;
   for(const p of [r.points[0],r.points[r.points.length-1]]){let nearest=null,min=Infinity,connected=false;
    for(const s of segs){if(s.id===id)continue;const q=project(p,s.a,s.b),d=distance(p,q);if(d<=Math.min(8.4,(r.width+s.width)*2))connected=true;if(d<min){min=d;nearest=q;}}
    if(!connected){deadEnds.push([...p]);if(nearest&&min<=24)gaps.push({from:[...p],to:nearest});}
   }
  }
  return {components:sorted.length,isolated,deadEnds,gaps};
 }
 const api={snapPoint,analyze};if(typeof module!=='undefined')module.exports=api;else root.CampusRoadTools=api;
})(typeof window!=='undefined'?window:globalThis);
