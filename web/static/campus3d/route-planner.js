(function(root){'use strict';
root.createRoutePlanner=function({scene,groups,places,getRoads,getObstacles,fitRoute}){
 const hud=document.getElementById('route-hud'),start=document.getElementById('route-start'),end=document.getElementById('route-end'),status=document.getElementById('route-status');
 const overlay=new THREE.Group();overlay.name='campus-route';scene.add(overlay);
 let active=false,result=null;
 function dispose(){
  while(overlay.children.length){const child=overlay.children[0];overlay.remove(child);child.geometry?.dispose();child.material?.dispose();}
 }
 const sorted=[...places].sort((a,b)=>a.name.localeCompare(b.name,'zh-CN'));
 for(const select of [start,end])for(const p of sorted){const option=document.createElement('option');option.value=p.id;option.textContent=p.name;select.appendChild(option);}
 start.value=places.find(p=>p.id==='teach_1')?.id||places[0]?.id||'';
 end.value=places.find(p=>p.id==='library')?.id||places[1]?.id||'';
 function endpoint(id,roads,obstacles){
  const b=places.find(p=>p.id===id);if(!b)return null;
  let point=[b.x,b.z];
  if(b.kind==='lake'){
   const bank=obstacles.find(o=>o.id===id)?.polygon||[];let best=null;
   for(const p of bank)for(const r of roads)for(let i=1;i<r.points.length;i++){
    const q=CampusRouting.project(p,r.points[i-1],r.points[i]).point,d=Math.hypot(p[0]-q[0],p[1]-q[1]);
    if(obstacles.some(o=>CampusRouting.inside(q,o.polygon))||CampusRouting.blocked(p,q,obstacles))continue;
    if(!best||d<best.d)best={p,q,d};
   }
   if(best){const d=Math.max(.001,best.d);point=[best.p[0]+(best.q[0]-best.p[0])*.6/d,best.p[1]+(best.q[1]-best.p[1])*.6/d];}
   return {id:id+'-bank',point};
  }
  return {id,point};
 }
 function strip(a,b,width,color){
  const dx=b[0]-a[0],dz=b[1]-a[1],length=Math.hypot(dx,dz);if(length<.001)return;
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(width,length),new THREE.MeshBasicMaterial({color,side:THREE.DoubleSide,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2}));
  mesh.rotation.x=-Math.PI/2;mesh.rotation.z=Math.atan2(dx,dz);mesh.position.set((a[0]+b[0])/2,.8,(a[1]+b[1])/2);overlay.add(mesh);
 }
 function draw(points,dashed=false){
  for(let i=1;i<points.length;i++){
   const a=points[i-1],b=points[i],length=Math.hypot(b[0]-a[0],b[1]-a[1]);
   if(dashed){for(let offset=0;offset<length;offset+=3){const from=offset/length,to=Math.min(length,offset+1.6)/length;strip([a[0]+(b[0]-a[0])*from,a[1]+(b[1]-a[1])*from],[a[0]+(b[0]-a[0])*to,a[1]+(b[1]-a[1])*to],1.2,'#ff4d4f');}}
   else {strip(a,b,3.2,'#ffffff');strip(a,b,2.0,'#e52b38');}
  }
 }
 function marker(point,color){const mesh=new THREE.Mesh(new THREE.SphereGeometry(1.8,16,12),new THREE.MeshBasicMaterial({color}));mesh.position.set(point[0],2.2,point[1]);overlay.add(mesh);}
 function plan(fit=true){
  dispose();
  const roads=getRoads(),obstacles=getObstacles(),a=endpoint(start.value,roads,obstacles),b=endpoint(end.value,roads,obstacles);
  if(!a||!b){status.textContent='请选择有效的起点和终点。';return;}
  if(start.value===end.value)result={status:'same-place'};
  else result=CampusRouting.findRoute(roads,a,b,{obstacles});
  active=result.status==='ok';
  if(!active){
   const messages={'same-place':'起点与终点相同，请选择两个不同地点。','no-roads':'当前没有道路，请先绘制或恢复路网。','no-access':'地点附近没有可用道路连接，请补充道路后重试。','disconnected':'起终点的道路尚未连通，请在画路中补齐连接。'};
   status.textContent=messages[result.status]||'暂时无法规划路线。';return;
  }
  draw(result.roadPoints);for(const access of result.access)draw(access,true);
  const roadPoints=result.roadPoints;
  if(roadPoints.length){marker(roadPoints[0],'#10b981');marker(roadPoints[roadPoints.length-1],'#e52b38');}
  const aName=places.find(p=>p.id===start.value).name,bName=places.find(p=>p.id===end.value).name;
  status.textContent=aName+' → '+bName+' · 路线已显示';
  if(fit)fitRoute(result.points);
 }
 function close(){hud.hidden=true;document.getElementById('route').classList.remove('active');}
 function clear(){dispose();active=false;result=null;status.textContent='选择起点和终点，沿校园道路规划路线。';}
 
 function planRoute(fromId,toId,fit=true){
  if(fromId)start.value=fromId;
  if(toId)end.value=toId;
  open();
  plan(fit);
 }
 function open(){

  if(root.BuildingEditor?.isEditing())root.BuildingEditor.toggleEditor();
  if(root.RoadEditor?.isEditing())root.RoadEditor.toggleEditor();
  root.CampusScene?.stopMotion();root.CampusScene?.closeMore();
  document.getElementById('card').hidden=true;
  hud.hidden=false;document.getElementById('route').classList.add('active');
 }
 document.getElementById('route').onclick=()=>hud.hidden?open():close();
 document.getElementById('route-close').onclick=close;
 document.getElementById('route-plan').onclick=()=>plan();
 document.getElementById('route-clear').onclick=clear;
 document.getElementById('route-swap').onclick=()=>{const old=start.value;start.value=end.value;end.value=old;if(active)plan();};
 start.onchange=end.onchange=clear;
 return {open,close,clear,planRoute,suspend(){close();dispose();},refresh(){if(active)plan(false);},getResult:()=>result};
};
})(typeof window!=='undefined'?window:globalThis);
