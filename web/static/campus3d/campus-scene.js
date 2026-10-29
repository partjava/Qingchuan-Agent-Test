/* Local, approximate exterior reconstruction; no geographic or indoor navigation claims. */

(function(){'use strict';

const error=document.getElementById('error');

window.addEventListener('error',e=>{error.style.display='block';error.textContent='三维场景加载失败：'+e.message+'。请返回航拍导览。';});

const scene=new THREE.Scene();scene.background=new THREE.Color('#e7efec');scene.fog=new THREE.Fog('#e7efec',1500,2800);

let renderer;

try{renderer=SceneUtils.createRenderer(THREE,innerWidth,innerHeight,window.devicePixelRatio);}

catch(e){error.style.display='block';error.textContent='此设备暂时无法创建三维渲染环境，请返回航拍导览。';console.error('Campus WebGL initialization failed',e);return;}

document.body.prepend(renderer.domElement);

const camera=new THREE.PerspectiveCamera(42,innerWidth/innerHeight,1,1800);scene.add(new THREE.HemisphereLight(0xffffff,0x73816d,1.5));

const sun=new THREE.DirectionalLight(0xfff4dc,2.0);sun.position.set(-200,450,180);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);Object.assign(sun.shadow.camera,{left:-360,right:360,top:400,bottom:-400,far:1000});sun.shadow.bias=-.001;scene.add(sun);

const materials=new Map();function mat(color){if(!materials.has(color))materials.set(color,new THREE.MeshStandardMaterial({color,roughness:.86}));return materials.get(color).clone();}

function box(w,h,d,x,y,z,color,parent=scene){if(color==='#789a9c'){if(!parent.userData.windows)parent.userData.windows=[];parent.userData.windows.push([w,h,d,x,y+h/2,z]);return;}const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat(color));m.position.set(x,y+h/2,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;}

function flat(points,y,color,parent=scene){const s=new THREE.Shape();points.forEach((p,i)=>i?s.lineTo(p[0],-p[1]):s.moveTo(p[0],-p[1]));s.closePath();const m=new THREE.Mesh(new THREE.ShapeGeometry(s),mat(color));m.rotation.x=-Math.PI/2;m.position.y=y;m.receiveShadow=true;parent.add(m);return m;}

buildCampusGround({scene,flat,box,mat});

const groups=new Map(),pickables=[],labels=[];

const allPlaces=[...CampusData.buildings,...(CampusData.regions||[])],regionGroups=window.SpecialTrace?SpecialTrace.render(CampusData,{scene,flat,mat}):[];

for(const record of regionGroups){

 pickables.push(record.surface);

 labels.push({b:record.b,s:label(record.b.name,record.b.x,3,record.b.z,record.b)});

 groups.set(record.b.id,record.group);

}

if(window.stadiumGroup){

 const stadiumB={id:'stadium',name:'田径场 / 足球场',category:'文体',region:true,x:638/4,z:266/4};

 allPlaces.push(stadiumB);

 if(window.stadiumSurface)pickables.push(window.stadiumSurface);

 groups.set('stadium', window.stadiumGroup);

 labels.push({b:stadiumB, s:label(stadiumB.name,stadiumB.x,4,stadiumB.z,stadiumB)});

}

function label(text,x,y,z,place){

 const el=document.createElement('div');

 el.className='map-label';

 el.textContent=text;

 if(place)el.onclick=e=>{

  e.stopPropagation();

  if(window.BuildingEditor&&window.BuildingEditor.isEditing&&window.BuildingEditor.isEditing()){

   window.BuildingEditor.selectBuilding(place.id);

   return;

  }

  select(place);

 };

 document.getElementById('labels').append(el);

 return {el,position:new THREE.Vector3(x,y,z),visible:true};

}

function pitchedRoof(w,d,rise,x,y,z,g,id){const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(SceneUtils.roofVertices(w,d,rise),3));geo.setIndex([0,2,1,3,4,5,0,3,5,0,5,2,2,5,4,2,4,1,0,1,4,0,4,3]);geo.computeVertexNormals();const m=new THREE.Mesh(geo,mat('#616c73'));m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;m.userData.id=id;g.add(m);pickables.push(m);}

