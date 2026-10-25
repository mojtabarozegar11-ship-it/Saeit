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
const operations=slice('const OPERATIONS=[','function plan(){');
const validator=slice('function validSavedWorld(s){','function restore(){');
const check=vm.runInNewContext('const NAMES=Array(30).fill("Hero");\n'+helper+operations+validator+'\nvalidSavedWorld');
const base={hero:0,mission:0,endless:false,victory:false,gameOver:false,x:2.5,y:7.5,angle:0,hp:100,maxHp:100,lives:100,ammo:8,rockets:12,drones:3,score:0,enemies:[{x:8.5,y:7.5,hp:39}],hostile:[],missiles:[],pickups:[]};
assert.equal(check(base),true,'normal persisted campaign must remain resumable');
assert.equal(check({...base,mission:0,objective:{done:2,hold:0,bossDefeated:false}}),true,'completed activation mission must remain resumable');
assert.equal(check({...base,mission:1,objective:{done:1,hold:22,bossDefeated:false}}),true,'completed defense timer must remain resumable');
for(const [label,bad] of [
 ['zero-health resume',{hp:0}],['bad hero',{hero:999}],['negative hero',{hero:-1}],['nonfinite x',{x:Infinity}],['bad health',{hp:200}],['negative lives',{lives:-2}],['impossible ammo',{ammo:999}],['nonfinite score',{score:NaN}],['out-of-bounds mission',{mission:6}],['endless campaign',{endless:true}],['invalid enemy',{enemies:[{x:NaN,y:7.5,hp:39}]}],['too many enemies',{enemies:Array(21).fill({x:8,y:8,hp:39})}],['invalid missiles',{missiles:{}}],
 ['nonfinite mission kills',{missionKills:NaN}],
 ['negative mission kills',{missionKills:-1}],
 ['invalid time',{time:Infinity}],
 ['invalid points',{points:1.5}],
 ['invalid objective',{objective:{done:Infinity,hold:0,bossDefeated:false}}],
 ['invalid objective hold',{objective:{done:0,hold:-2,bossDefeated:false}}],
 ['malformed objective',{objective:{done:0,hold:0,bossDefeated:'yes'}}],
 ['oversized hostile bullets',{hostile:Array(301).fill({})}],
 ['oversized rockets',{missiles:Array(201).fill({})}],
 ['oversized pickups',{pickups:Array(201).fill({})}],
 ['invalid missionPassed',{missionPassed:'true'}],
 ['too many activated sites',{mission:0,objective:{done:3,hold:0,bossDefeated:false}}],
 ['excess defense hold',{mission:1,objective:{done:1,hold:23,bossDefeated:false}}],
 ['defense time in activation mission',{mission:0,objective:{done:1,hold:1,bossDefeated:false}}],
 ['excess recovered intel',{mission:2,objective:{done:4,hold:0,bossDefeated:false}}]
])assert.equal(check({...base,...bad}),false,label);
assert(src.includes("if(world.missionPassed){showResult('منطقه پاکسازی شد'"),'completed mission restore must return to success/continue UI');
assert(src.includes('targetUid:target.uid'),'missiles must track stable enemy identities');
assert(src.includes('seenEnemyIds.has(e.uid)'),'restored duplicate enemy IDs must be repaired');
assert(src.includes('missionKills:0,kills:0,points:0,time:0'),'older saved campaigns must restore safe progress defaults');
assert(src.includes('world.enemies.find(e=>e.uid===m.targetUid)'),'missile guidance must resolve stable IDs');
assert(src.includes('document.addEventListener(\'visibilitychange\''),'hidden tabs must pause');
assert(src.includes('if(length>1){forward/=length;side/=length}'),'diagonal movement must be normalized');
assert(src.includes('if(world.time>=nextCheckpointAt){nextCheckpointAt=world.time+12;save()}'),'long campaigns must checkpoint automatically');
assert(src.includes('nextCheckpointAt=world.time+12'),'resumed games must rebase checkpoint schedule');
assert(src.includes('world.enemyTimer=Number.isFinite(world.enemyTimer)'),'corrupted enemy spawn cooldown must be repaired');
assert(src.includes('world.reloading=world.reloading===true'),'invalid reload state must be repaired');
console.log('RAMADAN_RUNTIME_INTEGRITY_PASS save-validation=13 stable-missiles controls visibility');
