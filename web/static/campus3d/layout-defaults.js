/* Capture packaged defaults before device storage overrides the scene. */
(function(root){
 const clone=v=>JSON.parse(JSON.stringify(v));
 const roads=clone(root.CampusLayout?.roads||[]),transforms=clone(root.CampusData?.defaultTransforms||{});
 const signature=value=>{const text=JSON.stringify(value);let h=2166136261;for(let i=0;i<text.length;i++)h=Math.imul(h^text.charCodeAt(i),16777619);return (h>>>0).toString(16);};
 const versions={roads:signature(roads),buildings:signature(transforms)};
 function read(key){try{const value=root.CampusNativeBridge?.loadConfig?.(key);if(value)return JSON.parse(value);}catch(_){}try{const value=root.localStorage?.getItem(key);if(value!==null&&value!==undefined)return JSON.parse(value);}catch(_){}return null;}
 function write(key,value){const text=JSON.stringify(value);try{root.CampusNativeBridge?.saveConfig?.(key,text);}catch(_){}try{root.localStorage?.setItem(key,text);}catch(_){} }
 function status(){const savedRoads=read('custom_campus_roads'),savedBuildings=read('custom_building_transforms'),meta=read('campus_default_versions')||{};
  const customRoads=Array.isArray(savedRoads)&&signature(savedRoads)!==versions.roads;
  const customBuildings=savedBuildings&&typeof savedBuildings==='object'&&signature({...transforms,...savedBuildings})!==versions.buildings;
  return {custom:!!(customRoads||customBuildings),outdated:!!((customRoads&&meta.roads&&meta.roads!==versions.roads)||(customBuildings&&meta.buildings&&meta.buildings!==versions.buildings)),unversioned:!!((customRoads&&!meta.roads)||(customBuildings&&!meta.buildings)),backup:!!read('campus_layout_backup')};
 }
 function markSaved(type){const meta=read('campus_default_versions')||{};meta[type]=versions[type];write('campus_default_versions',meta);refresh();}
 function backup(){write('campus_layout_backup',{roads:clone(root.RoadEditor?.getRoads()||read('custom_campus_roads')||roads),transforms:clone(root.BuildingEditor?.getTransforms()||{...transforms,...read('custom_building_transforms')})});}
 function useDefaults(){if(!status().custom)return;backup();root.RoadEditor?.resetDefaults();root.BuildingEditor?.resetDefaults();root.rebuildCampusRoads?.(clone(roads));root.RoutePlanner?.refresh();refresh();}
 function restoreBackup(){const prior=read('campus_layout_backup');if(!prior)return;root.RoadEditor?.replaceRoads(prior.roads);root.BuildingEditor?.replaceTransforms(prior.transforms);root.rebuildCampusRoads?.(clone(prior.roads));root.RoutePlanner?.refresh();refresh();}
 function refresh(){const el=root.document?.getElementById('layout-status-button'),text=root.document?.getElementById('layout-status-text'),restore=root.document?.getElementById('layout-restore-backup');if(!el)return;const state=status();el.textContent=state.outdated?'默认已更新':state.custom?'自定义布局':'默认布局';el.classList?.toggle('active',state.custom);if(text)text.textContent=state.outdated?'项目默认布局已更新。当前使用设备保存的布局，你可以保留它，或切换到最新默认。':state.unversioned?'设备保存的布局与项目默认不同，旧数据没有版本记录。你可以保留它，或切换到最新默认。':state.custom?'正在使用设备保存的自定义布局。切换默认前会自动备份。':'正在使用项目最新默认布局。';if(restore)restore.hidden=!state.backup;const use=root.document?.getElementById('layout-use-default');if(use)use.disabled=!state.custom;}
 function mount(){const doc=root.document,tools=doc.getElementById('tools-scroll')||doc.getElementById('more-tools');if(!tools||doc.getElementById('layout-status-button'))return;
  const btn=doc.createElement('button');btn.id='layout-status-button';btn.textContent='默认布局';tools.appendChild(btn);
  const panel=doc.createElement('section');panel.id='layout-status-panel';panel.className='layout-status-panel';panel.hidden=true;panel.innerHTML='<header><strong>地图布局</strong><button id="layout-status-close" aria-label="关闭布局面板">×</button></header><p id="layout-status-text"></p><div><button id="layout-use-default">使用最新默认</button><button id="layout-restore-backup" hidden>恢复切换前布局</button></div><small>自定义修改不会被自动覆盖。</small>';doc.body.appendChild(panel);
  btn.onclick=()=>{refresh();panel.hidden=!panel.hidden;root.CampusScene?.closeMore();};doc.getElementById('layout-status-close').onclick=()=>panel.hidden=true;doc.getElementById('layout-use-default').onclick=useDefaults;doc.getElementById('layout-restore-backup').onclick=restoreBackup;refresh();
 }
 const api={roads,transforms,versions,read,status,markSaved,backup,useDefaults,restoreBackup,refresh,mount};if(typeof module!=='undefined')module.exports=api;else root.CampusDefaults=api;
})(typeof window!=='undefined'?window:globalThis);