for(const b of CampusData.buildings){

 const g=new THREE.Group();g.position.set(b.x,0,b.z);scene.add(g);

 buildPhotoModel(b,g,{mat,box,pickables});

 const s=label(b.name,b.x,b.floors*3.2+10,b.z,b);labels.push({b,s});groups.set(b.id,g);

}

let theta=Math.PI/2,phi=.85,radius=560,target=new THREE.Vector3(165,0,155),selected=null,filter='全部',paused=false;

let contextLost=false;

const contextLostMessage='三维渲染正在恢复，请稍候…';

renderer.domElement.addEventListener('webglcontextlost',e=>{

 e.preventDefault();contextLost=true;

 error.style.display='block';error.textContent=contextLostMessage;

});

renderer.domElement.addEventListener('webglcontextrestored',()=>{

 contextLost=false;

 if(error.textContent===contextLostMessage){error.style.display='none';error.textContent='';}

});

let isCruising=false,cruiseTime=0;

let flyAnimation=null;



function updateCamera(){

 camera.position.set(target.x+radius*Math.sin(phi)*Math.sin(theta),target.y+radius*Math.cos(phi),target.z+radius*Math.sin(phi)*Math.cos(theta));

 camera.up.set(-Math.cos(phi)*Math.sin(theta),Math.sin(phi),-Math.cos(phi)*Math.cos(theta));

 camera.lookAt(target);

 camera.updateMatrixWorld(true);

 updateTopButton();

}

function updateTopButton(){

 const btn=document.getElementById('top');

 btn.classList.toggle('active',phi<.1);

 btn.setAttribute('aria-pressed',String(phi<.1));

}



function syncCamera(){

 const offset=camera.position.clone().sub(target);

 radius=Math.max(1,offset.length());

 phi=Math.acos(THREE.MathUtils.clamp(offset.y/radius,-1,1));

 theta=Math.atan2(offset.x,offset.z);

 updateTopButton();

}

function stopMotion(){

 stopCruise();

 if(flyAnimation){syncCamera();flyAnimation=null;}

}



let highlightRing = null;

function updateHighlightRing(b) {

 if (!highlightRing) {

  highlightRing = new THREE.Group();

  const ringGeo = new THREE.RingGeometry(18, 23, 48);

  ringGeo.rotateX(-Math.PI / 2);

  const ringMat = new THREE.MeshBasicMaterial({ color: 0xffcc00, side: THREE.DoubleSide, transparent: true, opacity: 0.9 });

  highlightRing.add(new THREE.Mesh(ringGeo, ringMat));



  const lineGeo = new THREE.BufferGeometry();

  const pts = [];

  for (let i = 0; i <= 64; i++) {

   const a = (i / 64) * Math.PI * 2;

   pts.push(new THREE.Vector3(Math.cos(a) * 24, 0.4, Math.sin(a) * 24));

  }

  lineGeo.setFromPoints(pts);

  const lineMat = new THREE.LineBasicMaterial({ color: 0xffe600, linewidth: 3 });

  highlightRing.add(new THREE.Line(lineGeo, lineMat));

  scene.add(highlightRing);

 }

 if (b) {

  const r = Math.max(24, (b.w || 28) * 0.85, (b.d || 28) * 0.85);

  const s = r / 20;

  highlightRing.scale.set(s, 1, s);

  highlightRing.position.set(b.x, 0.6, b.z);

  highlightRing.visible = true;

 } else {

  highlightRing.visible = false;

 }

}



