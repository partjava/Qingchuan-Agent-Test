/**
 * 晴川 3D 校园 · 可视化交互式路网网格编辑器 (Visual Road Grid Editor)
 * 功能特性：
 * 1. 🖐️ 移动视野：单指顺畅滑动平移整个校园地图，双指捏合缩放
 * 2. 🔘 两点连线：点击起点与终点，自动吸附20像素(5米)正交网格生成笔直道路
 * 3. 🖌️ 涂抹划线：按住手指连续滑动，沿途网格自动平滑铺设道路
 * 4. 🧹 橡皮擦：点选或划过任意已画道路，即可精准擦除该段道路
 * 5. 宽度与材质：主路 6m (深灰沥青)、次干 4.5m (中灰沥青)、白板路 3m (米白色石板人行道)
 * 6. 可折叠面板：一键收起为极简顶部浮标，展开可操作撤销/清空/导出/3D生成
 */
(function(root){
 function createRoadEditor(){
  let isEditing=false;
  let previousGroundMode='schematic';
  let isCollapsed=false;
  let drawMode='point'; // 'pan' (移动视野), 'point' (两点连线), 'drag' (涂抹划路), 'erase' (橡皮擦)
  let currentWidth=6.0; // 道路宽度：6.0 (主路), 4.5 (次干), 3.0 (白板路)
  let roads=[];         // 当前草稿道路列表
  let activePoints=[];  // 当前正在绘制的折线点
  let redoHistory=[],diagnosticsVisible=false;
  const packagedRoads=JSON.parse(JSON.stringify(window.CampusDefaults?.roads||window.CampusLayout?.roads||[]));
  let history=[];       // 撤销历史栈
  let editorGroup=null;
  let gridHelper=null;
  let markerMesh=null;
  let previewGroup=null;
  let raycaster=null;
  let groundPlane=null;
  let sceneRef=null, cameraRef=null, rendererRef=null;

  const GRID_STEP=8; // 网格步长（参考坐标系下每格 20 像素，对应世界尺寸 5 米）
  const snap=v=>Math.round(v/GRID_STEP)*GRID_STEP;

  function init({scene, camera, renderer}){
   sceneRef=scene;cameraRef=camera;rendererRef=renderer;
   raycaster=new THREE.Raycaster();
   groundPlane=new THREE.Plane(new THREE.Vector3(0,1,0),0);

   editorGroup=new THREE.Group();
   editorGroup.visible=false;
   scene.add(editorGroup);

   // 1. 创建半透明辅助正交网格线（覆盖 1320 x 1260 校园沙盘，每格2米）
   const gridGeo=new THREE.BufferGeometry();
   const gridPts=[];
   for(let x=0;x<=1320;x+=GRID_STEP){
    gridPts.push(x/4,.32,0, x/4,.32,1260/4);
   }
   for(let z=0;z<=1260;z+=GRID_STEP){
    gridPts.push(0,.32,z/4, 1320/4,.32,z/4);
   }
   gridGeo.setAttribute('position',new THREE.Float32BufferAttribute(gridPts,3));
   const gridMat=new THREE.LineBasicMaterial({color:'#4fa88d',transparent:true,opacity:.38});
   gridHelper=new THREE.LineSegments(gridGeo,gridMat);
   editorGroup.add(gridHelper);

   // 2. 当前选中吸附点光圈指示器
   const markerGeo=new THREE.RingGeometry(.7,1.4,16);markerGeo.rotateX(-Math.PI/2);
   const markerMat=new THREE.MeshBasicMaterial({color:'#ffc83b',side:THREE.DoubleSide});
   markerMesh=new THREE.Mesh(markerGeo,markerMat);
   markerMesh.position.y=.42;
   markerMesh.visible=false;
   editorGroup.add(markerMesh);

   // 3. 动态绘制线预览组
   previewGroup=new THREE.Group();
   editorGroup.add(previewGroup);

   loadInitialRoads();
   createUI();
   setupPointerEvents();
  }

  
  function recordHistory(){history.push(JSON.parse(JSON.stringify(roads)));if(history.length>100)history.shift();redoHistory=[];}
  function restoreGesture(){if(!gestureSnapshot)return;roads=gestureSnapshot.roads;activePoints=gestureSnapshot.activePoints;history=gestureSnapshot.history;redoHistory=gestureSnapshot.redo;}
  function undoRedo(redo=false){const from=redo?redoHistory:history,to=redo?history:redoHistory;if(!from.length)return;to.push(JSON.parse(JSON.stringify(roads)));if(to.length>100)to.shift();roads=from.pop();activePoints=[];updatePreview();autoSaveRoads();}
  function resetDefaultRoads(){recordHistory();roads=JSON.parse(JSON.stringify(packagedRoads));activePoints=[];updatePreview();autoSaveRoads();showToast('已恢复默认道路，可撤销');}
  function autoSaveRoads(){

   if(window.CampusNativeBridge && typeof window.CampusNativeBridge.saveConfig === 'function'){
    try{ window.CampusNativeBridge.saveConfig('custom_campus_roads', JSON.stringify(roads)); }catch(e){}
   }
   try{
    if(typeof localStorage !== 'undefined' && localStorage){
     localStorage.setItem('custom_campus_roads', JSON.stringify(roads));
    }
   }catch(e){}
   window.CampusDefaults?.markSaved('roads');
  }

  function loadInitialRoads(){
   if(window.CampusNativeBridge && typeof window.CampusNativeBridge.loadConfig === 'function'){
    try{
     const nativeStr = window.CampusNativeBridge.loadConfig('custom_campus_roads');
     if(nativeStr){ roads = JSON.parse(nativeStr); return; }
    }catch(e){}
   }
   try{
    if(typeof localStorage !== 'undefined' && localStorage){
     const stored = localStorage.getItem('custom_campus_roads');
     if(stored !== null){ roads = JSON.parse(stored); return; }
    }
   }catch(e){}
   if(packagedRoads.length>0){
    roads=JSON.parse(JSON.stringify(packagedRoads));
   }else{
    roads=[];
   }
  }

  function updatePreview(){
   while(previewGroup.children.length>0){
    const obj=previewGroup.children[0];
    const dispose=child=>{if(child.geometry)child.geometry.dispose();if(child.material&&child.material.dispose)child.material.dispose();};
    if(obj.traverse)obj.traverse(dispose);else dispose(obj);
    previewGroup.remove(obj);
   }
   const W=(window.CampusLayout&&window.CampusLayout.world)?window.CampusLayout.world:p=>[p[0]/4,p[1]/4];

   // Use the same junction geometry as the saved map.
   if(window.CampusRoadGeometry){
    previewGroup.add(window.CampusRoadGeometry.build(THREE,roads,{y:.4,preview:true}));
   }else{
   // 渲染已绘制的所有路段
   for(const r of roads){
    const pts=r.points;
    if(!pts||pts.length<2)continue;
    const isWhitePaved=(r.width<=3.2); // 3m 支路为米白色白板路
    const roadColor=isWhitePaved?'#eae5dc':'#3a4042';
    const lineColor=isWhitePaved?'#c5bdae':'#ffd15c';

    for(let i=1;i<pts.length;i++){
     const a=W(pts[i-1]),b=W(pts[i]);
     const dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);
     if(len<.1)continue;
     const angle=Math.atan2(dx,dz);
     const mx=(a[0]+b[0])/2,mz=(a[1]+b[1])/2;
     const geo=new THREE.BoxGeometry(r.width,.12,len);
     const mat=new THREE.MeshBasicMaterial({color:roadColor});
     const m=new THREE.Mesh(geo,mat);
     m.position.set(mx,.4,mz);m.rotation.y=angle;
     previewGroup.add(m);

     // 中心导引线（主路金黄色，白板路米灰线）
     const lineGeo=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(a[0],.52,a[1]),new THREE.Vector3(b[0],.52,b[1])]);
     const lineMat=new THREE.LineBasicMaterial({color:lineColor,linewidth:2});
     previewGroup.add(new THREE.Line(lineGeo,lineMat));
    }
   }

   }

   // 渲染当前正在连线的临时活动线段
   if(activePoints.length>0){
    for(let i=1;i<activePoints.length;i++){
     const a=W(activePoints[i-1]),b=W(activePoints[i]);
     const lineGeo=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(a[0],.6,a[1]),new THREE.Vector3(b[0],.6,b[1])]);
     const lineMat=new THREE.LineBasicMaterial({color:'#ff5e3a',linewidth:3});
     previewGroup.add(new THREE.Line(lineGeo,lineMat));
    }
   }
   drawDiagnostics();
   updateCollapsedLabel();
  }

  function getWorldCoords(e, snapToGrid=true){
   if(!rendererRef||!cameraRef)return null;
   const rect=rendererRef.domElement.getBoundingClientRect();
   const x=((e.clientX-rect.left)/rect.width)*2-1;
   const y=-((e.clientY-rect.top)/rect.height)*2+1;
   raycaster.setFromCamera(new THREE.Vector2(x,y),cameraRef);
   const hit=new THREE.Vector3();
   if(raycaster.ray.intersectPlane(groundPlane,hit)){
    let refX = hit.x*4;
    let refZ = hit.z*4;
    if(drawMode!=='erase'&&window.CampusRoadTools){
     const result=window.CampusRoadTools.snapPoint([refX,refZ],roads,10);
     if(result.kind){if(markerMesh?.material?.color)markerMesh.material.color.set('#34b78b');return result.point;}
    }
    if(markerMesh?.material?.color)markerMesh.material.color.set('#ffc83b');
    if(snapToGrid){
     refX = snap(refX);
     refZ = snap(refZ);
    }else{
     refX = Math.round(refX*10)/10;
     refZ = Math.round(refZ*10)/10;
    }
    if(refX>=0&&refX<=1320&&refZ>=0&&refZ<=1260){
     return [refX,refZ];
    }
   }
   return null;
  }

  // 橡皮擦功能：擦除指定交点附近的路段
  function eraseNear(pt){
   if(!pt||roads.length===0)return false;
   let erased=false;
   const remainingRoads=[];
   for(const r of roads){
    const pts=r.points;
    let hit=false;
    for(let i=1;i<pts.length;i++){
     const p1=pts[i-1],p2=pts[i];
     const d1=Math.hypot(pt[0]-p1[0],pt[1]-p1[1]);
     const d2=Math.hypot(pt[0]-p2[0],pt[1]-p2[1]);
     if(d1<=GRID_STEP*1.1||d2<=GRID_STEP*1.1){
      hit=true;break;
     }
     const l2=(p2[0]-p1[0])**2+(p2[1]-p1[1])**2;
     if(l2>0){
      let t=((pt[0]-p1[0])*(p2[0]-p1[0])+(pt[1]-p1[1])*(p2[1]-p1[1]))/l2;
      t=Math.max(0,Math.min(1,t));
      const projX=p1[0]+t*(p2[0]-p1[0]);
      const projZ=p1[1]+t*(p2[1]-p1[1]);
      const dist=Math.hypot(pt[0]-projX,pt[1]-projZ);
      if(dist<=(r.width*4/2)+GRID_STEP*0.8){
       hit=true;break;
      }
     }
    }
    if(hit)erased=true;
    else remainingRoads.push(r);
   }

   if(erased){
    recordHistory();
    roads=remainingRoads;
    updatePreview();
    autoSaveRoads();
    showToast('🧹 已精准擦除触碰的道路');
    return true;
   }
   return false;
  }

  let isDragging=false;
  let lastDragPt=null;
  const drawingPointers=new Set();
  let gesturePaused=false,gestureSnapshot=null;

  function setupPointerEvents(){
   const dom=rendererRef.domElement;

   dom.addEventListener('pointerdown',e=>{
    if(!isEditing)return;
    drawingPointers.add(e.pointerId);
    if(drawingPointers.size>1){
     gesturePaused=true;isDragging=false;lastDragPt=null;
     if(gestureSnapshot){restoreGesture();autoSaveRoads();updatePreview();}
     markerMesh.visible=false;
     return;
    }
    if(gesturePaused)return;
    gestureSnapshot={roads:JSON.parse(JSON.stringify(roads)),activePoints:JSON.parse(JSON.stringify(activePoints)),history:history.slice(),redo:redoHistory.slice()};
    if(drawMode==='pan')return; // 移动模式由 campus-scene.js 处理单指平移

    const shouldSnap = (drawMode === 'point');
    const pt = getWorldCoords(e, shouldSnap);
    if(!pt)return;

    if(drawMode==='erase'){
     // 橡皮擦模式：按下直接擦除
     isDragging=true;
     eraseNear(pt);
     markerMesh.position.set(pt[0]/4,.42,pt[1]/4);
     markerMesh.visible=true;
    }else if(drawMode==='point'){
     // 点选模式：点击一个点，再点击下一个点连线
     markerMesh.position.set(pt[0]/4,.42,pt[1]/4);
     markerMesh.visible=true;
     if(activePoints.length===0){
      activePoints.push(pt);
      showToast('已选起点 ('+pt[0]+', '+pt[1]+')，请点击下一个网格交点连线');
     }else{
      const prev=activePoints[activePoints.length-1];
      if(prev[0]!==pt[0]||prev[1]!==pt[1]){
       recordHistory();
       roads.push({width:currentWidth,points:[prev,pt]});
       activePoints=[pt];
       updatePreview();
       autoSaveRoads();
       showToast('已连接道路！继续点击连线，或点击“结束当前段”');
      }
     }
    }else if(drawMode==='drag'){
     // 涂抹模式：按下开始
     isDragging=true;
     activePoints=[pt];
     lastDragPt=pt;
     updatePreview();
    }
   });

   dom.addEventListener('pointermove',e=>{
    if(!isEditing||drawMode==='pan'||gesturePaused)return;
    const shouldSnap = (drawMode === 'point');
    const pt = getWorldCoords(e, shouldSnap);
    if(pt){
     markerMesh.position.set(pt[0]/4,.42,pt[1]/4);
     markerMesh.visible=(drawMode!=='pan');
    }
    if(drawMode==='erase'&&isDragging&&pt){
     eraseNear(pt);
    }else if(drawMode==='drag'&&isDragging&&pt&&lastDragPt){
     const dist=Math.hypot(pt[0]-lastDragPt[0],pt[1]-lastDragPt[1]);
     if(dist>=8){
      activePoints.push(pt);
      lastDragPt=pt;
      updatePreview();
     }
    }
   });

   dom.addEventListener('pointerup',e=>{
    drawingPointers.delete(e.pointerId);
    if(gesturePaused){if(!drawingPointers.size){gesturePaused=false;gestureSnapshot=null;}return;}
    if(!isEditing||drawMode==='pan')return;
    if(drawMode==='drag'&&isDragging){
     const end=getWorldCoords(e,false);if(end&&activePoints.length&&Math.hypot(end[0]-activePoints.at(-1)[0],end[1]-activePoints.at(-1)[1])>.1)activePoints.push(end);
     isDragging=false;
     if(activePoints.length>=2){
      recordHistory();
      roads.push({width:currentWidth,points:[...activePoints]});
      showToast('已生成自由绘制道路（'+activePoints.length+'个节点，顺滑随笔）');
     }
     activePoints=[];
     updatePreview();
     autoSaveRoads();
    }else if(drawMode==='erase'){
     isDragging=false;
    }
   });
   dom.addEventListener('pointercancel',e=>{
    drawingPointers.delete(e.pointerId);isDragging=false;lastDragPt=null;
    if(gestureSnapshot&&!gesturePaused){restoreGesture();autoSaveRoads();updatePreview();}
    if(!drawingPointers.size){gesturePaused=false;gestureSnapshot=null;}
    markerMesh.visible=false;
   });
  }

  function drawDiagnostics(){
   const el=document.getElementById('ed-network-status');if(!window.CampusRoadTools)return;
   if(!diagnosticsVisible){if(el)el.textContent='';return;}
   const report=window.CampusRoadTools.analyze(roads);
   if(el)el.textContent=diagnosticsVisible?'检查结果：'+report.components+' 个路网分区 · '+report.deadEnds.length+' 个端点 · '+report.gaps.length+' 处近距离间隙（端点可能是正常入口）':'';
   if(!diagnosticsVisible)return;
   const mark=p=>{const geo=new THREE.RingGeometry(1.4,1.8,20);geo.rotateX(-Math.PI/2);const m=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({color:'#e79c35',side:THREE.DoubleSide}));m.position.set(p[0]/4,.65,p[1]/4);previewGroup.add(m);};
   report.deadEnds.forEach(mark);
   const lines=(a,b,color)=>previewGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(a[0]/4,.67,a[1]/4),new THREE.Vector3(b[0]/4,.67,b[1]/4)]),new THREE.LineBasicMaterial({color})));
   report.gaps.forEach(g=>lines(g.from,g.to,'#ed7048'));
   for(const id of report.isolated){const pts=roads[id].points;for(let i=1;i<pts.length;i++)lines(pts[i-1],pts[i],'#db755d');}
  }
  function showToast(msg){
   const el=document.getElementById('editor-toast');
   if(el){
    el.textContent=msg;
    el.style.opacity='1';
    clearTimeout(el._t);
    el._t=setTimeout(()=>{el.style.opacity='0';},2500);
   }
  }

  function getModeName(){
   if(drawMode==='pan')return '🖐️ 移动视野';
   if(drawMode==='point')return '🔘 两点连线';
   if(drawMode==='drag')return '🖌️ 涂抹划线';
   if(drawMode==='erase')return '🧹 橡皮擦';
   return '';
  }

  function getWidthName(){
   if(currentWidth===6.0)return '主路 6m';
   if(currentWidth===4.5)return '次干 4.5m';
   return '白板路 3m';
  }

  function updateCollapsedLabel(){
   const undo=document.getElementById('ed-undo'),redo=document.getElementById('ed-redo');
   if(undo)undo.disabled=!history.length;if(redo)redo.disabled=!redoHistory.length;
   const lbl=document.getElementById('ed-collapsed-label');
   if(lbl){
    lbl.textContent=getModeName()+' · '+getWidthName()+' ('+roads.length+'段)';
   }
  }

  function createUI(){
   // 1. 在右侧工具栏添加【画路】按钮
   const tools=document.getElementById('tools-scroll')||document.getElementById('tools')||document.getElementById('more-tools')||document.querySelector('.tools');
   if(tools&&!document.getElementById('road-editor-btn')){
    const btn=document.createElement('button');
    btn.id='road-editor-btn';
    btn.textContent='画路';
    btn.title='开启网格画路编辑面板';
    btn.onclick=toggleEditor;
    tools.appendChild(btn);
    if(typeof window!=="undefined"&&window.restoreToolsScroll)window.restoreToolsScroll();
   }

   // 2. 创建顶部和底部编辑器 HUD 面板（支持收起与展开）
   const hud=document.createElement('div');
   hud.id='road-editor-hud';
   hud.style.cssText='display:none;position:fixed;inset:0;pointer-events:none;z-index:9;font-family:system-ui,-apple-system,sans-serif;';
   hud.innerHTML=`
    <section id="ed-panel-full" class="editor-panel" aria-label="校园道路绘制">
      <header class="editor-header">
        <div><p class="editor-kicker">CAMPUS STUDIO</p><div class="editor-title">绘制道路</div></div>
        <div class="editor-header-actions"><button id="ed-collapse-btn" class="editor-icon" aria-label="收起道路面板">收起</button><button id="ed-close-btn" class="editor-done">完成</button></div>
      </header>
      <div class="editor-section"><span class="editor-section-label">绘制方式</span><div class="editor-options">
        <button id="ed-mode-pan">↔ 移动视野</button><button id="ed-mode-point" style="background:#215e48;color:white">＋ 两点连线</button><button id="ed-mode-drag">〰 连续绘制</button><button id="ed-mode-erase">− 擦除道路</button>
      </div></div>
      <div class="editor-section"><span class="editor-section-label">道路类型</span><div class="editor-options editor-widths">
        <button id="ed-w-6" style="background:#215e48;color:white">主路 · 6m</button><button id="ed-w-4">次干路 · 4.5m</button><button id="ed-w-3">步行道 · 3m</button>
      </div></div>
      <div class="editor-history"><button id="ed-finish-active">结束当前段</button><button id="ed-undo">↶ 撤销</button><button id="ed-redo">↷ 重做</button></div>
      <div class="editor-history"><button id="ed-reset-default">恢复默认道路</button><button id="ed-check-network">检查连通</button></div><p id="ed-network-status" class="editor-caption" aria-live="polite"></p>
      <div class="editor-footer"><button id="ed-clear" class="editor-danger">清空道路</button><button id="ed-export">导出路网</button><button id="ed-save" class="editor-primary">应用路网</button></div>
      <p class="editor-caption">端点与路段自动吸附 · 绿色光圈表示已接上 · 修改自动保存</p>
    </section>
    <div id="ed-panel-mini" class="editor-mini" style="display:none"><strong>绘制道路</strong><span id="ed-collapsed-label">两点连线 · 主路 6m</span><button id="ed-expand-btn">展开 ↑</button></div>
    <div id="editor-toast" class="editor-toast">点击网格开始连线</div>
   `;
   document.body.appendChild(hud);

   // 绑定展开/收起事件
   const panelFull=document.getElementById('ed-panel-full');
   const panelMini=document.getElementById('ed-panel-mini');
   const setCollapse=(collapsed)=>{
    isCollapsed=collapsed;
    panelFull.style.display=collapsed?'none':'flex';
    panelMini.style.display=collapsed?'flex':'none';
    updateCollapsedLabel();
   };
   document.getElementById('ed-collapse-btn').onclick=()=>setCollapse(true);
   document.getElementById('ed-expand-btn').onclick=()=>setCollapse(false);

   // 绑定模式切换
   const setMode=(mode)=>{
    drawMode=mode;
    activePoints=[];
    ['ed-mode-pan','ed-mode-point','ed-mode-drag','ed-mode-erase'].forEach(id=>{
     const el=document.getElementById(id);
     const isActive=(id==='ed-mode-'+mode);
     if(id==='ed-mode-erase'){
      el.style.background=isActive?'#8f2d2d':'#ecdada';
      el.style.color=isActive?'white':'#8f2d2d';
     }else{
      el.style.background=isActive?'#215e48':'#e5ece8';
      el.style.color=isActive?'white':'#284d40';
     }
    });
    if(markerMesh)markerMesh.visible=(mode!=='pan');
    updateCollapsedLabel();
    if(mode==='pan')showToast('🖐️ 移动视野模式：单指滑动即可平移整个校园地图');
    else if(mode==='point')showToast('🔘 两点连线模式：点击起点交点，再点击终点生成道路');
    else if(mode==='drag')showToast('🖌️ 涂抹划线模式：随手指/鼠标任意滑动画线，不限网格，轻松画斜线！');
    else if(mode==='erase')showToast('🧹 橡皮擦模式：点击或划过任意已画道路即可精准擦除');
   };

   document.getElementById('ed-mode-pan').onclick=()=>setMode('pan');
   document.getElementById('ed-mode-point').onclick=()=>setMode('point');
   document.getElementById('ed-mode-drag').onclick=()=>setMode('drag');
   document.getElementById('ed-mode-erase').onclick=()=>setMode('erase');

   // 绑定路宽与白板路切换
   const setWidth=(w,elId)=>{
    currentWidth=w;
    ['ed-w-6','ed-w-4','ed-w-3'].forEach(id=>{
     const el=document.getElementById(id);
     el.style.background=(id===elId)?'#215e48':'#e5ece8';
     el.style.color=(id===elId)?'white':'#284d40';
    });
    updateCollapsedLabel();
    if(w<=3.2)showToast('已选【白板路 3m】：米白色石板人行道材质');
    else showToast('已选路宽 '+w+'m：深灰沥青机动车道材质');
   };
   document.getElementById('ed-w-6').onclick=()=>setWidth(6.0,'ed-w-6');
   document.getElementById('ed-w-4').onclick=()=>setWidth(4.5,'ed-w-4');
   document.getElementById('ed-w-3').onclick=()=>setWidth(3.0,'ed-w-3');

   // 结束当前折线
   document.getElementById('ed-finish-active').onclick=()=>{
    activePoints=[];
    if(markerMesh)markerMesh.visible=false;
    updatePreview();
    showToast('已结束当前线段，点击下一个点开始新路段');
   };

   // 撤销一步
   document.getElementById('ed-undo').onclick=()=>undoRedo();
   document.getElementById('ed-redo').onclick=()=>undoRedo(true);
   document.getElementById('ed-reset-default').onclick=resetDefaultRoads;
   document.getElementById('ed-check-network').onclick=()=>{diagnosticsVisible=!diagnosticsVisible;document.getElementById('ed-check-network').textContent=diagnosticsVisible?'隐藏检查':'检查连通';updatePreview();};

   // 清空所有道路
   document.getElementById('ed-clear').onclick=()=>{
    if(confirm('确定要清空画布上的所有道路吗？(可随时点撤销恢复)')){
     recordHistory();
     roads=[];activePoints=[];
     updatePreview();
     autoSaveRoads();
     showToast('🗑️ 画布已清空，请在网格上开始画路');
    }
   };

   // 导出道路坐标 JSON
   document.getElementById('ed-export').onclick=()=>{
    const jsonStr=JSON.stringify(roads,null,1);
    if(window.showExportModal) window.showExportModal('📋 道路路网数据导出 (' + roads.length + ' 段)', jsonStr);
    else prompt('当前绘制路网 JSON 数据：', jsonStr);
   };

   // 保存并实时生成 3D 沥青/白板路网
   document.getElementById('ed-save').onclick=()=>{
    showToast('🎉 3D 路网已实时更新！共生成 '+roads.length+' 段道路');
    toggleEditor();
   };

   document.getElementById('ed-close-btn').onclick=toggleEditor;
  }

  function toggleEditor(){
   if(!isEditing){
    window.CampusScene?.closeMore();
    if(window.BuildingEditor?.isEditing())window.BuildingEditor.toggleEditor();
    window.RoutePlanner?.suspend();
    previousGroundMode=window.getGroundMode?window.getGroundMode():'schematic';
    if(window.CampusScene?.stopMotion)window.CampusScene.stopMotion();
   }else{
    autoSaveRoads();
    if(window.rebuildCampusRoads)window.rebuildCampusRoads(roads);
    if(window.setGroundMode)window.setGroundMode(previousGroundMode);
    window.RoutePlanner?.refresh();
   }
   isEditing=!isEditing;
   drawingPointers.clear();gesturePaused=false;gestureSnapshot=null;isDragging=false;
   const hud=document.getElementById('road-editor-hud');
   const btn=document.getElementById('road-editor-btn');
   if(hud)hud.style.display=isEditing?'block':'none';
   if(btn){
    btn.classList.toggle('active',isEditing);
    btn.textContent=isEditing?'退出':'画路';
   }
   if(editorGroup)editorGroup.visible=isEditing;

   // 编辑模式下隐藏周围可能遮挡的搜索栏、标签和底卡
   const toHide=['.top','.filters','.badge','.card','#labels','.compass','.hint'];
   toHide.forEach(sel=>{
    const el=document.querySelector(sel);
    if(el)el.style.display=isEditing?'none':'';
   });

   if(isEditing){
    loadInitialRoads();
    updatePreview();
    if(window.setGroundMode)window.setGroundMode('aerial');
    if(window.resetCameraTop)window.resetCameraTop();
    showToast('选择绘制方式开始画路；收起面板可获得更大视野。');
   }else{
    if(markerMesh)markerMesh.visible=false;
    activePoints=[];
   }
  }

  root.RoadEditor={
   init,
   toggleEditor,
   isEditing:()=>isEditing,
   getMode:()=>drawMode,
   isGesturePaused:()=>gesturePaused,
   clearRoads:()=>{recordHistory();roads=[];activePoints=[];updatePreview();autoSaveRoads();},
   getRoads:()=>roads,
   resetDefaults:resetDefaultRoads,
   replaceRoads:value=>{recordHistory();roads=JSON.parse(JSON.stringify(value));activePoints=[];updatePreview();autoSaveRoads();},
   undo:()=>undoRedo(),redo:()=>undoRedo(true),
   autoSave:autoSaveRoads
  };
 }

 if(typeof module!=='undefined')module.exports=createRoadEditor;
 else createRoadEditor();
})(typeof window!=='undefined'?window:globalThis);
