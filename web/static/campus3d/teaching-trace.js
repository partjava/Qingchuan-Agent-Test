/* User's green-line drawing, resized reference 942 x 2048.
 * All four buildings and links share ONE transform; their relative silhouette
 * is never squeezed independently into the old four rectangular placements.
 * Roof outlines are traced; height of connecting corridors remains estimated. */
(function(root){
const shapes={
 teach_1:{outer:[[370,845],[660,756],[756,1155],[626,1198],[486,1230],[462,1173],[680,1105],[649,1027],[562,1056],[490,1055],[434,1025]],holes:[[[440,884],[590,848],[609,908],[520,934],[545,1023],[483,1037]]],
 roofWings:[[[370,845],[660,756],[590,848],[440,884]],[[370,845],[440,884],[490,1055],[434,1025]],[[660,756],[700,947],[649,1027],[590,848]],[[700,947],[756,1155],[680,1105],[649,1027]],[[520,934],[609,908],[649,1027],[562,1056]],[[462,1173],[680,1105],[756,1155],[626,1198],[486,1230]]],
 links:[{outline:[[571,1205],[626,1198],[680,1335],[614,1354]],height:8},{outline:[[375,1038],[434,1025],[449,1069],[387,1087]],height:8}]},
 teach_3:{outer:[[48,916],[334,848],[379,1035],[109,1139]],holes:[[[137,972],[279,939],[300,1003],[157,1040]]]},
 teach_4:{outer:[[213,1343],[490,1340],[495,1580],[195,1568]],holes:[[[298,1429],[440,1427],[438,1500],[283,1500]]],links:[{outline:[[490,1340],[620,1338],[622,1406],[491,1418]],height:8}]},
 teach_2:{outer:[[490,1350],[817,1313],[866,1534],[568,1585],[551,1407],[491,1418]],holes:[[[619,1425],[764,1400],[779,1481],[626,1509]]],
 roofWings:[[[490,1350],[817,1313],[764,1400],[619,1425],[551,1407],[491,1418]],[[817,1313],[866,1534],[779,1481],[764,1400]],[[866,1534],[568,1585],[626,1509],[779,1481]],[[568,1585],[551,1407],[619,1425],[626,1509]]]}
};
for(const shape of Object.values(shapes)){
 if(!shape.roofWings){const o=shape.outer,c=shape.holes[0];shape.roofWings=o.map((p,i)=>[p,o[(i+1)%4],c[(i+1)%4],c[i]]);}
 shape.links=shape.links||[];
}
const trace={reference:{width:942,height:2048,source:'User green-line teaching-area annotation, 2026-10-04'},shapes,world:p=>[224+(p[0]-48)/9.6,174+(p[1]-756)/9.6]};
trace.apply=function(data,models){for(const [id,shape]of Object.entries(shapes)){
 const b=data.buildings.find(b=>b.id===id),m=models[id];
 const points=shape.outer.map(trace.world),xs=points.map(p=>p[0]),zs=points.map(p=>p[1]);
 b.x=(Math.min(...xs)+Math.max(...xs))/2;b.z=(Math.min(...zs)+Math.max(...zs))/2;
 const local=p=>{const q=trace.world(p);return [q[0]-b.x,q[1]-b.z];};
 m.outer=shape.outer.map(local);m.holes=shape.holes.map(loop=>loop.map(local));m.roofWings=shape.roofWings.map(loop=>loop.map(local));
 m.links=shape.links.map(link=>({outline:link.outline.map(local),height:link.height}));
 m.roof='traced';m.infill=[];m.annex=[];m.corners=[];m.source='User-marked teaching-area screenshot';
}};
if(typeof module!=='undefined')module.exports=trace;else {root.TeachingTrace=trace;trace.apply(root.CampusData,root.CampusFootprints);}
})(typeof window!=='undefined'?window:globalThis);