function reset(){

 stopCruise();

 flyAnimation=null;

 selected=null;

 updateHighlightRing(null);

 const card=document.getElementById('card');

 card.hidden=true;

 card.classList.remove('selected');

 document.getElementById('title').textContent='晴川 3D 校园';

 document.getElementById('info').textContent='独立建筑模型 · 真实航拍底图 · 情缘湖与运动场';

 document.getElementById('badge').style.display='none';

 document.getElementById('thumb').style.display='none';

 document.getElementById('desc').style.display='none';

 document.getElementById('floors').style.display='none';

 document.getElementById('actions').style.display='none';

 const a=document.getElementById('photo');a.hidden=true;

 for(const g of groups.values())g.traverse(m=>{if(m.isMesh)m.material.emissive.set('#000000');});

 for(const r of regionGroups)r.surface.material.emissive.set('#000000');

 theta=Math.PI/2;phi=.7;radius=Math.max(500,205/Math.tan(42*Math.PI/360)/(innerWidth/innerHeight));

 target.set(165,0,157);

 updateCamera();

}

reset();



function select(b){

 stopCruise();

 flyAnimation=null;

 document.getElementById('card').hidden=false;

 document.getElementById('card').classList.add('selected');

 selected=b.id;

 updateHighlightRing(b);

 for(const [id,g] of groups)g.traverse(m=>{if(m.isMesh)m.material.emissive.set(id===b.id?'#665500':'#000000');});

 for(const r of regionGroups)r.surface.material.emissive.set(r.b.id===b.id?'#665500':'#000000');

 target.set(b.x,0,b.z);

 radius=Math.min(radius,b.region?190:230);

 phi=.85;

 updateCamera();



 const lm=(window.CampusLandmarks&&window.CampusLandmarks[b.id])||null;

 const titleEl=document.getElementById('title');

 const badgeEl=document.getElementById('badge');

 const infoEl=document.getElementById('info');

 const descEl=document.getElementById('desc');

 const floorsEl=document.getElementById('floors');

 const thumbEl=document.getElementById('thumb');

 const actionsEl=document.getElementById('actions');

 const photoA=document.getElementById('photo');



 titleEl.textContent=lm?lm.fullName:b.name;

 if(lm&&lm.category){badgeEl.textContent=lm.category;badgeEl.style.display='inline-block';}

 else if(b.category){badgeEl.textContent=b.category+'区';badgeEl.style.display='inline-block';}

 else badgeEl.style.display='none';



 infoEl.textContent=lm?(lm.totalFloors+' · '+(lm.tag||'')): (b.info||('共'+b.floors+'层 · '+b.category+'区'));



 if(lm&&lm.desc){descEl.textContent=lm.desc;descEl.style.display='block';}

 else descEl.style.display='none';



 if(lm&&lm.floorsGuide){floorsEl.textContent=lm.floorsGuide;floorsEl.style.display='block';}

 else floorsEl.style.display='none';



 const photoPath=lm?lm.photo:('photos/'+b.id+'.jpg');

 thumbEl.src=photoPath;

 thumbEl.style.display='block';

 thumbEl.onerror=function(){this.style.display='none';};



 actionsEl.style.display='flex';

 if(b.region){photoA.hidden=true;}

 else{

  photoA.hidden=false;

  photoA.href='campus://detail/'+encodeURIComponent(b.id);

 }

}



// Fly to current selected building

document.getElementById('fly').onclick=function(){

 const b=allPlaces.find(p=>p.id===selected);

 if(!b)return;

 stopCruise();

 const startPos=camera.position.clone();

 const endPos=new THREE.Vector3(b.x,18,b.z+42);

 const startLook=target.clone();

 const endLook=new THREE.Vector3(b.x,b.floors?b.floors*1.6:5,b.z);

 const startTime=performance.now(),duration=1500;

 flyAnimation={

  update:(now)=>{

   const t=Math.min(1,(now-startTime)/duration);

   const ease=t<.5?2*t*t:-1+(4-2*t)*t;

   camera.position.lerpVectors(startPos,endPos,ease);

   target.lerpVectors(startLook,endLook,ease);

   camera.lookAt(target);

   if(t>=1){syncCamera();flyAnimation=null;}

  }

 };

};





