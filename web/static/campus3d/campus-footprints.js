/* Manually interpreted from map_assets. Local x/z coordinates are estimated,
 * not surveyed. Every building carries its own silhouette and photo reference. */
(function(root){
const models={
 teach_1:{source:'每个方位/教学楼一（5楼）.png',outer:[[-22,-22],[20,-21],[23,23],[-21,22]],holes:[[[-12,-13],[11,-13],[13,12],[-12,13]]],infill:[{x:0,z:8,w:14,d:10,h:4,roof:'flat'}],corners:[[-20,-17],[20,19]],roof:'ring'},
 teach_2:{source:'每个方位/教学楼二（5楼）.png',outer:[[-18,-23],[18,-24],[20,22],[-19,23]],holes:[[[-10,-15],[9,-15],[10,15],[-10,15]]],infill:[],corners:[[-15,-19]],roof:'ring'},
 teach_3:{source:'每个方位/教学楼三（5楼）.png',outer:[[-17,-22],[17,-20],[19,22],[-18,22]],holes:[[[-9,-14],[9,-13],[10,13],[-10,13]]],infill:[],corners:[[-14,18]],roof:'ring'},
 teach_4:{source:'每个方位/教学楼四（5楼）.png',outer:[[-18,-22],[18,-22],[18,23],[-19,21]],holes:[[[-10,-14],[10,-14],[10,14],[-10,13]]],infill:[],corners:[[-15,-18]],roof:'ring'},
 lab_1:{source:'每个方位/实验楼1（5楼）.png',outer:[[-17,-21],[18,-20],[17,20],[-18,22]],holes:[[[-9,-12],[10,-12],[9,12],[-10,13]]],infill:[],corners:[],roof:'ring'},
 lab_2:{source:'每个方位/实验楼二（5楼）.png',outer:[[-17,-21],[18,-21],[19,23],[-18,23]],holes:[[[-9,-13],[10,-13],[10,14],[-10,14]]],infill:[{x:1,z:13,w:12,d:9,h:5,roof:'flat'}],corners:[[15,-17]],roof:'ring'},
 admin_1:{source:'每个方位/综合楼一（5楼）.png',outer:[[-19,-23],[12,-21],[15,24],[-20,24]],holes:[[[-11,-14],[4,-13],[6,14],[-12,14]]],infill:[{x:-3,z:13,w:12,d:9,h:4,roof:'flat'}],annex:[{x:24,z:9,w:15,d:22,h:10,roof:'hip',connect:true}],corners:[],roof:'ring'},
 admin_2:{source:'每个方位/综合楼二（5楼）.png',outer:[[-18,-23],[16,-22],[20,22],[-17,23]],holes:[[[-9,-15],[8,-14],[11,14],[-9,14]]],infill:[],corners:[[15,18]],roof:'ring'},
 library:{source:'每个方位/图书馆.png',outer:[[-24,25],[-29,14],[-15,-16],[-6,-27],[24,-27],[27,-13],[1,-13],[-6,-3],[-15,21]],holes:[],infill:[],corners:[],roof:'terrace',glass:[0,1,2,6,7],terrace:true},
 gym:{source:'每个方位/体育馆.png',outer:[[-19,-28],[18,-28],[21,24],[14,29],[-16,29],[-22,23]],holes:[],infill:[],corners:[],roof:'arena'},
 canteen_main:{source:'每个方位/食堂（3楼）.png',outer:[[-18,-20],[18,-17],[16,21],[-19,18]],holes:[],infill:[],corners:[],roof:'canteen'},
 theater_market:{source:'每个方位/小剧场（2楼）、超市（1楼）.png',outer:[[-10,-29],[9,-29],[11,27],[-11,29]],holes:[],infill:[],corners:[],roof:'hall'},
 art_museum:{source:'每个方位/美术馆.png',outer:[[-11,-10],[10,-8],[12,10],[-10,10]],holes:[],infill:[],corners:[],roof:'hip'},
 computer_center:{source:'每个方位/计算机实验室.png',outer:[[-12,-11],[10,-9],[12,10],[-10,11]],holes:[],infill:[],corners:[],roof:'hip'},
 small_dorm:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-9,-14],[10,-14],[10,14],[-9,14]],holes:[],infill:[],corners:[],roof:'hip'},
 dorm_1:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-17,-19],[17,-18],[17,19],[8,19],[8,-9],[-8,-9],[-8,19],[-17,18]],holes:[],infill:[],corners:[],roof:'open'},
 dorm_2:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-17,-17],[17,-18],[18,17],[9,18],[9,-8],[-8,-8],[-8,18],[-17,18]],holes:[],infill:[],corners:[],roof:'open'},
 dorm_3:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-17,-18],[17,-18],[17,18],[-17,19]],holes:[[[-9,-10],[9,-10],[9,10],[-9,10]]],infill:[],corners:[],roof:'ring'},
 dorm_4:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-18,-19],[17,-18],[17,18],[-18,19]],holes:[[[-10,-10],[9,-10],[9,10],[-10,11]]],infill:[],corners:[],roof:'ring'},
 dorm_5:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-18,-18],[18,-19],[18,18],[-18,18]],holes:[[[-10,-10],[10,-11],[10,10],[-10,10]]],infill:[],corners:[],roof:'ring'},
 dorm_6:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-18,-19],[17,-18],[18,19],[-18,18]],holes:[[[-10,-10],[9,-9],[10,10],[-10,10]]],infill:[],corners:[],roof:'ring'},
 dorm_7:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-17,-18],[-8,-18],[-8,9],[8,9],[8,-18],[17,-18],[17,18],[-17,18]],holes:[],infill:[],corners:[],roof:'open'},
 dorm_8:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-17,-18],[-8,-18],[-8,9],[9,9],[9,-17],[17,-17],[17,18],[-17,18]],holes:[],infill:[],corners:[],roof:'open'},
 dorm_9:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-16,-19],[-7,-19],[-7,9],[8,9],[8,-19],[17,-18],[17,18],[-16,18]],holes:[],infill:[],corners:[],roof:'open'},
 dorm_10:{source:'宿舍楼(已标记name-总楼层).jpg',outer:[[-18,-18],[-8,-18],[-8,9],[9,9],[9,-18],[18,-18],[18,18],[-18,18]],holes:[],infill:[],corners:[],roof:'open'},
 south_gate:{source:'photos/south_gate.jpg',outer:[[-12,-3],[12,-3],[12,3],[-12,3]],holes:[],infill:[],corners:[],roof:'gate'}
};
for(const m of Object.values(models))m.annex=m.annex||[];
if(typeof module!=='undefined')module.exports=models;else root.CampusFootprints=models;
})(typeof window!=='undefined'?window:globalThis);
