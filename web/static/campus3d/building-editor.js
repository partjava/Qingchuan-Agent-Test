
  function showExportModal(title, jsonStr){
   if(window.CampusNativeBridge && typeof window.CampusNativeBridge.copyToClipboard === 'function'){
    window.CampusNativeBridge.copyToClipboard(jsonStr);
   }
   let modal = document.getElementById('export-modal');
   if(!modal){
    modal = document.createElement('div');
    modal.id = 'export-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.65);backdrop-filter:blur(5px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:16px;pointer-events:auto;';
    modal.innerHTML = `
     <div style="background:white;border-radius:14px;max-width:92%;width:420px;max-height:85vh;display:flex;flex-direction:column;box-shadow:0 12px 32px rgba(0,0,0,0.3);overflow:hidden;">
       <div style="display:flex;align-items:center;justify-content:between;padding:12px 16px;background:#f5f7f6;border-bottom:1px solid #e1e7e4;">
         <span id="export-modal-title" style="font-weight:bold;font-size:14px;color:#1e4d3c;flex:1;">📋 数据导出</span>
         <button id="export-modal-close" style="background:#eee;border:0;border-radius:50%;width:26px;height:26px;cursor:pointer;font-weight:bold;color:#666;">✕</button>
       </div>
       <div style="padding:14px 16px;display:flex;flex-direction:column;gap:10px;flex:1;overflow:hidden;">
         <span style="font-size:12px;color:#456657;line-height:1.4;">✅ 已为您自动复制到剪贴板！<br>若复制未成功，您也可长按下方文本框全选复制：</span>
         <textarea id="export-modal-area" style="width:100%;height:200px;box-sizing:border-box;font-family:monospace;font-size:11px;padding:8px;border:1px solid #ccd6d0;border-radius:8px;resize:none;background:#fafafa;" readonly></textarea>
         <button id="export-modal-copy" style="padding:10px;background:#215e48;color:white;font-weight:bold;border:0;border-radius:8px;cursor:pointer;font-size:13px;">📋 点击再次复制到剪贴板</button>
       </div>
     </div>
    `;
    document.body.appendChild(modal);
    document.getElementById('export-modal-close').onclick = () => { modal.style.display = 'none'; };
    document.getElementById('export-modal-copy').onclick = () => {
     const ta = document.getElementById('export-modal-area');
     ta.select();
     if(window.CampusNativeBridge && typeof window.CampusNativeBridge.copyToClipboard === 'function'){
      window.CampusNativeBridge.copyToClipboard(ta.value);
     }else{
      document.execCommand('copy');
      alert('已复制到剪贴板！');
     }
    };
   }
   document.getElementById('export-modal-title').textContent = title;
   const ta = document.getElementById('export-modal-area');
   ta.value = jsonStr;
   modal.style.display = 'flex';
   ta.select();
  }
  window.showExportModal = showExportModal;
/**
 * 晴川 3D 校园 · 建筑与场地全要素位移与旋转微调器 (Building & Venue Transform Editor)
 * 支持：
 * 1. 全要素选取：支持所有建筑、驾校、田径足球场、篮球场、羽毛球场、排球场、小吃街、情缘湖等
 * 2. 上下左右平移：支持 0.5m / 1m / 3m 步长精细对齐底图
 * 3. 角度旋转：支持 1° / 5° / 15° 顺逆时针绕中心旋转
 * 4. 实时高亮反馈与标签同步
 * 5. 本地持久化保存 (localStorage) 与 一键代码导出
 */