const askAiBtn = document.getElementById('ask-ai');

if (askAiBtn) {

 askAiBtn.onclick = function() {

  const b = allPlaces.find(p => p.id === selected);

  if (!b) return;

  const lm = (window.CampusLandmarks && window.CampusLandmarks[b.id]) || null;

  const bName = lm ? lm.fullName : b.name;

  if (window.parent) {

   window.parent.postMessage({ type: 'ask_building', name: bName, id: b.id }, '*');

  }

 };

}



document.getElementById('close').onclick=()=>{

 document.getElementById('card').hidden=true;

 document.getElementById('card').classList.remove('selected');

 selected=null;

 updateHighlightRing(null);

 for(const g of groups.values())g.traverse(m=>{if(m.isMesh&&m.material.emissive)m.material.emissive.set('#000000');});

};



const raycaster=new THREE.Raycaster();

function pick(x,y){

 raycaster.setFromCamera(new THREE.Vector2(x/innerWidth*2-1,1-y/innerHeight*2),camera);

 const hit=raycaster.intersectObjects(pickables).find(h=>h.object.parent.visible);

 if(hit){

  const b=allPlaces.find(b=>b.id===hit.object.userData.id);

  if(b){

   if(window.BuildingEditor&&window.BuildingEditor.isEditing&&window.BuildingEditor.isEditing()){

    window.BuildingEditor.selectBuilding(b.id);

    return;

   }

   select(b);

  }

 }

}



for(const name of ['全部','教学','住宿','生活','文体']){

 const btn=document.createElement('button');

 btn.textContent=name;

 btn.className=name==='全部'?'active':'';

 btn.onclick=()=>{

  filter=name;

  for(const [id,g]of groups)g.visible=name==='全部'||allPlaces.find(b=>b.id===id)?.category===name;

  for(const r of regionGroups)r.group.visible=name==='全部'||r.b.category===name;

  for(const {b,s}of labels)s.visible=name==='全部'||b.category===name;

  document.querySelectorAll('#filters button:not(#label-toggle)').forEach(el=>el.classList.toggle('active',el===btn));

 };

 document.getElementById('filters').append(btn);

}

const labelToggle=document.getElementById('label-toggle');

document.getElementById('filters').append(labelToggle);

labelToggle.onclick=()=>{

 const labels=document.getElementById('labels');

 labels.hidden=!labels.hidden;

 labelToggle.textContent=labels.hidden?'显示名称':'隐藏名称';

 labelToggle.classList.toggle('active',labels.hidden);

 labelToggle.setAttribute('aria-pressed',String(labels.hidden));

 labelToggle.setAttribute('aria-label',labels.hidden?'显示地图地点名称':'隐藏地图地点名称');

};



function search(){

 const raw=document.getElementById('search').value.trim();

 const q=raw.replace('教1','教学楼1').replace('教2','教学楼2').replace('教3','教学楼3').replace('教4','教学楼4').replace(/^宿舍(\d+)$/,'$1号宿舍');

 const b=allPlaces.find(b=>q&&(b.name.includes(q)||b.id===q||(b.name&&q.includes(b.name))||(b.id==='south_gate'&&['大门','南门','校门','南大门','正门'].some(k=>raw.includes(k)))));

 if(b){

  document.querySelector('#filters button').click();

  select(b);

 }else document.getElementById('info').textContent='未找到地点，请输入建筑或区域名称。';

}

document.getElementById('find').onclick=search;

document.getElementById('search').onkeydown=e=>{if(e.key==='Enter')search();};



document.getElementById('plus').onclick=()=>{stopMotion();radius=Math.max(12,radius*.8);updateCamera();};

