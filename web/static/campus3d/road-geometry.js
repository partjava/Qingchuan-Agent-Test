/* Shared road surfaces: world units, immutable source coordinates. */
(function(root){
 function rectangle(a,b,width){const dx=b[0]-a[0],dz=b[1]-a[1],length=Math.hypot(dx,dz),nx=-dz/length*width/2,nz=dx/length*width/2;return [[a[0]+nx,a[1]+nz],[b[0]+nx,b[1]+nz],[b[0]-nx,b[1]-nz],[a[0]-nx,a[1]-nz]];}
 function circle(p,r){return Array.from({length:24},(_,i)=>[p[0]+Math.cos(i*Math.PI/12)*r,p[1]+Math.sin(i*Math.PI/12)*r]);}
 function distance(p,s){const t=Math.max(0,Math.min(1,((p[0]-s.a[0])*s.dx+(p[1]-s.a[1])*s.dz)/(s.length*s.length)));return Math.hypot(p[0]-s.a[0]-t*s.dx,p[1]-s.a[1]-t*s.dz);}
 function plan(roads){
  const result={curbs:[],asphalt:[],paving:[],markings:[]},segments=[];
  for(const road of roads){if(!Number.isFinite(road.width)||road.width<=0||!Array.isArray(road.points))continue;
   const pts=road.points.map(p=>[p[0]/4,p[1]/4]);
   for(let i=1;i<pts.length;i++){const a=pts[i-1],b=pts[i],dx=b[0]-a[0],dz=b[1]-a[1],length=Math.hypot(dx,dz);if(!Number.isFinite(length)||length<.1)continue;
    segments.push({a,b,dx,dz,length,width:road.width});
    const paved=road.width<=3.2,surface=paved?result.paving:result.asphalt,curbWidth=road.width+(paved?.6:1.2);
    result.curbs.push(rectangle(a,b,curbWidth),circle(a,curbWidth/2),circle(b,curbWidth/2));
    surface.push(rectangle(a,b,road.width),circle(a,road.width/2),circle(b,road.width/2));
   }
  }
  for(const s of segments){if(s.width<4.5)continue;
   // Short dashes stop near ends and wherever another road meets this road.
   for(let start=2;start<s.length-2;start+=3){const end=Math.min(start+1.5,s.length-2);if(end-start<.4)continue;
    const samples=[start,(start+end)/2,end].map(t=>[s.a[0]+s.dx*t/s.length,s.a[1]+s.dz*t/s.length]);
    const blocked=segments.some(other=>other!==s&&Math.abs(s.dx*other.dz-s.dz*other.dx)/(s.length*other.length)>.08&&samples.some(p=>distance(p,other)<other.width/2+.8));
    if(!blocked)result.markings.push(rectangle(samples[0],samples[2],.22));
   }
  }
  return result;
 }
 function build(THREE,roads,{y=.12,preview=false}={}){
  const group=new THREE.Group(),layers=plan(roads);
  const styles=[['curbs','#d5cfc2',0],['asphalt','#383d42',.04],['paving','#eae5dc',.05],['markings',preview?'#ffd15c':'#eae6dc',.065]];
  for(const [key,color,offset] of styles){const positions=[];
   for(const poly of layers[key]){const shape=new THREE.Shape(poly.map(p=>new THREE.Vector2(p[0],-p[1]))),geo=new THREE.ShapeGeometry(shape),triangles=geo.index?geo.toNonIndexed():geo,attr=triangles.attributes.position;
    for(let i=0;i<attr.count;i++)positions.push(attr.getX(i),y+offset,-attr.getY(i));
    if(triangles!==geo)triangles.dispose();geo.dispose();
   }
   if(!positions.length)continue;
   const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geo.computeVertexNormals();
   const material=preview?new THREE.MeshBasicMaterial({color}):new THREE.MeshStandardMaterial({color,roughness:.92});
   const mesh=new THREE.Mesh(geo,material);mesh.receiveShadow=true;mesh.userData.roadLayer=key;group.add(mesh);
  }
  return group;
 }
 const api={plan,build};if(typeof module!=='undefined')module.exports=api;else root.CampusRoadGeometry=api;
})(typeof window!=='undefined'?window:globalThis);
