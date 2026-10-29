(function(root){
function roofVertices(w,d,rise){return [-w/2,0,-d/2,w/2,0,-d/2,0,rise,-d/2,-w/2,0,d/2,w/2,0,d/2,0,rise,d/2];}
function chooseLabels(items){const accepted=[];for(const item of [...items].sort((a,b)=>b.priority-a.priority)){const r=item.rect;if(!accepted.some(a=>r[0]<a.rect[2]+6&&r[2]+6>a.rect[0]&&r[1]<a.rect[3]+4&&r[3]+4>a.rect[1]))accepted.push(item);}return accepted.map(a=>a.id);}
function createRenderer(THREE,width,height,pixelRatio){
 let renderer,compatible=false;
 try{renderer=new THREE.WebGLRenderer({antialias:true});}
 catch(e){
  // Some WebView/GPU combinations reject multisampled contexts. Retry on a
  // fresh renderer canvas without antialiasing; never reload or clear layout data.
  renderer=new THREE.WebGLRenderer({antialias:false,powerPreference:'default'});
  compatible=true;
 }
 compatible=compatible||!!(renderer.capabilities&&renderer.capabilities.isWebGL2===false);
 renderer.setPixelRatio(Math.min(Number.isFinite(pixelRatio)&&pixelRatio>0?pixelRatio:1,compatible?1:1.6));
 renderer.setSize(width,height);
 renderer.shadowMap.enabled=!compatible;
 renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 renderer.outputColorSpace=THREE.SRGBColorSpace;
 return renderer;
}
const api={roofVertices,chooseLabels,createRenderer};if(typeof module!=='undefined')module.exports=api;else root.SceneUtils=api;
})(typeof window!=='undefined'?window:globalThis);