document.getElementById('minus').onclick=()=>{stopMotion();radius=Math.min(1100,radius*1.25);updateCamera();};

document.getElementById('reset').onclick=reset;

document.getElementById('top').onclick=()=>{stopMotion();phi=phi<.1?.85:.025;theta=Math.PI/2;updateCamera();};



// Cruise mode implementation

const cruiseBtn=document.getElementById('cruise');

const cruiseWaypoints=[

 new THREE.Vector3(305,14,124), // East Main Gate entrance

 new THREE.Vector3(260,20,130), // Campus entrance boulevard

 new THREE.Vector3(180,18,180), // Lake south bank

 new THREE.Vector3(135,22,145), // Library curved terrace

 new THREE.Vector3(160,26,95),  // Athletic Stadium & Gym

 new THREE.Vector3(240,28,160), // Teaching buildings 1-4

 new THREE.Vector3(215,45,285)  // High overview climb

];

const cruiseLooks=[

 new THREE.Vector3(275,6,124),

 new THREE.Vector3(210,8,150),

 new THREE.Vector3(140,6,150),

 new THREE.Vector3(124,10,152),

 new THREE.Vector3(160,6,66),

 new THREE.Vector3(265,12,210),

 new THREE.Vector3(165,0,155)

];

const posCurve=new THREE.CatmullRomCurve3(cruiseWaypoints,true,'centripetal');

const lookCurve=new THREE.CatmullRomCurve3(cruiseLooks,true,'centripetal');



function startCruise(){

 isCruising=true;

 cruiseTime=0;

 flyAnimation=null;

 cruiseBtn.classList.add('active');

 cruiseBtn.textContent='漫游中';

 document.getElementById('info').textContent='正在沿晴川中轴线与核心景观自动巡航漫游... 点击任意处退出';

}

function stopCruise(){

 if(!isCruising)return;

 isCruising=false;

 syncCamera();

 cruiseBtn.classList.remove('active');

 cruiseBtn.textContent='巡航';

}

cruiseBtn.onclick=function(){

 if(isCruising)stopCruise();else startCruise();

};



const modeBtn=document.getElementById('mode');

function toggleGroundMode(){

 const mode=window.getGroundMode?window.getGroundMode():'schematic';

 if(window.setGroundMode)window.setGroundMode(mode==='schematic'?'aerial':'schematic');

}

if(modeBtn){

 modeBtn.textContent='沙盘';

 modeBtn.addEventListener('click',toggleGroundMode);

 modeBtn.addEventListener('touchend',e=>{e.preventDefault();toggleGroundMode();});

}



const pointers=new Map();let down=null,moved=false,pinch=0,gestureMode='pan';

const gestureBtn=document.getElementById('gesture');

gestureBtn.onclick=()=>{

 gestureMode=gestureMode==='pan'?'rotate':'pan';

 gestureBtn.textContent=gestureMode==='pan'?'平移':'旋转';

 gestureBtn.classList.toggle('active',gestureMode==='rotate');

 gestureBtn.setAttribute('aria-pressed',String(gestureMode==='rotate'));

};

function panMap(dx,dy){

 const scale=2*radius*Math.tan(camera.fov*Math.PI/360)/innerHeight;

 target.x-=scale*(dx*Math.cos(theta)+dy*Math.sin(theta)/Math.max(.2,Math.cos(phi)));

 target.z+=scale*(dx*Math.sin(theta)-dy*Math.cos(theta)/Math.max(.2,Math.cos(phi)));

 target.x=THREE.MathUtils.clamp(target.x,-50,380);

 target.z=THREE.MathUtils.clamp(target.z,-50,390);

}

const canvas=renderer.domElement;

function closeMore(){

 const panel=document.getElementById('more-tools');if(panel)panel.hidden=true;

 const btn=document.getElementById('more');if(btn){btn.setAttribute('aria-expanded','false');btn.classList.remove('active');}

}

