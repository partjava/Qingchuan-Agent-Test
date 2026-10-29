/* Ground geometry traced in the same reference coordinates as buildings. */
(function(){window.buildCampusGround=function({scene,flat,box,mat}){
 const L=CampusLayout,W=L.world;
 const groundSchematic=new THREE.Group();
 scene.add(groundSchematic);
 const polygon=(points,y,color)=>flat(points.map(W),y,color,groundSchematic);
 const base=new THREE.Shape(L.boundary.map(p=>new THREE.Vector2(p[0]/4,-p[1]/4)));
 const geo=new THREE.ExtrudeGeometry(base,{depth:4,bevelEnabled:false});geo.rotateX(-Math.PI/2);
 
 // Base lawn - fresh vibrant collegiate green
 const land=new THREE.Mesh(geo,mat('#5a9254'));
 land.position.y=-4;land.receiveShadow=true;groundSchematic.add(land);

 // South Gate Entrance Plaza & Ceremonial paving
 polygon(L.plaza,.06,'#ded7c8');
 polygon([[352,154],[529,112],[580,116],[551,143],[540,182],[544,372],[562,410],[523,394],[466,364],[375,340],[352,262]],.06,'#dfdbd0');
 polygon(L.grass,.08,'#5c9656');

 // Central Ceremonial White Marble Pathway (国旗大道主轴线)
 const centralWalk=[[806,1150],[830,1150],[830,730],[806,730]];
 polygon(centralWalk,.14,'#f7f5ee');
 polygon([[796,1150],[806,1150],[806,730],[796,730]],.13,'#dcd5c7');
 polygon([[830,1150],[840,1150],[840,730],[830,730]],.13,'#dcd5c7');

 const roadGroup=new THREE.Group();
 groundSchematic.add(roadGroup);

 // Load custom roads from storage if user customized them
  try{
   let saved = null;
   if(window.CampusNativeBridge && typeof window.CampusNativeBridge.loadConfig === 'function'){
    saved = window.CampusNativeBridge.loadConfig('custom_campus_roads');
   }
   if(!saved && typeof localStorage !== 'undefined' && localStorage){
    saved = localStorage.getItem('custom_campus_roads');
   }
   if(saved !== null && saved !== undefined){
    const parsed = JSON.parse(saved);
    if(Array.isArray(parsed)) L.roads = parsed;
   }
  }catch(e){}

 // All curb surfaces sit below all road surfaces, keeping crossings seamless.
 function drawRoadNetwork(roads){roadGroup.add(window.CampusRoadGeometry.build(THREE,roads));}
 drawRoadNetwork(L.roads);

 window.rebuildCampusRoads=function(newRoads){
  while(roadGroup.children.length>0){
   const obj=roadGroup.children[0];
   obj.traverse(child=>{if(child.geometry)child.geometry.dispose();if(child.material)child.material.dispose();});
   roadGroup.remove(obj);
  }
  drawRoadNetwork(newRoads);
  L.roads=newRoads;
  if(window.CampusNativeBridge && typeof window.CampusNativeBridge.saveConfig === 'function'){
    try{ window.CampusNativeBridge.saveConfig('custom_campus_roads', JSON.stringify(newRoads)); }catch(e){}
   }
   try{ if(typeof localStorage !== 'undefined' && localStorage) localStorage.setItem('custom_campus_roads', JSON.stringify(newRoads)); }catch(e){}
 };

 // Crosswalk zebra stripes at key pedestrian crossings
 function drawCrosswalk(pt,angle,stripes=5){
  const [cx,cz]=W(pt);
  for(let s=-stripes/2;s<=stripes/2;s++){
   const bar=box(2.2,.09,.42,cx+Math.sin(angle)*s*.85, .14, cz+Math.cos(angle)*s*.85,'#f7f4ed',groundSchematic);
   bar.rotation.y=angle;
  }
 }
 drawCrosswalk([818,1088],0,6);          // 南门广场前斑马线
 drawCrosswalk([818,750],0,5);           // 晴川广场北端湖滨斑马线
 drawCrosswalk([920,1088],Math.PI/2,5);  // 教学区西侧主路斑马线
 drawCrosswalk([505,1065],Math.PI/2,5);  // 宿舍生活大道交叉口斑马线
 drawCrosswalk([480,1065],Math.PI/2,5);  // 食堂超市前斑马线
 drawCrosswalk([670,1070],0,4);          // 小剧场与运动场斑马线

 // The lake surface and shore are owned by SpecialTrace's movable region group.

 const line=(points,y=.4,color='#f5f0e1')=>{const mesh=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(p[0]/4,y,p[1]/4))),new THREE.LineBasicMaterial({color}));groundSchematic.add(mesh);};
 
 const stadiumGroup=new THREE.Group();
 scene.add(stadiumGroup);
 window.stadiumGroup=stadiumGroup;
 const stadiumPolygon=(points,y,color)=>flat(points.map(W),y,color,stadiumGroup);
 const stadiumLine=(points,y=.4,color='#f5f0e1')=>{const mesh=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(p[0]/4,y,p[1]/4))),new THREE.LineBasicMaterial({color}));stadiumGroup.add(mesh);};

 // Athletic Running Track & Football Soccer Pitch
 const curve=new THREE.CatmullRomCurve3(L.track.map(p=>new THREE.Vector3(p[0],0,p[1])),true,'centripetal');
 const track=curve.getPoints(100).map(p=>[p.x,p.z]);
 const stadiumSurface=stadiumPolygon(track,.25,'#ba4938');
 stadiumSurface.userData.id='stadium';
 window.stadiumSurface=stadiumSurface;

 const c=[638,266];
 for(const scale of [.98,.94,.9,.86,.82])stadiumLine(track.map(p=>[c[0]+(p[0]-c[0])*scale,c[1]+(p[1]-c[1])*scale]),.29,'#ffffff');
 const pitchSurface=stadiumPolygon(L.pitch,.32,'#4e8a52');
 pitchSurface.userData.id='stadium';
 stadiumLine([...L.pitch,L.pitch[0]],.35,'#ffffff');
 const pitchPoint=(u,v)=>L.bilinear(L.pitch,u,v);
 stadiumLine([pitchPoint(0,.5),pitchPoint(1,.5)],.35,'#ffffff');
 const circle=[];for(let i=0;i<=60;i++)circle.push(pitchPoint(.5+.14*Math.cos(i*Math.PI/30),.5+.08*Math.sin(i*Math.PI/30)));stadiumLine(circle,.35,'#ffffff');
 for(const v of [0,1]){const end=v===0?.17:.83;stadiumLine([pitchPoint(.22,v),pitchPoint(.22,end),pitchPoint(.78,end),pitchPoint(.78,v)],.35,'#ffffff');}
 
 L.courts.forEach((quad,index)=>{
  const rows=index===0?3:2,cols=2;
  polygon(quad,.25,index===2?'#5a9ca4':'#5c9779');
  for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){
   const p=(u,v)=>L.bilinear(quad,(c+u)/cols,(r+v)/rows);
   const rect=[p(.09,.08),p(.91,.08),p(.91,.92),p(.09,.92)];
   line([...rect,rect[0]],.3,'#ffffff');line([p(.09,.5),p(.91,.5)],.3,'#ffffff');
  }
 });
 if(window.AcademicTrace)AcademicTrace.buildParking({scene:groundSchematic,flat,mat});

 // Trees - Lush Greenery along Avenues and Lakeside
 function inside(p,loop){let hit=false;for(let i=0,j=loop.length-1;i<loop.length;j=i++){const a=loop[i],b=loop[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;}
 const buildings=CampusData.buildings.flatMap(b=>{const m=CampusFootprints[b.id];return [m.outer,...(m.links||[]).map(link=>link.outline)].map(loop=>loop.map(p=>[p[0]*4+b.x*4,p[1]*4+b.z*4]));});
 if(window.AcademicTrace)buildings.push(AcademicTrace.parkingWorld.map(p=>p.map(v=>v*4)));
 if(CampusData.regions)buildings.push(...CampusData.regions.filter(r=>!['plaza','lake'].includes(r.kind)).map(r=>r.outline.map(p=>p.map(v=>v*4))));
 
 const trunkGeo=new THREE.CylinderGeometry(.3,.4,1.8,5),leafGeo=new THREE.IcosahedronGeometry(1.9,0);
 const treeMats=['#447b48','#558e5a','#689f64'].map(c=>mat(c));
 const trunkMat=mat('#7d6f55');

 for(const road of L.roads)for(let i=1;i<road.points.length;i++){
  const a=road.points[i-1],b=road.points[i],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);
  if(len<20)continue;
  for(let t=18;t<len-10;t+=38)for(const sign of [-1,1]){
   const offset=(road.width/2+3.2)*4,p=[a[0]+dx*t/len-sign*dz/len*offset,a[1]+dz*t/len+sign*dx/len*offset];
   if(!inside(p,L.boundary)||inside(p,L.lake)||buildings.some(loop=>inside(p,loop)))continue;
   const [x,z]=W(p);
   const trunk=new THREE.Mesh(trunkGeo,trunkMat);
   const leaf=new THREE.Mesh(leafGeo,treeMats[(Math.round(x+z)%3)]);
   const s=0.85+Math.sin(x*17+z*31)*0.2;
   trunk.scale.set(s,s,s);leaf.scale.set(s,s,s);
   trunk.position.set(x,.9*s,z);leaf.position.set(x,3.2*s,z);leaf.castShadow=true;
   groundSchematic.add(trunk,leaf);
  }
 }

 // --- High-Resolution Perfectly Aligned Aerial Satellite Ground Texture Layer ---
 const aerialGroup=new THREE.Group();
 scene.add(aerialGroup);
 
 // Base Architectural Plinth
 const plinthGeo=new THREE.BoxGeometry(334,4,319);
 const plinthMat=mat('#2c352f');
 const plinthMesh=new THREE.Mesh(plinthGeo,plinthMat);
 plinthMesh.position.set(165,-2.02,157.5);
 plinthMesh.receiveShadow=true;
 aerialGroup.add(plinthMesh);

 const texLoader=new THREE.TextureLoader();
 texLoader.load('campus_aerial.jpg',function(tex){
   if(THREE.SRGBColorSpace)tex.colorSpace=THREE.SRGBColorSpace;
   tex.minFilter=THREE.LinearFilter;
   tex.magFilter=THREE.LinearFilter;
   
   // Exact 1:1 isometric match to reference 1320 x 1260 (world size: 330 x 315)
   const planeGeo=new THREE.PlaneGeometry(330,315);
   planeGeo.rotateX(-Math.PI/2);
   const planeMat=new THREE.MeshStandardMaterial({
     map:tex,
     roughness:0.82,
     metalness:0.04
   });
   const aerialMesh=new THREE.Mesh(planeGeo,planeMat);
   aerialMesh.position.set(165,0.02,157.5);
   aerialMesh.receiveShadow=true;
   aerialGroup.add(aerialMesh);
 });

 let groundMode='schematic';
 window.getGroundMode=()=>groundMode;
 window.setGroundMode=function(mode){
   groundMode=mode==='aerial'?'aerial':'schematic';
   const isAerial=(mode==='aerial');
   aerialGroup.visible=isAerial;
   groundSchematic.visible=!isAerial;
   const btn=document.getElementById('mode');
   if(btn){btn.textContent=isAerial?'实景':'沙盘';btn.classList.toggle('active',isAerial);}
 };
 // Default to the lush, detailed 3D Sandbox mode
 window.setGroundMode('schematic');
};})();
