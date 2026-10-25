'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const src=fs.readFileSync('games/ramadan-war/game.js','utf8');
const slice=(from,to)=>{
 const i=src.indexOf(from),j=src.indexOf(to,i+from.length);
 assert(i>=0&&j>i,'missing runtime function '+from);
 return src.slice(i,j);
};
const helper=slice('const safeHero=v=>','let enemySerial=0;');
const validator=slice('function validSavedWorld(s){','function restore(){');
const check=vm.runInNewContext('const NAMES=Array(30).fill("Hero");\n'+helper+validator+'\nvalidSavedWorld');
const base={hero:0,mission:0,endless:false,victory:false,gameOver:false,x:2.5,y:7.5,angle:0,hp:100,maxHp:100,lives:100,ammo:8,rockets:12,drones:3,score:0,enemies:[{x:8.5,y:7.5,hp:39}],hostile:[],missiles:[],pickups:[]};
assert.equal(check(base),true,'normal persisted campaign must remain resumable');
for(const [label,bad] of [
 ['bad hero',{hero:999}],['negative hero',{hero:-1}],['nonfinite x',{x:Infinity}],['bad health',{hp:200}],['negative lives',{lives:-2}],['impossible ammo',{ammo:999}],['nonfinite score',{score:NaN}],['out-of-bounds mission',{mission:6}],['endless campaign',{endless:true}],['invalid enemy',{enemies:[{x:NaN,y:7.5,hp:39}]}],['too many enemies',{enemies:Array(21).fill({x:8,y:8,hp:39})}],['invalid missiles',{missiles:{}}]
])assert.equal(check({...base,...bad}),false,label);
assert(src.includes('targetUid:target.uid'),'missiles must track stable enemy identities');
assert(src.includes('world.enemies.find(e=>e.uid===m.targetUid)'),'missile guidance must resolve stable IDs');
assert(src.includes('document.addEventListener(\'visibilitychange\''),'hidden tabs must pause');
assert(src.includes('if(length>1){forward/=length;side/=length}'),'diagonal movement must be normalized');
console.log('RAMADAN_RUNTIME_INTEGRITY_PASS save-validation=13 stable-missiles controls visibility');