const moreBtn=document.getElementById('more');

if(moreBtn){

 moreBtn.onclick=()=>{

  const panel=document.getElementById('more-tools');if(!panel)return;

  panel.hidden=!panel.hidden;

  moreBtn.setAttribute('aria-expanded',String(!panel.hidden));

  moreBtn.classList.toggle('active',!panel.hidden);

 };

}



const toolsEl=document.getElementById('tools-scroll')||document.getElementById('tools')||document.querySelector('.tools');

const toolsDock=document.getElementById('tools')||document.querySelector('.tools');

if(toolsDock){

 toolsDock.addEventListener('pointerdown',e=>e.stopPropagation());

 toolsDock.addEventListener('touchstart',e=>e.stopPropagation(),{passive:true});

}

if(toolsEl){

 const STORAGE_KEY='campus3d_tools_scroll';

 let scrollTimer=null;

 function saveToolsScroll(){

  try{if(typeof localStorage!=='undefined')localStorage.setItem(STORAGE_KEY,String(toolsEl.scrollTop));}catch(_){}

 }

 toolsEl.addEventListener('scroll',()=>{

  if(typeof setTimeout!=='undefined'){

   clearTimeout(scrollTimer);

   scrollTimer=setTimeout(saveToolsScroll,50);

  }else{saveToolsScroll();}

 },{passive:true});

 toolsEl.addEventListener('click',saveToolsScroll);

 function restoreToolsScroll(){

  try{

   if(typeof localStorage!=='undefined'){

    const saved=localStorage.getItem(STORAGE_KEY);

    if(saved!==null){

     const top=parseFloat(saved);

     if(Number.isFinite(top)&&top>=0)toolsEl.scrollTop=top;

    }

   }

  }catch(_){}

 }

 window.restoreToolsScroll=restoreToolsScroll;

 restoreToolsScroll();

 if(typeof setTimeout!=='undefined'){

  setTimeout(restoreToolsScroll,50);

  setTimeout(restoreToolsScroll,250);

 }

 toolsEl.addEventListener('pointerdown',e=>e.stopPropagation());

 toolsEl.addEventListener('touchstart',e=>e.stopPropagation(),{passive:true});

 toolsEl.addEventListener('touchmove',e=>e.stopPropagation(),{passive:true});

 toolsEl.addEventListener('wheel',e=>e.stopPropagation(),{passive:true});

}

const groundPlane=new THREE.Plane(new THREE.Vector3(0,1,0),0);

function groundPoint(x,y){

 camera.updateMatrixWorld(true);

 raycaster.setFromCamera(new THREE.Vector2(x/innerWidth*2-1,1-y/innerHeight*2),camera);

 return raycaster.ray.intersectPlane(groundPlane,new THREE.Vector3());

}

canvas.onpointerdown=e=>{

 closeMore();

 stopMotion();

 canvas.setPointerCapture(e.pointerId);

 pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});

 if(pointers.size===1){down={x:e.clientX,y:e.clientY};moved=false;}

 else{moved=true;const [a,b]=[...pointers.values()];pinch=Math.hypot(a.x-b.x,a.y-b.y);}

};

