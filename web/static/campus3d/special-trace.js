/* User special-area annotation: 1130 x 1067. Flat map cross-checks road
 * connectivity; photographic polygons specify parcels and building silhouettes.
 * A gym parcel includes paving; it is deliberately separate from the gym mass.
 * Facades, gym roof perimeter, court counts and site markings are schematic. */
(function(root){
const shapes={
 library:{outer:[[446,402],[493,455],[462,535],[514,606],[466,637],[397,538],[403,490]],roof:'terrace',glass:[1,2,3],terraceOutline:[[437,406],[393,491],[388,540],[460,642],[466,637],[397,538],[403,490],[446,402]]},
 gym:{outer:[[358,167],[474,128],[474,257],[437,279],[378,264],[348,220]],roof:'arena',arenaCenter:[[399,183],[447,178],[451,245],[400,254]],arenaShoulders:[[[358,167],[474,128],[447,178],[399,183]],[[474,128],[474,257],[451,245],[447,178]],[[474,257],[437,279],[378,264],[400,254],[451,245]],[[378,264],[348,220],[358,167],[399,183],[400,254]]]},
 canteen_main:{outer:[[487,730],[594,730],[594,861],[485,861]],roof:'canteen'},
 theater_market:{outer:[[594,813],[650,813],[650,791],[789,789],[789,862],[594,862]],roof:'traced',roofWings:[[[594,813],[650,813],[650,862],[594,862]],[[650,791],[789,789],[789,862],[650,862]]]}
};
const regions=[
 {id:'lake',name:'情缘湖',kind:'lake',category:'文体',color:'#318e91',outline:[[506,399],[581,382],[621,438],[669,507],[712,572],[714,579],[633,622],[597,620],[589,615],[533,556],[501,519],[509,466]],info:'情缘湖 · 环湖步行区域'},
 {id:'gym_plaza',name:'体育场周边',kind:'plaza',category:'文体',color:'#dbd5c6',outline:[[330,140],[485,105],[530,108],[504,131],[495,163],[498,322],[514,353],[480,340],[430,315],[350,295],[330,230]],info:'体育馆及前方铺地区域'},
 {id:'basketball_north',name:'北侧篮球场',kind:'basketball',category:'文体',color:'#6e9a8d',outline:[[291,439],[347,431],[370,564],[313,582]],grid:[[297,444],[341,440],[361,563],[316,573]],rows:2,cols:1,info:'篮球运动区域'},
 {id:'basketball_west',name:'西侧篮球场',kind:'basketball',category:'文体',color:'#789e9d',offset:[-9,0],outline:[[81,662],[144,662],[154,851],[71,855],[55,729],[80,729]],grid:[[82,668],[139,668],[150,844],[73,848]],rows:3,cols:2,info:'篮球运动区域'},
 {id:'badminton_courts',name:'羽毛球场',kind:'badminton',category:'文体',color:'#79a592',outline:[[617,675],[758,631],[788,776],[617,774]],grid:[[625,679],[752,642],[778,768],[625,768]],rows:2,cols:2,info:'羽毛球运动区域'},
 {id:'volleyball_courts',name:'排球场',kind:'volleyball',category:'文体',color:'#70a4ad',outline:[[389,865],[590,880],[608,983],[387,981]],grid:[[397,874],[581,888],[594,974],[396,972]],rows:1,cols:2,info:'排球运动区域'},
 {id:'snack_street',name:'小吃街',kind:'street',category:'生活',color:'#c7b695',offset:[-12,0],outline:[[46,355],[85,349],[138,602],[85,618]],info:'餐饮商铺区域'},
 {id:'driving_school',name:'驾校',kind:'training',category:'生活',color:'#c8c3b0',outline:[[590,886],[816,890],[786,994],[743,989],[742,1032],[634,1027],[632,984],[608,985]],info:'驾校训练场地'}
];
const trace={reference:{width:1130,height:1067,source:'User special-area satellite annotation'},shapes,regions,world:p=>[p[0]*.285-6,p[1]*.3-3.5]};
trace.apply=function(data,models,layout){
 for(const [id,s]of Object.entries(shapes)){const b=data.buildings.find(b=>b.id===id),m=models[id],points=s.outer.map(trace.world),xs=points.map(p=>p[0]),zs=points.map(p=>p[1]);b.x=(Math.min(...xs)+Math.max(...xs))/2;b.z=(Math.min(...zs)+Math.max(...zs))/2;const local=p=>{const q=trace.world(p);return [q[0]-b.x,q[1]-b.z];};
  m.outer=s.outer.map(local);m.holes=[];m.roof=s.roof;m.roofWings=(s.roofWings||[]).map(loop=>loop.map(local));m.links=[];m.infill=[];m.annex=[];m.corners=[];m.source='User special-area annotation';
  if(s.glass)m.glass=s.glass;if(s.terraceOutline)m.terraceOutline=s.terraceOutline.map(local);if(s.arenaCenter){m.arenaCenter=s.arenaCenter.map(local);m.arenaShoulders=s.arenaShoulders.map(loop=>loop.map(local));}
 }
 data.regions=regions.map(r=>{const convert=p=>trace.world(p).map((v,i)=>v+(r.offset?.[i]||0)),outline=r.outline.map(convert),x=outline.reduce((sum,p)=>sum+p[0],0)/outline.length,z=outline.reduce((sum,p)=>sum+p[1],0)/outline.length;return {...r,outline,x,z,region:true};});
 const pixels=p=>trace.world(p).map(v=>v*4);layout.lake=regions[0].outline.map(pixels);layout.courts=[];
 if(layout.roads&&layout.roads[5])layout.roads[5].points=[[496,395],[498,469],[489,519],[522,584],[573,642],[632,651],[728,597],[725,576],[622,431],[588,370],[496,395]].map(pixels);
 if(layout.defaultRoads&&layout.defaultRoads[5])layout.defaultRoads[5].points=[[496,395],[498,469],[489,519],[522,584],[573,642],[632,651],[728,597],[725,576],[622,431],[588,370],[496,395]].map(pixels);
};
// Small schematic furnishings, confined to the existing parcels. Shared geometry
// and materials keep this cosmetic layer inexpensive in the Android WebView.
trace.decorate=function(r,group,{flat,mat}){
 if(!['street','training'].includes(r.kind))return;
 const geometry=new THREE.BoxGeometry(1,1,1),palette=new Map();
 const material=c=>{if(!palette.has(c))palette.set(c,mat(c));return palette.get(c);};
 const prism=(w,h,d,x,y,z,c,parent=group)=>{const m=new THREE.Mesh(geometry,material(c));m.scale.set(w,h,d);m.position.set(x,y+h/2,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;};
 const stroke=(pts,c='#eee9d9')=>{const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts.map(p=>new THREE.Vector3(p[0],.39,p[1]))),new THREE.LineBasicMaterial({color:c}));group.add(line);};
 if(r.kind==='street'){
  const q=r.outline,p=(u,v)=>CampusLayout.bilinear(q,u,v),angle=-Math.atan2(q[3][0]-q[0][0],q[3][1]-q[0][1]);
  flat([p(.48,.02),p(.92,.02),p(.92,.98),p(.48,.98)],.34,'#ddd2bd',group);
  for(let i=0;i<23;i++)stroke([p(.49,(i+1)/24),p(.91,(i+1)/24)],'#c3b69f');
  for(let i=0;i<8;i++){const a=p(.25,.08+i*.115),g=new THREE.Group();g.position.set(a[0],0,a[1]);g.rotation.y=angle;group.add(g);
   prism(3.6,3.2,5,0,.35,0,'#eee1cb',g);prism(3.9,.45,5.35,0,3.55,0,'#665b50',g);
   prism(.12,1.45,3.9,1.83,1.3,0,'#4f7778',g);prism(1.4,.25,4.5,2.35,1.2,0,'#b88e60',g);
   prism(2.6,.2,5.2,2.55,3.1,0,i%2?'#d8ad65':'#bc7762',g);
   prism(.15,2.75,.15,3.75,.35,-2.25,'#786953',g);prism(.15,2.75,.15,3.75,.35,2.25,'#786953',g);
  }
  for(const v of [.025,.97]){const a=p(.73,v);prism(2.8,.7,1.5,a[0],.35,a[1],'#9c8970');prism(2.5,.65,1.2,a[0],1,a[1],'#72945d');}
 }else{
  const p=(u,v)=>trace.world([618+u*168,905+v*70]);
  const pts=[[.03,.08],[.94,.08],[.87,.87],[.18,.87],[.03,.08]].map(a=>p(...a));stroke(pts);
  for(let i=0;i<5;i++){const u=.11+i*.13;stroke([p(u,.08),p(u,.37),p(u+.1,.37),p(u+.1,.08)]);}
  // An illustrative bend and parking exercise; no real driving route is claimed.
  stroke([[.16,.7],[.25,.6],[.39,.6],[.49,.73],[.63,.73],[.76,.58]].map(a=>p(...a)),'#e3ca7b');
  stroke([[.16,.76],[.25,.67],[.36,.67],[.46,.8],[.65,.8],[.8,.63]].map(a=>p(...a)),'#e3ca7b');
  const coneGeo=new THREE.ConeGeometry(.38,1.1,5),coneMat=material('#ca8157');
  for(let i=0;i<12;i++){const a=p(.1+i*.065,.48),cone=new THREE.Mesh(coneGeo,coneMat);cone.position.set(a[0],.9,a[1]);group.add(cone);}
  for(let i=0;i<3;i++){const a=p(.16+i*.13,.21);prism(2.6,1.05,4.5,a[0],.38,a[1],['#dfdfce','#91afb5','#c3b398'][i]);prism(2.2,.65,2.4,a[0],1.43,a[1],'#547177');}
  const a=p(.88,.23);prism(4.7,2.8,4.1,a[0],.35,a[1],'#e3decc');prism(5.1,.35,4.5,a[0],3.15,a[1],'#637c72');
 }
};
trace.render=function(data,{scene,flat,mat}){
 const records=[];
 for(const r of data.regions){const group=new THREE.Group();scene.add(group);let outline=r.outline;
  if(r.kind==='lake')outline=new THREE.CatmullRomCurve3(outline.map(p=>new THREE.Vector3(p[0],0,p[1])),true,'centripetal').getPoints(100).map(p=>[p.x,p.z]);
  else {const shape=new THREE.Shape(outline.map(p=>new THREE.Vector2(p[0],-p[1]))),geo=new THREE.ExtrudeGeometry(shape,{depth:4,bevelEnabled:false});geo.rotateX(-Math.PI/2);const pad=new THREE.Mesh(geo,mat('#9eb98b'));pad.position.y=-4;scene.add(pad);}
  const y=r.kind==='plaza'?.1:.29,surface=flat(outline,y,r.kind==='training'?'#969e9b':r.kind==='street'?'#bbab91':r.color,group);surface.userData.id=r.id;
  trace.decorate(r,group,{flat,mat});
  const line=points=>{const mesh=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(p[0],y+.05,p[1]))),new THREE.LineBasicMaterial({color:'#f1eddd'}));group.add(mesh);};
  if(r.kind==='lake'){
   surface.material.roughness=.18;surface.material.metalness=.75;
   const shore=outline.map(p=>[r.x+(p[0]-r.x)*1.07,r.z+(p[1]-r.z)*1.07]);
   line(shore);
  }
  if(r.grid){const quad=r.grid.map(p=>trace.world(p).map((v,i)=>v+(r.offset?.[i]||0)));for(let row=0;row<r.rows;row++)for(let col=0;col<r.cols;col++){const p=(u,v)=>CampusLayout.bilinear(quad,(col+u)/r.cols,(row+v)/r.rows);line([p(.07,.07),p(.93,.07),p(.93,.93),p(.07,.93),p(.07,.07)]);line([p(.07,.5),p(.93,.5)]);
   if(r.kind==='basketball'){const circle=[];for(let i=0;i<=32;i++)circle.push(p(.5+.14*Math.cos(i*Math.PI/16),.5+.08*Math.sin(i*Math.PI/16)));line(circle);for(const end of [.07,.93]){const inner=end<.5?.24:.76;line([p(.32,end),p(.32,inner),p(.68,inner),p(.68,end)]);}}
   if(r.kind==='badminton'){for(const u of [.2,.8])line([p(u,.07),p(u,.93)]);for(const v of [.28,.72])line([p(.07,v),p(.93,v)]);}
   if(r.kind==='volleyball')for(const v of [.33,.67])line([p(.07,v),p(.93,v)]);
  }}
  records.push({b:r,group,surface});
 }
 return records;
};
if(typeof module!=='undefined')module.exports=trace;else {root.SpecialTrace=trace;trace.apply(root.CampusData,root.CampusFootprints,root.CampusLayout);}
})(typeof window!=='undefined'?window:globalThis);