(function(root){
 function createBuildingEditor(){
  let isEditing=false;
  let isCollapsed=false;
  let selectedId=null;
  let stepMove=1.0; // 米
  let stepRot=5;    // 度 (DEG)
  let defaultTransforms={};
  let transforms={}; // { [id]: { dx: 0, dz: 0, rot: 0 } }
  let undoHistory=[],redoHistory=[],previousGroundMode='schematic';
  let baseTransforms={}; // { [id]: { x, z, rot, cx, cz, isRegion } }

  let sceneRef=null, cameraRef=null, rendererRef=null;
  let groupsRef=null, labelsRef=null, placesRef=[], selectFn=null;
  let highlightMarker=null;

  function init({scene, camera, renderer, groups, labels, CampusData, select, allPlaces}){
   sceneRef=scene; cameraRef=camera; rendererRef=renderer;
   groupsRef=groups; labelsRef=labels; selectFn=select;
   placesRef=allPlaces || (CampusData ? [...CampusData.buildings, ...(CampusData.regions||[])] : []);

   // 记录所有建筑与运动场地的初始基准位置与旋转
   for(const b of placesRef){
    const g=groupsRef.get(b.id);
    if(g){
     baseTransforms[b.id]={
      x: g.position.x,
      z: g.position.z,
      rot: g.rotation.y,
      cx: b.x || 0,
      cz: b.z || 0,
      isRegion: Boolean(b.region)
     };
    }
   }

   // 选中光圈指示器
   const ringGeo=new THREE.RingGeometry(2, 2.8, 32);
   ringGeo.rotateX(-Math.PI/2);
   const ringMat=new THREE.MeshBasicMaterial({color:'#ffc83b', side:THREE.DoubleSide, transparent:true, opacity:.85});
   highlightMarker=new THREE.Mesh(ringGeo, ringMat);
   highlightMarker.position.y=0.45;
   highlightMarker.visible=false;
   scene.add(highlightMarker);

   defaultTransforms = (CampusData && CampusData.defaultTransforms) ? JSON.parse(JSON.stringify(CampusData.defaultTransforms)) : {};
   loadTransforms();
   applyAllTransforms();
   createUI();
  }

  function loadTransforms(){
   transforms = JSON.parse(JSON.stringify(defaultTransforms));
   if(window.CampusNativeBridge && typeof window.CampusNativeBridge.loadConfig === 'function'){
    try{
     const nativeStr = window.CampusNativeBridge.loadConfig('custom_building_transforms');
     if(nativeStr){ Object.assign(transforms, JSON.parse(nativeStr)); return; }
    }catch(e){}
   }
   try{
    if(typeof localStorage !== 'undefined' && localStorage){
     const stored = localStorage.getItem('custom_building_transforms');
     if(stored) Object.assign(transforms, JSON.parse(stored));
    }
   }catch(e){}
  }

  function applyTransform(id){
   const g=groupsRef.get(id);
   const b=placesRef.find(item=>item.id===id);
   const base=baseTransforms[id];
   if(!g||!b||!base)return;

   const t=transforms[id]||{dx:0, dz:0, rot:0};
   const rad=((t.rot||0)*Math.PI/180);

   if(base.isRegion){
    // 场地（驾校、篮球场、足球场、羽毛球场等）：绕自身中心 (cx, cz) 旋转与平移
    const cx=base.cx||0, cz=base.cz||0;
    const cos=Math.cos(rad), sin=Math.sin(rad);
    g.rotation.y=base.rot+rad;
    g.position.x=base.x+(t.dx||0)+cx-(cx*cos+cz*sin);
    g.position.z=base.z+(t.dz||0)+cz-(-cx*sin+cz*cos);

    b.x=base.cx+(t.dx||0);
    b.z=base.cz+(t.dz||0);
   }else{
    // 普通建筑模型：Group 原点即为自身中心 (b.x, b.z)
    g.position.x=base.x+(t.dx||0);
    g.position.z=base.z+(t.dz||0);
    g.rotation.y=base.rot+rad;

    b.x=g.position.x;
    b.z=g.position.z;
   }

   if(labelsRef){
    const lbl=labelsRef.find(item=>item.b.id===id);
    if(lbl&&lbl.s&&lbl.s.position){
     lbl.s.position.x=b.x;
     lbl.s.position.z=b.z;
    }
   }

   if(highlightMarker&&selectedId===id){
    highlightMarker.position.x=b.x;
    highlightMarker.position.z=b.z;
   }
  }

  function applyAllTransforms(){
   for(const id of Object.keys(baseTransforms)){
    applyTransform(id);
   }
  }

  function selectBuilding(id){
   if(!id||!baseTransforms[id])return;
   selectedId=id;

   // 恢复所有物体材质原色，高亮选中的物体
   for(const [gId, g] of groupsRef){
    g.traverse(m=>{
     if(m.isMesh&&m.material&&m.material.emissive){
      m.material.emissive.set(gId===id?'#554400':'#000000');
     }
    });
   }

   // 移动光圈到物体底部
   const b=placesRef.find(item=>item.id===id);
   if(b&&highlightMarker){
    highlightMarker.position.x=b.x;
    highlightMarker.position.z=b.z;
    highlightMarker.visible=true;
   }

   // 同步下拉框
   const sel=document.getElementById('bld-select');
   if(sel&&sel.value!==id)sel.value=id;

   updateReadout();
   showToast('已选中：'+(b?b.name:id)+'，可通过下方按钮调整位置与旋转');
  }

  function nudge(dx, dz, drot){
   if(!selectedId)return;
   rememberEdit();
   if(!transforms[selectedId])transforms[selectedId] = defaultTransforms[selectedId] ? {...defaultTransforms[selectedId]} : {dx:0, dz:0, rot:0};
   const t=transforms[selectedId];
   t.dx=Math.round((t.dx+dx)*10)/10;
   t.dz=Math.round((t.dz+dz)*10)/10;
   t.rot=Math.round((t.rot+drot)*10)/10;
   applyTransform(selectedId);
   updateReadout();
   autoSaveTransforms();
  }

  function resetCurrent(){
   if(!selectedId)return;
   rememberEdit();
   transforms[selectedId]=defaultTransforms[selectedId] ? {...defaultTransforms[selectedId]} : {dx:0, dz:0, rot:0};
   applyTransform(selectedId);
   updateReadout();
   autoSaveTransforms();
   showToast('已复位该对象至默认位置');
  }

  function resetAll(){
   if(confirm('确定要将所有建筑和场地恢复至已校准的默认布局吗？')){
    rememberEdit();
    transforms=JSON.parse(JSON.stringify(defaultTransforms));
    applyAllTransforms();
    updateReadout();
    autoSaveTransforms();
    showToast('已全部恢复默认位置');
   }
  }

  function autoSaveTransforms(){

   if(window.CampusNativeBridge && typeof window.CampusNativeBridge.saveConfig === 'function'){
    try{ window.CampusNativeBridge.saveConfig('custom_building_transforms', JSON.stringify(transforms)); }catch(e){}
   }
   try{
    if(typeof localStorage !== 'undefined' && localStorage){
     localStorage.setItem('custom_building_transforms', JSON.stringify(transforms));
    }
   }catch(e){}
   window.CampusDefaults?.markSaved('buildings');
  }

  function rememberEdit(){
   undoHistory.push(JSON.parse(JSON.stringify(transforms)));
   if(undoHistory.length>100)undoHistory.shift();
   redoHistory=[];
   updateHistoryButtons();
  }
  function restoreHistory(from,to){
   if(!from.length)return;
   to.push(JSON.parse(JSON.stringify(transforms)));
   transforms=from.pop();
   applyAllTransforms();
   updateReadout();
   autoSaveTransforms();
   updateHistoryButtons();
  }
  function undo(){restoreHistory(undoHistory,redoHistory);}
  function redo(){restoreHistory(redoHistory,undoHistory);}
  function updateHistoryButtons(){
   for(const [id,history] of [['bld-undo',undoHistory],['bld-redo',redoHistory]]){
    const btn=document.getElementById(id);
    if(btn){btn.disabled=!history.length;btn.style.opacity=history.length?'1':'.45';}
   }
  }

  function saveTransforms(){
   autoSaveTransforms();
   showToast('🎉 位置与角度已成功保存到手机硬盘！');
  }

  // Keep persisted transforms in original coordinates; expose edits relative to defaults.
  function relativeTransform(id){
   const t=transforms[id]||defaultTransforms[id]||{};
   const baseline=defaultTransforms[id]||{};
   const delta=key=>Math.round(((t[key]||0)-(baseline[key]||0))*10)/10;
   return {dx:delta('dx'),dz:delta('dz'),rot:delta('rot')};
  }

  function exportTransformsCode(){
   const active={};
   const ids=new Set([...Object.keys(defaultTransforms),...Object.keys(transforms)]);
   for(const id of ids)active[id]=relativeTransform(id);
   const json=JSON.stringify(active, null, 2);
   if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(json).catch(()=>{});
   }
   prompt('相对当前默认布局的偏移 JSON（全为 0 表示未调整；可发给我更新默认布局）：', json);
  }

  function updateReadout(){
   const info=document.getElementById('bld-readout');
   const t=relativeTransform(selectedId);
   if(info){
    const b=placesRef.find(item=>item.id===selectedId);
    const name=b?b.name:'未选择';
    info.innerHTML=`<strong>${name}</strong>（相对默认）: X偏: <span style="color:#d46238;">${t.dx>=0?'+':''}${t.dx}m</span>, Z偏: <span style="color:#d46238;">${t.dz>=0?'+':''}${t.dz}m</span>, 角度: <span style="color:#215e48;">${t.rot>=0?'+':''}${t.rot}°</span>`;
   }
  }

  function showToast(msg){
   const el=document.getElementById('bld-toast');
   if(el){
    el.textContent=msg;
    el.style.opacity='1';
    clearTimeout(el._t);
    el._t=setTimeout(()=>{el.style.opacity='0';},2500);
   }
  }

  function createUI(){
   // 1. 在右侧工具栏添加【移楼】按钮
   const tools=document.getElementById('tools-scroll')||document.getElementById('tools')||document.getElementById('more-tools')||document.querySelector('.tools');
   if(tools&&!document.getElementById('building-editor-btn')){
    const btn=document.createElement('button');
    btn.id='building-editor-btn';
    btn.textContent='移楼';
    btn.title='开启建筑与场地位置/旋转微调面板';
    btn.onclick=toggleEditor;
    tools.appendChild(btn);
    if(typeof window!=="undefined"&&window.restoreToolsScroll)window.restoreToolsScroll();
   }

   // 2. 创建建筑变换悬浮操作面板
   const hud=document.createElement('div');
   hud.id='building-editor-hud';
   hud.style.cssText='display:none;position:fixed;inset:0;pointer-events:none;z-index:9;font-family:system-ui,-apple-system,sans-serif;';
   hud.innerHTML=`
    <section id="bld-panel-full" class="editor-panel" aria-label="建筑位置调整">
      <header class="editor-header">
        <div><p class="editor-kicker">CAMPUS STUDIO</p><div class="editor-title">调整建筑</div></div>
        <div class="editor-header-actions"><button id="bld-collapse-btn" class="editor-icon" aria-label="收起调整面板">收起</button><button id="bld-close-btn" class="editor-done">完成</button></div>
      </header>
      <label class="editor-select">调整对象<select id="bld-select" aria-label="选择建筑或场地"><option value="">点击地图上的建筑或选择对象</option></select></label>
      <div id="bld-readout" class="editor-readout">选择建筑，开始调整位置与方向</div>
      <div class="editor-motion">
        <div class="editor-dpad">
          <button id="bld-up" aria-label="向北移动" title="向北移动">↑</button>
          <button id="bld-left" aria-label="向西移动" title="向西移动">←</button>
          <button id="bld-right" aria-label="向东移动" title="向东移动">→</button>
          <button id="bld-down" aria-label="向南移动" title="向南移动">↓</button><span>平移</span>
        </div>
        <div class="editor-adjustments">
          <div class="editor-row"><button id="bld-rot-ccw">↶ 左旋</button><button id="bld-rot-cw">右旋 ↷</button></div>
          <div class="editor-row"><span class="editor-row-label">距离</span><button id="bld-step-05">0.5m</button><button id="bld-step-1" style="background:#215e48;color:white">1m</button><button id="bld-step-3">3m</button></div>
          <div class="editor-row"><span class="editor-row-label">角度</span><button id="bld-rot-1">1°</button><button id="bld-rot-5" style="background:#215e48;color:white">5°</button><button id="bld-rot-15">15°</button></div>
        </div>
      </div>
      <div class="editor-history"><button id="bld-undo">↶ 撤销</button><button id="bld-redo">重做 ↷</button></div>
      <div class="editor-footer"><button id="bld-reset-cur">复位当前</button><button id="bld-reset-all" class="editor-danger">全部复位</button><button id="bld-export">导出布局</button><button id="bld-save" class="editor-primary">保存</button></div>
      <p class="editor-caption">拖动地图调整视野 · 点击建筑切换对象 · 修改自动保存</p>
    </section>
    <div id="bld-panel-mini" class="editor-mini" style="display:none"><strong>调整建筑</strong><span id="bld-mini-name">点击建筑选择对象</span><button id="bld-expand-btn">展开 ↑</button></div>
    <div id="bld-toast" class="editor-toast">点击建筑或场地开始调整</div>
   `;
   document.body.appendChild(hud);

   // 分类填充全要素下拉框
   const sel=document.getElementById('bld-select');
   if(sel&&placesRef.length>0){
    sel.innerHTML='<option value="">-- 点击物体或下拉选择 --</option>';
    const catMap={
     '教学':'🏫 教学与综合办公',
     '住宿':'🛏️ 宿舍生活公寓',
     '生活':'🏪 生活服务与驾校场地',
     '文体':'⚽ 运动场地与园林景观'
    };
    ['教学','住宿','生活','文体'].forEach(cat=>{
     const list=placesRef.filter(p=>p.category===cat);
     if(list.length>0){
      const grp=document.createElement('optgroup');
      grp.label=catMap[cat]||cat;
      list.forEach(b=>{
       const opt=document.createElement('option');
       opt.value=b.id;
       opt.textContent=b.name;
       grp.appendChild(opt);
      });
      sel.appendChild(grp);
     }
    });

    sel.onchange=()=>{
     if(sel.value)selectBuilding(sel.value);
    };
   }

   // 折叠与展开
   const panelFull=document.getElementById('bld-panel-full');
   const panelMini=document.getElementById('bld-panel-mini');
   const setCollapse=(collapsed)=>{
    isCollapsed=collapsed;
    panelFull.style.display=collapsed?'none':'flex';
    panelMini.style.display=collapsed?'flex':'none';
    const miniName=document.getElementById('bld-mini-name');
    if(miniName){
     const b=placesRef.find(item=>item.id===selectedId);
     miniName.textContent=b?b.name:'未选择';
    }
   };
   document.getElementById('bld-collapse-btn').onclick=()=>setCollapse(true);
   document.getElementById('bld-expand-btn').onclick=()=>setCollapse(false);

   // 平移按钮绑定 (北=-Z, 南=+Z, 西=-X, 东=+X)
   document.getElementById('bld-up').onclick=()=>nudge(0, -stepMove, 0);
   document.getElementById('bld-down').onclick=()=>nudge(0, stepMove, 0);
   document.getElementById('bld-left').onclick=()=>nudge(-stepMove, 0, 0);
   document.getElementById('bld-right').onclick=()=>nudge(stepMove, 0, 0);

   // 旋转按钮绑定
   document.getElementById('bld-rot-ccw').onclick=()=>nudge(0, 0, -stepRot);
   document.getElementById('bld-rot-cw').onclick=()=>nudge(0, 0, stepRot);

   // 步长切换
   const setStepMove=(s, elId)=>{
    stepMove=s;
    ['bld-step-05','bld-step-1','bld-step-3'].forEach(id=>{
     const el=document.getElementById(id);
     el.style.background=(id===elId)?'#215e48':'#e5ece8';
     el.style.color=(id===elId)?'white':'#284d40';
    });
   };
   document.getElementById('bld-step-05').onclick=()=>setStepMove(0.5, 'bld-step-05');
   document.getElementById('bld-step-1').onclick=()=>setStepMove(1.0, 'bld-step-1');
   document.getElementById('bld-step-3').onclick=()=>setStepMove(3.0, 'bld-step-3');

   // 旋转步长切换
   const setStepRot=(r, elId)=>{
    stepRot=r;
    ['bld-rot-1','bld-rot-5','bld-rot-15'].forEach(id=>{
     const el=document.getElementById(id);
     el.style.background=(id===elId)?'#215e48':'#e5ece8';
     el.style.color=(id===elId)?'white':'#284d40';
    });
   };
   document.getElementById('bld-rot-1').onclick=()=>setStepRot(1, 'bld-rot-1');
   document.getElementById('bld-rot-5').onclick=()=>setStepRot(5, 'bld-rot-5');
   document.getElementById('bld-rot-15').onclick=()=>setStepRot(15, 'bld-rot-15');

   // 控制操作
   document.getElementById('bld-reset-cur').onclick=resetCurrent;
   document.getElementById('bld-reset-all').onclick=resetAll;
   document.getElementById('bld-export').onclick=exportTransformsCode;
   document.getElementById('bld-save').onclick=saveTransforms;
   document.getElementById('bld-close-btn').onclick=toggleEditor;
   document.getElementById('bld-undo').onclick=undo;
   document.getElementById('bld-redo').onclick=redo;
   updateHistoryButtons();
  }

  function toggleEditor(){
   if(!isEditing){
    window.CampusScene?.closeMore();
    if(window.RoadEditor?.isEditing())window.RoadEditor.toggleEditor();
    window.RoutePlanner?.suspend();
    previousGroundMode=window.getGroundMode?window.getGroundMode():'schematic';
    if(window.CampusScene?.stopMotion)window.CampusScene.stopMotion();
   }else{
    autoSaveTransforms();
    if(window.setGroundMode)window.setGroundMode(previousGroundMode);
    window.RoutePlanner?.refresh();
   }
   isEditing=!isEditing;
   const hud=document.getElementById('building-editor-hud');
   const btn=document.getElementById('building-editor-btn');
   if(hud)hud.style.display=isEditing?'block':'none';
   if(btn){
    btn.classList.toggle('active', isEditing);
    btn.textContent=isEditing?'完成':'移楼';
   }
   if(highlightMarker)highlightMarker.visible=isEditing&&Boolean(selectedId);

   // 隐藏干扰 UI
   const toHide=['.top','.filters','.badge','.card','#labels','.hint'];
   toHide.forEach(sel=>{
    const el=document.querySelector(sel);
    if(el)el.style.display=isEditing?'none':'';
   });

   if(isEditing){
    // 进入移楼模式：自动切换实景底图，方便直接对着航拍图微调
    if(window.setGroundMode)window.setGroundMode('aerial');
    if(!selectedId&&placesRef.length>0){
     selectBuilding(placesRef[0].id);
    }
    showToast('点击建筑选择对象，使用方向键微调；拖动地图可调整视野。');
   }else{
    // 退出编辑模式：恢复所有物体默认颜色
    for(const [gId, g] of groupsRef){
     g.traverse(m=>{
      if(m.isMesh&&m.material&&m.material.emissive){
       m.material.emissive.set('#000000');
      }
     });
    }
   }
  }

  root.BuildingEditor={
   init,
   toggleEditor,
   isEditing:()=>isEditing,
   selectBuilding,
   nudge,
   resetDefaults:()=>{rememberEdit();transforms=JSON.parse(JSON.stringify(defaultTransforms));applyAllTransforms();updateReadout();autoSaveTransforms();},
   replaceTransforms:value=>{rememberEdit();transforms=JSON.parse(JSON.stringify(value));applyAllTransforms();updateReadout();autoSaveTransforms();},
   getTransforms:()=>transforms,
   applyAllTransforms,
   autoSave:autoSaveTransforms,
   undo,
   redo
  };
 }

 if(typeof module!=='undefined')module.exports=createBuildingEditor;
 else createBuildingEditor();
})(typeof window!=='undefined'?window:globalThis);