canvas.onpointermove=e=>{

 const old=pointers.get(e.pointerId);

 if(!old)return;

 const dx=e.clientX-old.x,dy=e.clientY-old.y;

 const previousPair=[...pointers.values()].slice(0,2);

 pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});

 if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)>7)moved=true;

 if(pointers.size===1){

  if(window.RoadEditor&&window.RoadEditor.isEditing&&window.RoadEditor.isEditing()){

   if(window.RoadEditor.getMode&&window.RoadEditor.getMode()==='pan'||window.RoadEditor.isGesturePaused?.()){

    panMap(dx,dy);

    updateCamera();

   }

   return;

  }

  if(gestureMode==='pan'||window.BuildingEditor?.isEditing())panMap(dx,dy);

  else{

   theta-=dx*.007;

   if(phi>=.1)phi=THREE.MathUtils.clamp(phi+dy*.005,.1,Math.PI-.025);

  }

 }else{

  const [a,b]=[...pointers.values()],dist=Math.hypot(a.x-b.x,a.y-b.y);

  const oldMid={x:(previousPair[0].x+previousPair[1].x)/2,y:(previousPair[0].y+previousPair[1].y)/2};

  const mid={x:(a.x+b.x)/2,y:(a.y+b.y)/2};

  const anchor=groundPoint(oldMid.x,oldMid.y);

  if(pinch)radius=THREE.MathUtils.clamp(radius*pinch/Math.max(dist,1),12,1100);

  pinch=dist;

  updateCamera();

  const after=groundPoint(mid.x,mid.y);

  if(anchor&&after){target.x+=anchor.x-after.x;target.z+=anchor.z-after.z;}

  else panMap(dx/2,dy/2);

 }

 updateCamera();

};

function release(e){

 if(!window.RoadEditor?.isEditing()&&!moved&&pointers.size===1&&down&&e.type!=='pointercancel')pick(e.clientX,e.clientY);

 pointers.delete(e.pointerId);pinch=0;

 if(pointers.size===1){down={...[...pointers.values()][0]};moved=true;}

 else if(!pointers.size){down=null;}

}

canvas.onpointerup=release;

canvas.onpointercancel=release;

canvas.onwheel=e=>{

 stopMotion();

 e.preventDefault();

 radius=THREE.MathUtils.clamp(radius*Math.exp(e.deltaY*.001),12,1100);

 updateCamera();

};

window.addEventListener('load',()=>requestAnimationFrame(reset));

window.onresize=()=>{

 camera.aspect=innerWidth/innerHeight;

 camera.updateProjectionMatrix();

 renderer.setSize(innerWidth,innerHeight);

};

document.addEventListener('visibilitychange',()=>paused=document.hidden);

window.resetCameraTop=function(){

 stopMotion();

 selected=null;

 updateHighlightRing(null);

 target.set(165,0,157.5);

 phi=0.025;

 theta=Math.PI/2;

 radius=480;

 updateCamera();

};

if(window.RoadEditor&&typeof window.RoadEditor.init==='function'){

 window.RoadEditor.init({scene,camera,renderer});

}

if(window.BuildingEditor&&typeof window.BuildingEditor.init==='function'){

 window.BuildingEditor.init({scene,camera,renderer,groups,labels,CampusData,select,allPlaces});

}

const ID_FALLBACKS = {

  'admin': 'admin_1',

  'admin_center': 'admin_1',

  'canteen': 'canteen_main',

  'gate': 'south_gate',

  'main_gate': 'south_gate',

  'dorm': 'dorm_1',

  'dorm_cluster': 'dorm_1'

};



window.select = function(bOrId) {

 if (typeof bOrId === 'string') {

  const targetId = ID_FALLBACKS[bOrId] || bOrId;

  const b = allPlaces.find(p => p.id === targetId);

  if (b) select(b);

 } else if (bOrId) {

  select(bOrId);

 }

};



window.CampusScene={

 stopMotion,

 closeMore,

 select:id=>{

  const targetId = ID_FALLBACKS[id] || id;

  const b=allPlaces.find(b=>b.id===targetId);

  if(b)select(b);

 },

 pause:v=>paused=v,

 buildings:CampusData.buildings,

 regions:CampusData.regions||[]

};

