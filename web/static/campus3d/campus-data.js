(function(root){
const buildings=[];
function add(id,name,x,z,w,d,floors,category,shape='court',extra={}){
 buildings.push({id,name,x,z,w,d,floors,category,shape,...extra});
}
add('teach_1','教学楼1',250,251,39,36,5,'教学');
add('teach_2','教学楼2',250,303,39,34,5,'教学');
add('teach_3','教学楼3',197,251,38,36,5,'教学');
add('teach_4','教学楼4',197,303,38,34,5,'教学');
add('lab_1','实验楼1',227,43,36,34,5,'教学');
add('lab_2','实验楼2',272,43,36,34,5,'教学');
add('admin_2','综合楼2',227,110,36,34,5,'教学');
add('admin_1','综合楼1',263,110,36,34,5,'教学');
add('art_museum','美术馆',227,76,22,18,3,'文体','solid',{info:'楼层数待确认 · 高度暂按照片估算'});
add('computer_center','计算机实验室',272,77,22,18,3,'教学','solid',{info:'楼层数待确认 · 高度暂按照片估算'});
add('library','图书馆',111,162,28,62,4,'文体','library',{basements:1,info:'共5层：地下1层、地上4层'});
add('gym','体育馆',126,74,26,57,3,'文体','gym');
add('canteen_main','食堂',110,283,30,44,3,'生活','solid');
add('theater_market','超市 / 小剧场',144,291,22,58,2,'生活','solid',{info:'1楼：超市 · 2楼：小剧场'});
add('small_dorm','小宿舍',89,222,20,26,3,'住宿','solid');
[[85,248],[85,288],[41,288],[41,248],[41,204],[41,165],[85,122],[41,122],[85,78],[41,78]].forEach((p,i)=>add('dorm_'+(i+1),(i+1)+'号宿舍',p[0],p[1],28,29,6,'住宿','court'));
add('south_gate','正大门',294.5,124,24,6,2,'教学','gate',{info:'晴川标志性古典正门牌楼 · 汉白玉校名大门'});
const defaultTransforms={"south_gate":{"dx":0,"dz":0,"rot":-75},"driving_school":{"dx":2,"dz":9,"rot":0},"gym_plaza":{"dx":3,"dz":8,"rot":5},"gym":{"dx":5,"dz":11,"rot":0},"volleyball_courts":{"dx":0,"dz":9,"rot":0},"canteen_main":{"dx":0,"dz":8,"rot":0},"theater_market":{"dx":4,"dz":7,"rot":0},"badminton_courts":{"dx":5,"dz":6,"rot":0},"dorm_2":{"dx":5,"dz":-1,"rot":0},"dorm_1":{"dx":5,"dz":-3,"rot":0},"small_dorm":{"dx":3,"dz":-3,"rot":0},"basketball_north":{"dx":-3,"dz":3,"rot":5},"dorm_6":{"dx":2,"dz":-4,"rot":0},"dorm_5":{"dx":0,"dz":-3,"rot":5},"dorm_3":{"dx":3,"dz":-3,"rot":0},"teach_4":{"dx":0,"dz":6,"rot":0},"teach_2":{"dx":0,"dz":5,"rot":0},"teach_1":{"dx":5,"dz":0,"rot":0},"teach_3":{"dx":3,"dz":4,"rot":0},"lake":{"dx":3,"dz":4,"rot":0},"dorm_9":{"dx":3,"dz":-2,"rot":0},"stadium":{"dx":2,"dz":-3,"rot":0},"dorm_7":{"dx":2,"dz":-6,"rot":5},"dorm_8":{"dx":2,"dz":-4,"rot":0},"dorm_10":{"dx":1,"dz":-2,"rot":0},"snack_street":{"dx":0,"dz":-2,"rot":-5},"lab_1":{"dx":-6,"dz":-6,"rot":5},"art_museum":{"dx":-3,"dz":-2,"rot":0},"admin_2":{"dx":-2,"dz":0,"rot":0},"lab_2":{"dx":2,"dz":-4,"rot":0},"computer_center":{"dx":1,"dz":0,"rot":0},"admin_1":{"dx":1,"dz":1,"rot":0}};
const data={buildings,defaultTransforms};
if(typeof module!=='undefined')module.exports=data;else root.CampusData=data;
})(typeof window!=='undefined'?window:globalThis);
