import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

(() => {
'use strict';
const T = 2.25, NX = 20, NZ = 14, WORLD_W = NX * T, WORLD_D = NZ * T;
const $ = id => document.getElementById(id);
const ui = {};
for (const id of ['world','resources','day','season','enemies','mission','log','estate','quest','questfill','selection','actions','toast','intro','start','loading','error','tour','tutorial','close-tour','cam-left','cam-home','cam-right','zoom-in','zoom-out','next-day']) ui[id] = $(id);
const itemDefs = {
 wheat:{label:'گندم',icon:'🌾',cost:{gold:16},days:2,yield:{food:34,gold:15},build:true},
 corn:{label:'ذرت',icon:'🌽',cost:{gold:26},days:3,yield:{food:52,gold:23},build:true},
 pumpkin:{label:'کدو',icon:'🎃',cost:{gold:35},days:4,yield:{food:68,gold:42},build:true},
 orchard:{label:'باغ میوه',icon:'🌳',cost:{gold:75,wood:30},build:true},
 barn:{label:'دامداری',icon:'🐄',cost:{gold:90,wood:40},build:true},
 mill:{label:'آسیاب',icon:'⚙️',cost:{gold:110,wood:55},build:true},
 tower:{label:'برج دفاع',icon:'🏰',cost:{gold:100,wood:65},build:true},
 market:{label:'بازارچه',icon:'🏪',cost:{gold:95,wood:35},build:true},
 harvest:{label:'برداشت',icon:'🧺'},
 train:{label:'سرباز',icon:'🛡️',cost:{gold:55,food:24}},
 attack:{label:'حمله',icon:'⚔️',cost:{army:4,food:24}},
 repair:{label:'تعمیر',icon:'🧱',cost:{gold:60,wood:45}},
 next:{label:'روز بعد',icon:'☀️'}
};
const factions=[{name:'خاندان آتش',color:0xcf6542,x:15,z:2,initial:220},{name:'خاندان آهن',color:0x6b7cae,x:16,z:7,initial:260},{name:'خاندان سایه',color:0x7c5c8f,x:15,z:12,initial:310}];
const assetList=['tree-oak','tree-detailed','tree-default','tree-pine','tree-fall','plant-bush','flower-yellow','flower-red','grass','rock','wheat-a','wheat-b','corn-a','corn-d','pumpkin','carrot','fence','fence-gate','bridge-wood','catapult','ballista','flag','character-male','character-female','orc','horse','cow'];
const key=(x,z)=>x+','+z;
const pos=(x,z)=>new THREE.Vector3((x-(NX-1)/2)*T,0,(z-(NZ-1)/2)*T);
function rng(v){let n=Math.sin(v*127.1+17.75)*43758.5453;return n-Math.floor(n);}
function fresh(){
 let d={v:3,day:1,gold:420,food:190,wood:220,army:12,workers:5,health:450,maxHealth:450,plots:{},enemies:factions.map(f=>f.initial),selected:{x:7,z:8},enemySelected:0,log:['مزرعه بزرگ زمرد آماده فرمان شماست.'],completed:false,wins:0,score:0};
 d.plots[key(6,9)]={type:'wheat',age:2};
 d.plots[key(7,9)]={type:'corn',age:1};
 d.plots[key(6,10)]={type:'wheat',age:1};
 return d;
}
function validate(s){
 return !!(s&&s.v===3&&Number.isSafeInteger(s.day)&&s.day>0&&s.day<50000&&
 ['gold','food','wood','army','workers','health','maxHealth','score','wins','enemySelected'].every(k=>Number.isSafeInteger(s[k])&&s[k]>=0&&s[k]<10000000)&&
 s.enemySelected<3&&Array.isArray(s.enemies)&&s.enemies.length===3&&s.enemies.every((n,i)=>Number.isSafeInteger(n)&&n>=0&&n<=factions[i].initial)&&
 s.plots&&Object.keys(s.plots).length<=120&&Object.entries(s.plots).every(([k,p])=>{
 const parts=k.split(',').map(Number);return parts.length===2&&parts.every(Number.isInteger)&&isPlayerPlot(parts[0],parts[1])&&itemDefs[p?.type]?.build&&Number.isInteger(p.age)&&p.age>=0&&p.age<10000;
 })&&s.selected&&Number.isInteger(s.selected.x)&&Number.isInteger(s.selected.z)&&Array.isArray(s.log)&&s.log.length<=8&&s.log.every(x=>typeof x==='string'&&x.length<200)&&typeof s.completed==='boolean');
}
const STORAGE='zm-farm-dominion-3d-v3';
function restore(){try{const obj=JSON.parse(localStorage.getItem(STORAGE));if(validate(obj))return obj;}catch(e){}return fresh();}
let state=restore(),mode='wheat',assets={},renderer,scene,camera,sun,terrain,groundPlane,selection,selectionBorder;
let cam={center:new THREE.Vector3(-3.5,0,0),angle:Math.PI/4,zoom:1,polar:Math.PI/3.05},camMin=0.8,camMax=2.7;
let buildingGroup,cropGroup,environmentGroup,actorsGroup,particlesGroup,flags=[],windmills=[],animals=[],animatedUnits=[],fx=[],ready=false;
let rafId=0,lastTime=0,frame=0,lastToast=0,activePointers=new Map(),lastPinch=0;
const rendererStats={drawCalls:0};
function save(){try{localStorage.setItem(STORAGE,JSON.stringify(state));}catch(e){}}
function notice(message){state.log.unshift(message);state.log=state.log.slice(0,6);updateUI();const t=ui.toast;t.textContent=message;t.classList.remove('hide');lastToast=performance.now();}
function affordable(cost){return Object.entries(cost||{}).every(([k,v])=>state[k]>=v);}
function pay(cost){for (const [k,v] of Object.entries(cost||{}))state[k]-=v;}
function gain(result){for (const [k,v] of Object.entries(result||{}))state[k]+=v;}
function isInside(x,z){return x>=0&&x<NX&&z>=0&&z<NZ;}
function isPlayerPlot(x,z){return isInside(x,z)&&x>=1&&x<=8&&z>=1&&z<=12&&!((x<=4&&z>=5&&z<=8)||(x>=4&&x<=6&&z>=2&&z<=4));}
function readyCrop(p){return !!p&&['wheat','corn','pumpkin'].includes(p.type)&&p.age>=itemDefs[p.type].days;}
function countType(t){return Object.values(state.plots).filter(p=>p.type===t).length;}
function liveEnemyCount(){return state.enemies.filter(n=>n>0).length;}
function currentTarget(){return factions[state.enemySelected];}
function terrainMaterial(color,rough=.86){return new THREE.MeshStandardMaterial({color,roughness:rough,metalness:0});}
const pal={
 grass:terrainMaterial(0x7fa967),forest:terrainMaterial(0x437955),
 pine:terrainMaterial(0x3b6950),soil:terrainMaterial(0x865538),
 dirt:terrainMaterial(0xa17a4b),sand:terrainMaterial(0xe0b77c),
 stone:terrainMaterial(0xa8a9a0),whiteStone:terrainMaterial(0xe3dbbb),
 wood:terrainMaterial(0x84552c),darkWood:terrainMaterial(0x533824),
 red:terrainMaterial(0xb7473c),redRoof:terrainMaterial(0xa94030,.63),
 blueRoof:terrainMaterial(0x365c75,.65),goldRoof:terrainMaterial(0xc38a47,.65),
 roof:terrainMaterial(0x8d4d34,.75),gold:terrainMaterial(0xe7ba5b,.43),
 crop:terrainMaterial(0xd7b551,.8),wall:terrainMaterial(0xe2cd9d),fort:terrainMaterial(0xbdbbb0),
 turquoise:terrainMaterial(0x369bc0,.25),water: new THREE.MeshPhysicalMaterial({color:0x3ea8ac,roughness:.19,metalness:.05,transparent:true,opacity:.84,clearcoat:.8}),
 black:terrainMaterial(0x2b322b),window:new THREE.MeshStandardMaterial({color:0xffdb78,emissive:0xa45f12,emissiveIntensity:1.1,roughness:.4}),
 leaves:terrainMaterial(0x5e9f51),highlight:new THREE.MeshBasicMaterial({color:0xf8dd8f,transparent:true,opacity:.18,depthWrite:false,side:THREE.DoubleSide})
};
function addBox(parent,w,h,d,x,y,z,material,cast=true){
 const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);
 m.position.set(x,y,z);m.castShadow=cast;m.receiveShadow=true;parent.add(m);return m;
}
function addCylinder(parent,r1,r2,h,x,y,z,material,segments=8){
 const m=new THREE.Mesh(new THREE.CylinderGeometry(r1,r2,h,segments),material);
 m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;
}
function addCone(parent,r,h,x,y,z,material,segments=6){
 const m=new THREE.Mesh(new THREE.ConeGeometry(r,h,segments),material);
 m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;
}
function addSphere(parent,r,x,y,z,material){
 const m=new THREE.Mesh(new THREE.IcosahedronGeometry(r,1),material);
 m.position.set(x,y,z);m.castShadow=true;parent.add(m);return m;
}
function colorMat(hex){return new THREE.MeshStandardMaterial({color:hex,roughness:.78,metalness:.04});}
function groupAt(x,z,y=0){let g=new THREE.Group();g.position.copy(pos(x,z));g.position.y=y;return g;}
function cloneModel(name,size=1){
 const src=assets[name];
 if(!src)return null;
 const model=src.clone(true);
 const box=new THREE.Box3().setFromObject(model);
 const sz=box.getSize(new THREE.Vector3());
 const width=Math.max(sz.x,sz.z,.001),height=Math.max(sz.y,.001);
 const factor=size/Math.max(width,height*.7);
 model.scale.setScalar(factor);
 const b2=new THREE.Box3().setFromObject(model);
 model.position.sub(new THREE.Vector3((b2.min.x+b2.max.x)/2,b2.min.y,(b2.min.z+b2.max.z)/2));
 model.traverse(c=>{if(c.isMesh){c.castShadow=true;c.receiveShadow=true;c.frustumCulled=true;}});
 return model;
}
function putModel(group,name,size,x=0,y=0,z=0){
 const clone=cloneModel(name,size);
 if(!clone)return null;
 const holder=new THREE.Group();holder.position.set(x,y,z);holder.add(clone);group.add(holder);
 return holder;
}
function gable(parent,w,depth,baseY,rise,material){
 const shape=new THREE.Shape();
 shape.moveTo(-w*.56,baseY);
 shape.lineTo(0,baseY+rise);
 shape.lineTo(w*.56,baseY);
 shape.closePath();
 const geometry=new THREE.ExtrudeGeometry(shape,{depth:depth+0.12,bevelEnabled:true,bevelThickness:.045,bevelSize:.06,bevelSegments:1});
 geometry.computeVertexNormals();
 const mesh=new THREE.Mesh(geometry,material);
 mesh.position.z=-(depth+0.12)/2;mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);
 for(let j=-1;j<=1;j++){
 const beam=addBox(parent,w*.6,.035,.038,0,baseY+rise*.56,j*depth*.43,pal.darkWood,false);
 beam.rotation.z=.63;
 }
 return mesh;
}
function windows(g,w,h,d,count=2){
 for(let i=0;i<count;i++){
  const x=(i-(count-1)/2)*w*.48;
  addBox(g,.29,.42,.05,x,h*.6,d/2+.027,pal.window,false);
  addBox(g,.36,.05,.06,x,h*.6+.19,d/2+.055,pal.darkWood,false);
  addBox(g,.08,.46,.06,x,h*.6,d/2+.07,pal.darkWood,false);
 }
}
function houseModel(kind='house',faction=0){
 const g=new THREE.Group();
 const barn=kind==='barn',wind=kind==='mill',market=kind==='market',tower=kind==='tower',orchard=kind==='orchard';
 if(orchard){
  for(let i=0;i<5;i++){
   const x=(-1+i%3)*.52,z=(-1+Math.floor(i/3))*0.7;
   let obj=putModel(g,'tree-oak',1.5,x,0,z);
   if(!obj){addCylinder(g,.13,.16,.85,x,.43,z,pal.wood);addSphere(g,.55,x,1.12,z,pal.leaves);}
   addSphere(g,.13,x+.18,1.0,z+.13,colorMat(i%2?0xe78c29:0xcf4939));
  }
  addBox(g,1.6,.1,.18,0,.1,.95,pal.wood);return g;
 }
 if(tower){
  addCylinder(g,.65,.75,2.5,0,1.3,0,pal.fort,8);
  for(let j=0;j<8;j++){let a=j*Math.PI/4;addBox(g,.28,.4,.27,Math.sin(a)*.67,2.5,Math.cos(a)*.67,pal.fort);}
  addCone(g,1.1,1.1,0,3.12,0,pal.redRoof,8);
  addBox(g,.15,.7,.14,0,3.9,0,pal.darkWood);
  const banner=addBox(g,.48,.28,.025,.24,3.86,0,colorMat(0x54af73));
  flags.push({node:banner,base:0,seed:Math.random()*20});
  return g;
 }
 if(market){
  addBox(g,2.3,.2,1.65,0,.18,0,pal.wood);
  for(let x of [-.95,.95])for(let z of [-.62,.62])addBox(g,.09,1.6,.1,x,1.0,z,pal.darkWood);
  for(let j=0;j<6;j++)addBox(g,2.48/6,.13,1.9,(j-2.5)*2.45/6,1.85,0,j%2?pal.redRoof:pal.whiteStone);
  addBox(g,1.5,.12,.58,0,.75,.65,pal.darkWood);
  for(let x of [-.55,-.16,.21,.58])addSphere(g,.16,x,.95,.62,x<0?pal.crop:pal.leaves);
  return g;
 }
 const w=barn?2.4:wind?1.45:1.85;
 const d=barn?1.85:wind?1.35:1.55;
 const h=barn?2.1:wind?2.3:1.52;
 const walls=barn?pal.red:pal.whiteStone,roof=barn?pal.redRoof:wind?pal.roof:pal.blueRoof;
 addBox(g,w,.33,d,0,.16,0,pal.stone);
 addBox(g,w,h,d,0,h/2+.3,0,walls);
 for(let level=0;level<3;level++){
   addBox(g,.07,.07,d+.06,-w/2+.08,.45+level*h*.44,0,pal.darkWood,false);
   addBox(g,.07,.07,d+.06,w/2-.08,.45+level*h*.44,0,pal.darkWood,false);
 }
 gable(g,w,d,h+.3,barn?1.22:wind?.85:.85,roof);
 addBox(g,barn?.7:.55,barn?1.18:.91,.065,0,barn?.92:.83,d/2+.042,pal.darkWood);
 addBox(g,.16,.19,.07,0,.7,d/2+.1,pal.gold);
 windows(g,w,h+.3,d,barn?1:2);
 addCylinder(g,.22,.25,.7,w*.32,h+1.0,-d*.2,pal.whiteStone,6);
 if(barn){
  addBox(g,.58,.2,.4,1.16,.43,-.4,pal.wood);
  addBox(g,.5,.14,.15,-.8,.4,1.02,pal.gold);
 }
 if(wind){
  const axis=new THREE.Group();axis.position.set(0,h*.8+.3,d/2+.31);
  addCylinder(axis,.18,.2,.3,0,0,.1,pal.wood,12).rotation.x=Math.PI/2;
  for(let i=0;i<4;i++){
   const blade=new THREE.Group();blade.rotation.z=i*Math.PI/2;
   addBox(blade,.12,1.16,.10,0,.65,0,pal.darkWood);
   addBox(blade,.56,.79,.04,.19,.67,.055,pal.sand);
   addBox(blade,.09,.88,.07,.39,.63,.06,pal.darkWood);
   axis.add(blade);
  }
  g.add(axis);windmills.push(axis);
 }
 return g;
}
function castleModel(tint=0x5c9e6c,enemy=false){
 const g=new THREE.Group();
 const col=colorMat(tint),roof=enemy?pal.redRoof:pal.blueRoof;
 addBox(g,4.25,.85,3.9,0,.43,0,pal.whiteStone);
 addBox(g,3.25,1.8,2.85,0,1.55,0,pal.fort);
 for(let i=-1;i<=1;i++)addBox(g,.85,.38,1.05,i*1.05,2.62,1.03,pal.fort);
 addBox(g,.92,1.42,.14,0,1.23,2.01,pal.darkWood);
 addBox(g,.18,.31,.16,0,1.43,2.13,pal.gold);
 addBox(g,3.6,.22,3.2,0,2.5,0,pal.whiteStone);
 gable(g,2.7,2,2.66,1.03,enemy?pal.redRoof:pal.goldRoof);
 for(let x of [-2,2])for(let z of [-1.7,1.7]){
  addCylinder(g,.57,.65,3.1,x,1.6,z,pal.fort,10);
  for(let j=0;j<8;j++){
   const a=j*Math.PI/4;
   addBox(g,.25,.38,.28,x+Math.sin(a)*.55,3.27,z+Math.cos(a)*.55,pal.whiteStone);
  }
  addCone(g,.79,1.05,x,3.77,z,roof,8);
  const pole=addCylinder(g,.055,.055,.9,x,4.55,z,pal.darkWood,7);
  const flag=addBox(g,.47,.32,.035,x+.23,4.64,z,col);
  flags.push({node:flag,base:x+.23,seed:(x+z)*3.1});
 }
 for(let j=-1;j<=1;j++)for(let k of [-1,1])addBox(g,.18,.18,.08,j*.66,1.75,k*1.57,pal.darkWood);
 addBox(g,4.8,.20,4.3,0,.08,0,enemy?pal.dirt:pal.stone,false);
 const tower=putModel(g,'catapult',1.65,enemy?2.9:-2.9,0,-1.5);
 if(tower)tower.rotation.y=enemy?Math.PI*.6:-Math.PI*.3;
 return g;
}
function waterShape(){
 const vertices=[],indices=[],segments=68;
 const xBase=(9.57-(NX-1)/2)*T;
 for(let i=0;i<=segments;i++){
  const z=(i/segments-.5)*WORLD_D;
  const mid=xBase+Math.sin(i*.34)*.43+Math.cos(i*.1)*.14;
  const span=2.28+Math.sin(i*.5)*.10;
  vertices.push(mid-span,-.13,z,mid+span,-.13,z);
  if(i<segments){let j=i*2;indices.push(j,j+1,j+2,j+2,j+1,j+3);}
 }
 const geom=new THREE.BufferGeometry();
 geom.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
 geom.setIndex(indices);geom.computeVertexNormals();
 const mesh=new THREE.Mesh(geom,pal.water);mesh.receiveShadow=true;mesh.userData.water=true;return mesh;
}
function buildLandscape(){
 environmentGroup=new THREE.Group();scene.add(environmentGroup);
 const base=new THREE.Mesh(new THREE.BoxGeometry(WORLD_W+1,1.9,WORLD_D+1),pal.soil);
 base.position.y=-1.11;base.castShadow=true;base.receiveShadow=true;environmentGroup.add(base);
 const plane=new THREE.Mesh(new THREE.PlaneGeometry(WORLD_W,WORLD_D,49,35),pal.grass);
 plane.rotation.x=-Math.PI/2;plane.receiveShadow=true;environmentGroup.add(plane);groundPlane=plane;
 const roughColor=new THREE.Color();
 const mat=new THREE.MeshStandardMaterial({vertexColors:true,roughness:.95});
 const floor=new THREE.PlaneGeometry(WORLD_W,WORLD_D,99,69);
 const colors=[];
 for(let i=0;i<floor.attributes.position.count;i++){
  const x=floor.attributes.position.getX(i),z=floor.attributes.position.getY(i);
  let n=rng(x*3.1+z*5.17),factor=.84+n*.31;
  roughColor.setRGB(.38*factor,.59*factor,.31*factor,THREE.SRGBColorSpace);
  colors.push(roughColor.r,roughColor.g,roughColor.b);
 }
 floor.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
 const ground=new THREE.Mesh(floor,mat);ground.rotation.x=-Math.PI/2;ground.position.y=.009;ground.receiveShadow=true;environmentGroup.add(ground);
 environmentGroup.add(waterShape());
 // River foam edges and stepping stones.
 for(let z=0;z<NZ;z++){
  const pp=pos(9.6,z);
  for(let side of [-1,1]){
   addSphere(environmentGroup,.11,pp.x+side*2.45,.025,pp.z+.33,pal.stone);
  }
 }
 // Single central stone-wood bridge.
 const bridgeCenter=pos(9.6,7);
 const bridge=new THREE.Group();bridge.position.set(bridgeCenter.x,.3,bridgeCenter.z);
 addBox(bridge,7.5,.3,2.45,0,.2,0,pal.wood);
 for(let x=-3.35;x<3.5;x+=.55)addBox(bridge,.5,.04,2.45,x,.38,0,pal.sand,false);
 for(let side of [-1,1]){
  for(let x=-3.4;x<3.7;x+=1.15)addBox(bridge,.15,.67,.18,x,.75,side*1.1,pal.darkWood);
  addBox(bridge,7.35,.13,.16,0,1.09,side*1.1,pal.wood);
 }
 environmentGroup.add(bridge);
 // winding ground roads, engraved paving, dry patches
 for(const path of [[2,7,9,7],[3,4,8,4],[4,10,7,10],[11,7,18,7],[13,2,17,2],[13,12,17,12]]){
  const [x0,z0,x1,z1]=path;let first=pos(x0,z0),last=pos(x1,z1);
  const len=first.distanceTo(last);
  const road=addBox(environmentGroup,len+.8,.022,.83,(first.x+last.x)/2,.029,(first.z+last.z)/2,pal.dirt,false);
  if(z1!==z0)road.rotation.y=Math.PI/2;
  for(let j=0;j<Math.max(1,Math.floor(len/.75));j++){
   const t=j/Math.max(1,Math.floor(len/.75));
   const cx=THREE.MathUtils.lerp(first.x,last.x,t),cz=THREE.MathUtils.lerp(first.z,last.z,t);
   addBox(environmentGroup,.19,.026,.09,cx,.044,cz,pal.sand,false);
  }
 }
 // coherent miniature natural environment with real CC0 models
 for(let x=0;x<NX;x++)for(let z=0;z<NZ;z++){
  const r=rng(x*37+z*89);if((x>1&&x<9&&z>1&&z<12)||(x>12&&x<18&&z>0&&z<13))continue;
  if(x===9||x===10)continue;
  const wp=pos(x,z);
  if(r<.26){
   const tree=putModel(environmentGroup,['tree-oak','tree-detailed','tree-default','tree-pine'][Math.floor(rng(x*17+z*19)*4)],2.4+rng(x*9+z*16)*1.15,wp.x+(r-.14)*.8,0,wp.z);
   if(!tree){
    addCylinder(environmentGroup,.14,.17,.82,wp.x,.4,wp.z,pal.wood);
    addSphere(environmentGroup,.87,wp.x,1.48,wp.z,pal.leaves);
   }
  }else if(r<.39){putModel(environmentGroup,'plant-bush',.87,wp.x,0,wp.z);}
  else if(r<.52){putModel(environmentGroup,'flower-yellow',.5,wp.x,0,wp.z);}
  else if(r<.58){putModel(environmentGroup,'rock',.9,wp.x,0,wp.z);}
 }
 // extra clusters of 3D trees along borders, flowers, reeds and animated scenery
 for(let i=0;i<135;i++){
  const x=rng(i*57.11)*WORLD_W-WORLD_W/2,z=rng(i*91.2)*WORLD_D-WORLD_D/2;
  const cellX=Math.floor((x+WORLD_W/2)/T),cellZ=Math.floor((z+WORLD_D/2)/T);
  if(!isInside(cellX,cellZ)||x>-3.3&&x<3.5||isPlayerPlot(cellX,cellZ)&&rng(i*19)>.09)continue;
  const type=rng(i*16);
  if(type<.16)putModel(environmentGroup,'flower-red',.25,x,0,z);
  else if(type<.42)putModel(environmentGroup,'grass',.4,x,0,z);
  else if(type<.48)putModel(environmentGroup,'rock',.47,x,0,z);
 }
 // atmosphere: small fluffy mesh-clouds above island
 const cloudMat=new THREE.MeshLambertMaterial({color:0xfffdf1,transparent:true,opacity:.38,depthWrite:false});
 for(let i=0;i<10;i++){
  const x=(rng(i*13)-.5)*85,z=(rng(i*74)-.5)*80,h=13+rng(i*9)*7;
  for(let j=0;j<4;j++){
   const part=new THREE.Mesh(new THREE.SphereGeometry(1.5+j*.24,10,8),cloudMat);
   part.scale.set(2.2,0.39,1.0);part.position.set(x+j*1.25,h+j*.12,z+Math.sin(i+j)*.8);part.castShadow=false;environmentGroup.add(part);
  }
 }
}
function makeFences(parent,x,z,s=1){
 for(let i=-1;i<=1;i++){
  for(let side of [-1,1]){
   const fence=putModel(parent,'fence',.95,i*.75,.05,side*.95);
   if(fence)fence.rotation.y=0;else addBox(parent,.62,.42,.09,i*.75,.35,side*.95,pal.wood);
  }
 }
 for(let side of [-1,1]){
  for(let i=-1;i<=1;i++){
   const fence=putModel(parent,'fence',.95,side*1.16,.04,i*.62);
   if(fence)fence.rotation.y=Math.PI/2;else addBox(parent,.09,.42,.60,side*1.16,.35,i*.62,pal.wood);
  }
 }
}
function placePermanent(){
 buildingGroup=new THREE.Group();scene.add(buildingGroup);
 const castle=castleModel(0x70c17b);castle.position.copy(pos(3,6));buildingGroup.add(castle);
 for(let i=0;i<factions.length;i++){
  const e=factions[i];let c=castleModel(e.color,true);c.position.copy(pos(e.x,e.z));c.rotation.y=i===1?Math.PI/3:-Math.PI/4;buildingGroup.add(c);
 }
 for(const [type,x,z,rot] of [['house',5,6,0],['barn',3,3,-.1],['mill',6,2,.3],['house',5,10,.12],['market',7,5,.3]]){
  const g=houseModel(type);g.position.copy(pos(x,z));g.rotation.y=rot;buildingGroup.add(g);
 }
 for(let z=3;z<=10;z+=1.1){let p=pos(1,z);const fence=putModel(buildingGroup,'fence',1.2,p.x,.03,p.z);if(fence)fence.rotation.y=Math.PI/2;}
 const pasture=groupAt(2.4,10.3);makeFences(pasture);
 let cow=putModel(pasture,'cow',1.1,-.35,.07,.22),horse=putModel(pasture,'horse',1.4,.44,.1,-.35);
 if(cow)animals.push({obj:cow,initial:cow.position.clone(),seed:2});if(horse)animals.push({obj:horse,initial:horse.position.clone(),seed:3});
 buildingGroup.add(pasture);
 // enemy siege machinery and camps
 factions.forEach((f,i)=>{
   for(let j=0;j<2;j++){
    let p=pos(f.x+(j?1.4:-1.1),f.z+(j?.9:-1.5));
    let siege=putModel(buildingGroup,j?'ballista':'catapult',1.55,p.x,.05,p.z);
    if(siege)siege.rotation.y=.8+i;
   }
   const tent=houseModel('house');tent.scale.setScalar(.72);tent.position.copy(pos(f.x-1.6,f.z+1.55));tent.rotation.y=.2;buildingGroup.add(tent);
 });
 const farmer=putModel(buildingGroup,'character-female',1.45,pos(5,8).x,.05,pos(5,8).z);
 if(farmer)animals.push({obj:farmer,initial:farmer.position.clone(),seed:6});
}
function cropPatch(x,z,type,age){
 const g=groupAt(x,z);
 const ripe=age>=itemDefs[type].days;
 addBox(g,1.89,.15,1.93,0,.075,0,pal.soil);
 for(let row=0;row<5;row++){
  let zz=(row-2)*.33;
  addBox(g,1.69,.073,.18,0,.18,zz,pal.dirt,false);
 }
 for(let a=0;a<4;a++)for(let b=0;b<3;b++){
  const xp=(a-1.5)*.39,zp=(b-1)*.53;
  let which=type==='wheat'?ripe?'wheat-b':'wheat-a':type==='corn'?ripe?'corn-d':'corn-a':'pumpkin';
  let object=putModel(g,which,type==='pumpkin'?.58:.55,xp,.24,zp);
  if(!object){
   let material=type==='wheat'?pal.crop:pal.leaves;
   addCone(g,.12,ripe?.75:.35,xp,.3,zp,material,6);
  }
 }
 if(ripe){
  const sparkle=addSphere(g,.18,0,1.1,0,pal.gold);sparkle.material=new THREE.MeshBasicMaterial({color:0xf9df93,transparent:true,opacity:.6});
  g.userData.ready=true;g.userData.sparkle=sparkle;
 }
 return g;
}
function refreshPlots(){
 if(cropGroup){scene.remove(cropGroup);cropGroup.traverse(o=>{if(o.geometry)o.geometry.dispose();});}
 cropGroup=new THREE.Group();scene.add(cropGroup);
 for(const [coord,p] of Object.entries(state.plots)){
   const [x,z]=coord.split(',').map(Number);
   let g;
   if(['wheat','corn','pumpkin'].includes(p.type))g=cropPatch(x,z,p.type,p.age);
   else if(p.type==='orchard')g=houseModel('orchard');
   else g=houseModel(p.type);
   if(!g.position.lengthSq())g.position.copy(pos(x,z));
   cropGroup.add(g);
 }
}
function initScene(){
 const mobile=window.innerWidth<750;
 if(mobile){cam.center.copy(pos(3.4,6));}else{cam.center.set(-1,0,-.5);}
 renderer=new THREE.WebGLRenderer({canvas:ui.world,antialias:!mobile,alpha:false,powerPreference:'high-performance'});
 renderer.setPixelRatio(Math.min(devicePixelRatio||1,mobile?1.4:1.8));
 renderer.setSize(ui.world.clientWidth||innerWidth,ui.world.clientHeight||innerHeight);
 renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.17;
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 scene=new THREE.Scene();scene.background=new THREE.Color(0xa0c3c6);
 scene.fog=new THREE.FogExp2(0x9dbfc0,.007);
 const hemi=new THREE.HemisphereLight(0xe5f4ff,0x6f8754,1.65);scene.add(hemi);
 const ambient=new THREE.AmbientLight(0xf4dcbb,.45);scene.add(ambient);
 sun=new THREE.DirectionalLight(0xffd49e,2.95);sun.position.set(-25,38,16);sun.castShadow=true;
 sun.shadow.mapSize.set(mobile?1024:2048,mobile?1024:2048);
 sun.shadow.camera.left=-37;sun.shadow.camera.right=37;sun.shadow.camera.top=35;sun.shadow.camera.bottom=-35;
 sun.shadow.camera.near=.5;sun.shadow.camera.far=100;
 sun.shadow.bias=-.00035;sun.shadow.normalBias=.015;sun.target.position.set(0,0,0);scene.add(sun,sun.target);
 camera=new THREE.OrthographicCamera(-20,20,12,-12,.1,300);
 updateCamera();
 buildLandscape();placePermanent();refreshPlots();
 actorsGroup=new THREE.Group();scene.add(actorsGroup);
 particlesGroup=new THREE.Group();scene.add(particlesGroup);
 const g=new THREE.PlaneGeometry(T-.12,T-.12);
 selection=new THREE.Mesh(g,pal.highlight);selection.rotation.x=-Math.PI/2;selection.position.copy(pos(state.selected.x,state.selected.z));selection.position.y=.15;scene.add(selection);
 const e=new THREE.EdgesGeometry(new THREE.BoxGeometry(T-.14,.02,T-.14));
 selectionBorder=new THREE.LineSegments(e,new THREE.LineBasicMaterial({color:0xffdf89,transparent:true,opacity:.95}));
 selectionBorder.position.copy(selection.position);selectionBorder.position.y=.18;scene.add(selectionBorder);
 window.addEventListener('resize',resize,{passive:true});
 resize();
}
function resize(){
 if(!renderer||!camera)return;
 const w=ui.world.clientWidth||window.innerWidth,h=ui.world.clientHeight||window.innerHeight;
 renderer.setSize(w,h,false);
 const aspect=w/h;
 const viewHeight=(w<750?34:43)/cam.zoom;
 camera.left=-viewHeight*aspect/2;camera.right=viewHeight*aspect/2;camera.top=viewHeight/2;camera.bottom=-viewHeight/2;
 camera.updateProjectionMatrix();
 renderer.render(scene,camera);
}
function updateCamera(){
 if(!camera)return;
 const distance=48;
 camera.position.set(cam.center.x+Math.sin(cam.angle)*distance,cam.center.y+distance*.91,cam.center.z+Math.cos(cam.angle)*distance);
 camera.lookAt(cam.center.x,0,cam.center.z);
 resize();
}
function panCamera(dx,dy){
 const scale=(window.innerWidth<750?34:43)/(innerHeight*cam.zoom);
 const forward=new THREE.Vector3(-Math.sin(cam.angle),0,-Math.cos(cam.angle));
 const right=new THREE.Vector3(Math.cos(cam.angle),0,-Math.sin(cam.angle));
 cam.center.addScaledVector(right,-dx*scale).addScaledVector(forward,dy*scale*1.13);
 cam.center.x=THREE.MathUtils.clamp(cam.center.x,-23,23);cam.center.z=THREE.MathUtils.clamp(cam.center.z,-17,17);
 updateCamera();
}
function setZoom(factor){cam.zoom=THREE.MathUtils.clamp(cam.zoom*factor,camMin,camMax);updateCamera();}
function raycastPoint(cx,cy){
 const bounds=ui.world.getBoundingClientRect();
 const xy=new THREE.Vector2((cx-bounds.left)/bounds.width*2-1,-((cy-bounds.top)/bounds.height)*2+1);
 const ray=new THREE.Raycaster();ray.setFromCamera(xy,camera);
 const hit=ray.intersectObject(groundPlane,true);
 if(hit.length===0)return null;
 const wp=hit[0].point;
 const x=Math.floor((wp.x+WORLD_W/2)/T),z=Math.floor((wp.z+WORLD_D/2)/T);
 return isInside(x,z)?{x,z}:null;
}
function select(x,z){
 if(!isInside(x,z))return;
 if(x>=12){
   const best=factions.map((f,i)=>({i,dist:Math.hypot(x-f.x,z-f.z)})).sort((a,b)=>a.dist-b.dist)[0];
   if(best.dist<5){state.enemySelected=best.i;notice('هدف انتخاب شد: '+factions[best.i].name);}
 }else if(isPlayerPlot(x,z)){state.selected={x,z};}
 const v=pos(state.selected.x,state.selected.z);
 selection.position.set(v.x,.15,v.z);
 selectionBorder.position.set(v.x,.18,v.z);
 updateUI();
}
function showToast(msg){const t=ui.toast;t.textContent=msg;t.classList.remove('hide');lastToast=performance.now();}
function action(modeName){
 if(modeName==='next')return nextDay();
 if(state.completed){showToast('این دور به پایان رسیده است. برای شروع دوباره از منوی بازی جدید استفاده کنید.');return;}
 const def=itemDefs[modeName];
 if(!def){return;}
 mode=modeName;
 if(def.build){
   const {x,z}=state.selected;
   if(!isPlayerPlot(x,z)){showToast('ساخت‌وساز فقط در زمین‌های سبز شما ممکن است.');return;}
   if(state.plots[key(x,z)]){showToast('این زمین قبلاً ساخته شده است؛ یک زمین خالی را انتخاب کنید.');return;}
   if(!affordable(def.cost)){showToast('منابع کافی ندارید؛ برداشت محصول و تجارت را ادامه دهید.');return;}
   pay(def.cost);
   state.plots[key(x,z)]={type:modeName,age:0};
   refreshPlots();notice(def.label+' در زمین '+(x+1)+'–'+(z+1)+' ساخته شد.');burst(pos(x,z),0xede1a4,16);save();
 }else if(modeName==='harvest'){
   const p=state.plots[key(state.selected.x,state.selected.z)];
   if(!readyCrop(p)){showToast('ابتدا یک کشتزار کاملاً رسیده را انتخاب کنید.');return;}
   const yieldItem=itemDefs[p.type].yield;
   gain(yieldItem);delete state.plots[key(state.selected.x,state.selected.z)];
   refreshPlots();notice('محصول برداشت شد: '+yieldItem.food+' غذا و '+yieldItem.gold+' سکه.');burst(pos(state.selected.x,state.selected.z),0xe9d28c,20);
 }else if(modeName==='train'){
   if(!affordable(def.cost)){showToast('برای آموزش نیرو به طلا و غذا نیاز است.');return;}
   pay(def.cost);state.army+=4;notice('چهار سرباز تازه نفس به ارتش زمرد پیوستند.');
   spawnSquad(true,3,pos(3,6),pos(5,8));
 }else if(modeName==='attack'){
   const i=state.enemySelected;
   if(!state.enemies[i]){showToast('قلعه این خاندان قبلاً فتح شده است؛ دشمن دیگری را انتخاب کنید.');return;}
   if(!affordable(def.cost)){showToast('برای نبرد حداقل چهار سرباز و ۲۴ غذا لازم است.');return;}
   pay(def.cost);
   const strength=36+Math.floor(Math.random()*20)+Math.min(18,countType('tower')*3)+Math.min(12,state.workers*2);
   state.enemies[i]=Math.max(0,state.enemies[i]-strength);
   state.score+=strength*4;
   const target=pos(factions[i].x,factions[i].z);
   spawnSquad(true,4,pos(3,6),target,()=>burst(target,0xffb96f,28));
   notice('سپاه زمرد به '+factions[i].name+' یورش برد؛ '+strength+' خسارت وارد شد.');
   if(state.enemies[i]===0){
    state.gold+=170;state.wood+=45;state.wins++;
    notice('پرچم زمرد بر فراز '+factions[i].name+' برافراشته شد! +۱۷۰ طلا');
    if(liveEnemyCount()===0){state.completed=true;setTimeout(()=>showVictory(),1900);}
   }
 }else if(modeName==='repair'){
   if(state.health>=state.maxHealth){showToast('قلعه شما در سلامت کامل است.');return;}
   if(!affordable(def.cost)){showToast('برای تعمیر قلعه به چوب و طلا نیاز دارید.');return;}
   pay(def.cost);state.health=Math.min(state.maxHealth,state.health+85);notice('دژ زمرد تعمیر شد: +۸۵ سلامت.');
 }else return;
 updateUI();save();
}
function nextDay(){
 if(state.completed)return;
 state.day++;
 const gold=20+countType('market')*38+countType('mill')*23;
 const wood=10+countType('orchard')*17;
 const food=countType('barn')*25;
 const upkeep=Math.ceil(state.army/3);
 gain({gold,wood,food});
 state.food=Math.max(0,state.food-upkeep);
 for(const p of Object.values(state.plots))if(['wheat','corn','pumpkin'].includes(p.type))p.age++;
 if(state.day%2===0&&liveEnemyCount()){
   const alive=factions.map((f,i)=>({...f,i})).filter(f=>state.enemies[f.i]>0);
   const attacker=alive[state.day%alive.length],damage=Math.max(1,35+Math.floor(Math.random()*16)-countType('tower')*15-Math.floor(state.army/5));
   state.health=Math.max(0,state.health-damage);
   spawnSquad(false,3,pos(attacker.x,attacker.z),pos(3,6),()=>burst(pos(3,6),0xffae74,16));
   notice('هجوم '+attacker.name+': '+damage+' خسارت به قلعه! برج‌های دفاعی خسارت را کاهش می‌دهند.');
 }else{
   notice('روز '+state.day+' آغاز شد: '+gold+' طلا، '+wood+' چوب و '+food+' غذا به انبار اضافه شد.');
 }
 if(state.day%4===0){
   const idx=state.enemies.findIndex(h=>h>0);
   if(idx>=0)state.enemies[idx]=Math.min(factions[idx].initial,state.enemies[idx]+12);
 }
 if(state.health===0){state.completed=true;setTimeout(()=>showDefeat(),1500);}
 refreshPlots();updateUI();save();
}
function showVictory(){
 ui['tour'].style.display='block';ui['tour'].querySelector('h2').textContent='🏆 امپراتوری زمرد پیروز شد!';
 ui['tour'].querySelector('p').textContent='هر سه خاندان رقیب تسخیر شدند. امتیاز شما '+state.score+' است و قلعه زمرد پس از '+state.day+' روز پابرجاست. برای شروع دوباره از منوی بازی جدید استفاده کنید.';
}
function showDefeat(){
 ui['tour'].style.display='block';ui['tour'].querySelector('h2').textContent='قلعه زمرد سقوط کرد';
 ui['tour'].querySelector('p').textContent='مزارع شما تا روز '+state.day+' مقاومت کردند. برای دور بعد برج‌های دفاع و سربازهای بیشتری آماده کنید.';
}
function spawnSquad(friendly,n,from,to,onHit){
 if(!actorsGroup)return;
 let hitCount=0;
 for(let i=0;i<n;i++){
  const g=new THREE.Group();
  const src=putModel(g,friendly?'character-male':'orc',1.15);
  if(!src){
   addCylinder(g,.16,.23,.57,0,.55,0,friendly?colorMat(0x65a77e):pal.red,9);
   addSphere(g,.2,0,1.05,0,pal.sand);
  }
  const banner=addBox(g,.07,1.17,.07,-.27,.85,0,pal.darkWood);
  const pennant=addBox(g,.36,.22,.035,-.1,1.37,0,friendly?colorMat(0x65b18a):pal.red);
  const v=from.clone();v.x+=(i%3-1)*.34;v.z+=(Math.floor(i/3)-1)*.35;
  const dest=to.clone();dest.x+=(i%3-1)*.48;dest.z+=(Math.floor(i/3)-1)*.25;
  g.position.copy(v);g.rotation.y=Math.atan2(dest.x-v.x,dest.z-v.z);
  actorsGroup.add(g);
  animatedUnits.push({obj:g,from:v,to:dest,t:0,speed:6+Math.random()*1.4,delay:i*.16,friendly,onHit,i});
 }
}
function burst(location,color,count){
 if(!particlesGroup)return;
 const mat=new THREE.MeshBasicMaterial({color,transparent:true,opacity:.9,depthWrite:false});
 for(let i=0;i<count;i++){
   const p=new THREE.Mesh(new THREE.IcosahedronGeometry(.07+.08*Math.random(),0),mat.clone());
   p.position.copy(location);p.position.y=1+Math.random()*1.7;
   const vel=new THREE.Vector3((Math.random()-.5)*6,Math.random()*4.4,(Math.random()-.5)*6);
   particlesGroup.add(p);fx.push({p,vel,life:1.1+Math.random()*.4});
 }
}
function updateUI(){
 const badges=[['☀','روز',state.day],['🪙','طلا',state.gold],['🌾','غذا',state.food],['🪵','چوب',state.wood],['🛡','سپاه',state.army],['♥','قلعه',state.health+'/'+state.maxHealth]];
 ui.resources.innerHTML=badges.map(([sym,title,n])=>'<div class="resource"><span class="sym">'+sym+'</span><div><strong>'+n+'</strong><small>'+title+'</small></div></div>').join('');
 ui.day.textContent='روز '+state.day;ui.season.textContent='مرحله '+(1+Math.floor(state.day/5));
 ui.enemies.innerHTML=factions.map((f,i)=>{
  const hp=state.enemies[i],selected=i===state.enemySelected;
  return '<button type="button" class="target" data-enemy="'+i+'" aria-pressed="'+selected+'" style="background:'+(selected?'#416b506e':'transparent')+';color:#fff0ca;border:0;border-bottom:1px solid #b9d1ac40;width:100%;text-align:right;cursor:pointer;border-radius:5px"><span><span style="color:#'+new THREE.Color(f.color).getHexString()+'">◆</span> <span class="faction">'+f.name+'</span></span><span class="health">'+(hp===0?'فتح شد ✓':hp+' / '+f.initial)+'</span></button>';
 }).join('');
 ui.mission.textContent=state.completed?(state.health>0?'🎉 هر سه قلعه فتح شدند!':'قلعه شما سقوط کرد.'):('🎯 قلعه هدف: '+currentTarget().name+' · '+state.enemies[state.enemySelected]+' جان');
 ui.log.textContent=state.log.slice(0,4).map((s,i)=>(i===0?'◉ ':'▫ ')+s).join('\n');
 ui.estate.innerHTML=[['🏘 ساختمان‌ها',Object.values(state.plots).filter(p=>!['wheat','corn','pumpkin'].includes(p.type)).length+5],['🌱 مزارع',Object.values(state.plots).filter(p=>['wheat','corn','pumpkin'].includes(p.type)).length],['👷 کارگران',state.workers],['🛡 برج دفاع',countType('tower')],['🏆 پیروزی',state.wins+'/۳']].map(([k,v])=>'<div class="row-small"><span>'+k+'</span><b>'+v+'</b></div>').join('');
 ui.quest.textContent=state.wins===0?'اولین قلعه رقیب را فتح کنید. منابع بسازید و سپاه را برای حمله آماده کنید.':state.wins===3?'هر سه خاندان شکست خوردند.':state.wins+' قلعه فتح شد. '+(3-state.wins)+' رقیب باقی مانده است.';
 ui.questfill.style.width=(state.wins/3*100)+'%';
 const selected=state.selected,p=state.plots[key(selected.x,selected.z)];
 ui.selection.textContent='زمین '+(selected.x+1)+' / '+(selected.z+1)+' · '+(p?(itemDefs[p.type].label+(readyCrop(p)?' · محصول آماده برداشت ✓':p.age?' · '+p.age+' روز رشد':'')):'آماده کاشت یا ساخت')+' · روی زمین بزنید و فرمان صادر کنید';
 for(const b of ui.actions.querySelectorAll('button[data-action]')){
   const name=b.dataset.action,def=itemDefs[name];
   b.classList.toggle('active',name===mode);
   b.disabled=state.completed||!!def.cost&&!affordable(def.cost);
 }
}
function buildActions(){
 const order=['wheat','corn','pumpkin','harvest','orchard','barn','mill','market','tower','train','attack','repair'];
 ui.actions.innerHTML=order.map(name=>{
  const d=itemDefs[name],cost=Object.entries(d.cost||{}).map(([k,v])=>v+({gold:'🪙',wood:'🪵',food:'🌾',army:'🛡'}[k])).join(' ');
  return '<button class="tool '+(name==='attack'?'war':name==='harvest'?'special':'')+'" data-action="'+name+'" type="button"><span class="ico">'+d.icon+'</span><span class="title">'+d.label+'</span><span class="cost">'+(cost||'آماده')+'</span></button>';
 }).join('');
 ui.actions.addEventListener('click',e=>{const b=e.target.closest('button[data-action]');if(b)action(b.dataset.action);});
 ui.enemies.addEventListener('click',e=>{
  const b=e.target.closest('[data-enemy]');if(!b)return;
  state.enemySelected=Number(b.dataset.enemy);
  const t=factions[state.enemySelected];showToast('قلعه هدف: '+t.name);
  cam.center.lerp(pos(t.x,t.z),.35);updateCamera();updateUI();
 });
 for(const [id,fn] of [['next-day',nextDay],['cam-left',()=>{cam.angle-=Math.PI/8;updateCamera();}],['cam-right',()=>{cam.angle+=Math.PI/8;updateCamera();}],['cam-home',()=>{cam.center.set(-3.5,0,0);cam.angle=Math.PI/4;cam.zoom=1;updateCamera();}],['zoom-in',()=>setZoom(1.2)],['zoom-out',()=>setZoom(.82)]]){
  ui[id].addEventListener('click',fn);
 }
 ui.tutorial.addEventListener('click',()=>{ui.tour.style.display='block';});
 ui['close-tour'].addEventListener('click',()=>ui.tour.style.display='none');
 ui.start.addEventListener('click',()=>{
  ui.intro.classList.add('hidden');
  if(!localStorage.getItem('zm-farm-dominion-intro-seen')){
   localStorage.setItem('zm-farm-dominion-intro-seen','yes');
   showToast('برای کاشت‌وکار روی زمین خود بزنید؛ راهنما از پنل فرماندهی در دسترس است.');
  }
 });
 ui.world.addEventListener('pointerdown',e=>{
  ui.world.setPointerCapture?.(e.pointerId);
  activePointers.set(e.pointerId,{x:e.clientX,y:e.clientY,downX:e.clientX,downY:e.clientY,moved:false});
  lastPinch=0;
 });
 ui.world.addEventListener('pointermove',e=>{
  const p=activePointers.get(e.pointerId);if(!p)return;
  const dx=e.clientX-p.x,dy=e.clientY-p.y;
  if(Math.hypot(e.clientX-p.downX,e.clientY-p.downY)>8)p.moved=true;
  p.x=e.clientX;p.y=e.clientY;
  if(activePointers.size===1&&p.moved)panCamera(dx,dy);
  if(activePointers.size===2){
   const a=[...activePointers.values()],dist=Math.hypot(a[0].x-a[1].x,a[0].y-a[1].y);
   if(lastPinch>0)setZoom(dist/lastPinch);
   lastPinch=dist;
  }
 });
 function up(e){
  const p=activePointers.get(e.pointerId);
  if(p&&!p.moved&&activePointers.size===1&&ready&&!ui.intro.classList.contains('hidden')===false){
   const hit=raycastPoint(e.clientX,e.clientY);if(hit)select(hit.x,hit.z);
  }
  activePointers.delete(e.pointerId);lastPinch=0;
 }
 ui.world.addEventListener('pointerup',up);ui.world.addEventListener('pointercancel',e=>activePointers.delete(e.pointerId));
 ui.world.addEventListener('wheel',e=>{e.preventDefault();setZoom(e.deltaY<0?1.13:.88);},{passive:false});
 window.addEventListener('keydown',e=>{
  if(e.key==='Escape')ui.tour.style.display='none';
  if(e.key==='+')setZoom(1.18);if(e.key==='-')setZoom(.85);
  if(e.key==='ArrowLeft')panCamera(-35,0);
  if(e.key==='ArrowRight')panCamera(35,0);
  if(e.key==='ArrowDown')panCamera(0,35);
  if(e.key==='ArrowUp')panCamera(0,-35);
 });
}
function animate(time){
 rafId=requestAnimationFrame(animate);
 const dt=Math.min((time-lastTime)/1000,.05)||0;lastTime=time;frame++;
 const t=time/1000;
 for(const w of windmills)w.rotation.z=t*.48;
 for(const f of flags){f.node.rotation.z=Math.sin(t*1.8+f.seed)*.08;}
 for(const a of animals){a.obj.position.set(a.initial.x+Math.sin(t*.62+a.seed)*.22,a.initial.y+Math.sin(t*2.4+a.seed)*.04,a.initial.z+Math.sin(t*.5+a.seed)*.19);a.obj.rotation.y=Math.sin(t*.37+a.seed)*.31;}
 if(cropGroup){for(const p of cropGroup.children)if(p.userData.ready&&p.userData.sparkle){p.userData.sparkle.position.y=1.3+.18*Math.sin(t*2);p.userData.sparkle.material.opacity=.3+.3*Math.sin(t*3);}}
 for(let i=animatedUnits.length-1;i>=0;i--){
  const a=animatedUnits[i];
  a.t+=dt/a.speed;
  const k=THREE.MathUtils.clamp((a.t-a.delay)/Math.max(.1,1-a.delay),0,1);
  a.obj.position.lerpVectors(a.from,a.to,k);
  a.obj.position.y=.18+Math.abs(Math.sin(t*12+a.i))*.1;
  if(k>=1){
    actorsGroup.remove(a.obj);animatedUnits.splice(i,1);
    if(a.i===0&&a.onHit)a.onHit();
  }
 }
 for(let i=fx.length-1;i>=0;i--){
  const e=fx[i];e.life-=dt;
  e.p.position.addScaledVector(e.vel,dt);e.vel.y-=dt*11;
  e.p.material.opacity=Math.max(0,e.life);
  if(e.life<=0){particlesGroup.remove(e.p);e.p.geometry.dispose();e.p.material.dispose();fx.splice(i,1);}
 }
 sun.position.x=-25+Math.sin(t*.021)*10;
 if(time-lastToast>4100&&ui.toast&&!ui.toast.classList.contains('hide'))ui.toast.classList.add('hide');
 if(frame%2===0||innerWidth>770)renderer.render(scene,camera);
}
async function loadModels(){
 const loader=new GLTFLoader();
 let finished=0;
 await Promise.all(assetList.map(async name=>{
  try{
   const gltf=await loader.loadAsync('./assets/'+name+'.glb');
   assets[name]=gltf.scene;
  }catch(e){console.warn('Optional 3D asset unavailable:',name);}
  finished++;
  ui.loading.textContent='مدل‌های سه‌بعدی: '+finished+' از '+assetList.length;
 }));
}
async function main(){
 buildActions();updateUI();
 try{
  initScene();animate(0);
  await loadModels();
  // refresh when all detailed CC0 assets have loaded
  if(environmentGroup){scene.remove(environmentGroup);environmentGroup.traverse(n=>{if(n.isMesh&&n.geometry)n.geometry.dispose();});}
  if(buildingGroup){scene.remove(buildingGroup);buildingGroup.traverse(n=>{if(n.isMesh&&n.geometry)n.geometry.dispose();});}
  buildLandscape();placePermanent();refreshPlots();
  ready=true;ui.start.disabled=false;ui.start.textContent='ورود به دنیای سه‌بعدی ▶';
  ui.loading.textContent='جهان سه‌بعدی آماده است • مدل‌های سه‌بعدی CC0 • بدون خرید درون‌برنامه‌ای';
  updateUI();resize();
 }catch(error){
  console.error('Farm Dominion failed:',error);
  ui.error.style.display='block';ui.error.textContent='اجرای موتور سه‌بعدی با مشکل مواجه شد. مرورگر دیگری یا نسخه تازه مرورگر را امتحان کنید.';
  ui.loading.textContent='خطا در آماده‌سازی بازی';
 }
}
window.FarmDominionDebug={
 getState:()=>JSON.parse(JSON.stringify(state)),getRender:()=>({canvasWidth:ui.world.width,canvasHeight:ui.world.height,assets:Object.keys(assets).length,sceneChildren:scene?.children.length||0,renderReady:ready,drawCalls:renderer?.info.render.calls}),
 select,action,nextDay,
 reset:()=>{state=fresh();refreshPlots();updateUI();save();},
 render:()=>renderer?.render(scene,camera),
 zoom:setZoom,
 getCamera:()=>({zoom:cam.zoom,center:cam.center.toArray()}),
 assets:()=>Object.keys(assets),
 controls:()=>ui.actions.querySelectorAll('button').length
};
main();
})();