if(window.createRoutePlanner)window.RoutePlanner=createRoutePlanner({scene,groups,places:allPlaces,

 getRoads:()=>CampusLayout.roads.map(r=>({...r,points:r.points.map(CampusLayout.world)})),

 getObstacles:()=>{

  scene.updateMatrixWorld(true);

  const polygons=[];

  for(const b of CampusData.buildings){

   const g=groups.get(b.id),m=CampusFootprints[b.id];if(!g||!m)continue;

   for(const outline of [m.outer,...(m.links||[]).map(l=>l.outline)])polygons.push({id:b.id,polygon:outline.map(p=>{const q=g.localToWorld(new THREE.Vector3(p[0],0,p[1]));return [q.x,q.z];})});

  }

  for(const r of CampusData.regions||[])if(r.kind==='lake'){

   const g=groups.get(r.id);polygons.push({id:r.id,polygon:r.outline.map(p=>{const q=g.localToWorld(new THREE.Vector3(p[0],0,p[1]));return [q.x,q.z];})});

  }

  return polygons;

 },

 fitRoute:points=>{

  stopMotion();document.getElementById('card').hidden=true;

  const xs=points.map(p=>p[0]),zs=points.map(p=>p[1]);

  const minX=Math.min(...xs),maxX=Math.max(...xs),minZ=Math.min(...zs),maxZ=Math.max(...zs);

  phi=.025;theta=Math.PI/2;

  radius=Math.max(130,Math.max((maxX-minX)/camera.aspect,maxZ-minZ+100)/(2*Math.tan(camera.fov*Math.PI/360)))*1.35;

  target.set((minX+maxX)/2,0,(minZ+maxZ)/2+35);updateCamera();

 }

});



function updateLabels(){

 const candidates=[];const close=radius<480;

 const top=document.getElementById('filters').getBoundingClientRect().bottom+8;

 const card=document.getElementById('card');

 const bottom=card.hidden||card.style.display==='none'?innerHeight-30:card.getBoundingClientRect().top-10;

 const reserved=['.badge','.tools','#more-tools'].map(q=>document.querySelector(q)).filter(Boolean).map(el=>el.getBoundingClientRect());

 for(const {b,s}of labels){

  s.el.style.display='none';

  if(!s.visible)continue;

  const important=b.region||['library','gym','canteen_main','teach_1','theater_market'].includes(b.id);

  if(!close&&!important&&b.id!==selected)continue;

  const p=s.position.clone().project(camera);

  if(p.z<-1||p.z>1)continue;

  const x=(p.x+1)*innerWidth/2,y=(1-p.y)*innerHeight/2;

  const w=Math.max(46,b.name.length*11+14),h=24;

  if(x-w/2<5||x+w/2>innerWidth-5||y<top+h||y>bottom)continue;

  if(reserved.some(r=>x+w/2>r.left-4&&x-w/2<r.right+4&&y>r.top-4&&y-h<r.bottom+4))continue;

  candidates.push({id:b.id,priority:b.id===selected?100:important?10:1,rect:[x-w/2,y-h,x+w/2,y],x,y,s});

 }

 const accepted=new Set(SceneUtils.chooseLabels(candidates));

 for(const c of candidates)if(accepted.has(c.id)){

  c.s.el.style.display='block';

  c.s.el.style.left=c.x+'px';

  c.s.el.style.top=c.y+'px';

  c.s.el.classList.toggle('chosen',c.id===selected);

 }

 document.getElementById('compass').style.transform='rotate('+(Math.PI-theta)+'rad)';

}



let lastFrame=0;

function frame(now){

 requestAnimationFrame(frame);

 if(paused||contextLost)return;

 if(flyAnimation)flyAnimation.update(now);

 else if(isCruising){

  cruiseTime+=0.0006;

  const t=(cruiseTime%1);

  const p=posCurve.getPointAt(t);

  const l=lookCurve.getPointAt(t);

  camera.position.copy(p);

  camera.lookAt(l);

  target.copy(l);

 }

 if(now-lastFrame>32){

  lastFrame=now;

  renderer.render(scene,camera);

  updateLabels();

 }

}

window.CampusDefaults?.mount();

requestAnimationFrame(frame);

})();

