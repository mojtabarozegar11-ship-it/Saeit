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
const tileCode=slice('function tile(', 'function newWorld(');
const validator=slice('function validSavedWorld(s){','function restore(){');
const check=vm.runInNewContext('const NAMES=Array(30).fill("Hero");\n'+helper+operations+tileCode+validator+'\nvalidSavedWorld');
const segment=vm.runInNewContext('const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));'+slice('function segmentHitsCircle(', 'function blocked(')+'segmentHitsCircle');
assert.equal(segment(0,0,2,0,1,0,.31),true,'fast projectile crossing a player must register contact');
assert.equal(segment(0,1,2,1,1,0,.31),false,'nearby projectile must not damage a player');
assert.equal(segment(0,0,0,0,0,0,.31),true,'stationary projectile contact must remain valid');
assert.equal(segment(0,0,2,0,3,0,.31),false,'collision must not extend beyond the projectile path');
assert.ok(src.includes('blocked(b.x,b.y,nx,ny)'), 'hostile projectile must test walls before damaging the player');
const base={hero:0,mission:0,endless:false,victory:false,gameOver:false,x:2.5,y:7.5,angle:0,hp:100,maxHp:100,lives:100,ammo:8,rockets:12,drones:3,score:0,enemies:[{x:8.5,y:7.5,hp:39}],hostile:[],missiles:[],pickups:[]};
assert.equal(check(base),true,'normal persisted campaign must remain resumable');
assert.equal(check({...base,mission:0,objective:{done:2,hold:0,bossDefeated:false}}),true,'completed activation mission must remain resumable');
assert.equal(check({...base,mission:1,objective:{done:1,hold:22,bossDefeated:false}}),true,'completed defense timer must remain resumable');
for(const [label,bad] of [
 ['saved player inside crate wall',{x:3.5,y:3.5}],['saved player inside mission barrier',{mission:1,x:7.5,y:4.5}],['zero-health resume',{hp:0}],['bad hero',{hero:999}],['negative hero',{hero:-1}],['nonfinite x',{x:Infinity}],['bad health',{hp:200}],['negative lives',{lives:-2}],['impossible ammo',{ammo:999}],['nonfinite score',{score:NaN}],['out-of-bounds mission',{mission:6}],['endless campaign',{endless:true}],['invalid enemy',{enemies:[{x:NaN,y:7.5,hp:39}]}],['too many enemies',{enemies:Array(21).fill({x:8,y:8,hp:39})}],['invalid missiles',{missiles:{}}],
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

const cleanup=slice('function cleanSavedProjectiles(', 'function restore(){');
const cleanupFns=vm.runInNewContext(cleanup+'({cleanSavedProjectiles,cleanSavedPickups})');
const goodHostile={x:5,y:7,vx:4.2,vy:0,life:4,hp:14};
const goodMissile={x:2.5,y:7.5,vx:7.5,vy:0,life:2.5,targetUid:1};
assert.equal(cleanupFns.cleanSavedProjectiles([goodHostile],100,'hostile').length,1,'legitimate hostile projectile must survive resume');
assert.equal(cleanupFns.cleanSavedProjectiles([goodMissile],50,'missile').length,1,'legitimate player missile must survive resume');
assert.equal(cleanupFns.cleanSavedProjectiles([{...goodHostile,vx:1e100},goodHostile],100,'hostile').length,1,'extreme velocity must not corrupt physics');
assert.equal(cleanupFns.cleanSavedProjectiles([{...goodMissile,x:-50}],50,'missile').length,0,'off-map missiles must be removed');
assert.equal(cleanupFns.cleanSavedProjectiles([{...goodHostile,hp:-999}],100,'hostile').length,0,'negative projectile damage must be rejected');
assert.equal(cleanupFns.cleanSavedProjectiles([{...goodMissile,life:Infinity}],50,'missile').length,0,'infinite projectile lifetime must be rejected');
assert.equal(cleanupFns.cleanSavedPickups([{x:8.5,y:7.5,life:3600,type:'mission-intel'}]).length,1,'mission intel must survive resume');
assert.equal(cleanupFns.cleanSavedPickups([{x:8.5,y:7.5,life:22,type:'ammo'}]).length,1,'normal ammo must survive resume');
assert.equal(cleanupFns.cleanSavedPickups([{x:8.5,y:7.5,life:22,type:'script'}]).length,0,'unknown pickup types must not enter gameplay');
assert.equal(cleanupFns.cleanSavedPickups([{x:8.5,y:7.5,life:1e20,type:'health'}]).length,0,'invalid pickup lifetime must be removed');
assert(src.includes('world.hostile=cleanSavedProjectiles('),'resume must sanitize enemy projectiles');
assert(src.includes('world.missiles=cleanSavedProjectiles('),'resume must sanitize guided missiles');
assert(src.includes('world.pickups=cleanSavedPickups('),'resume must sanitize pickups');

// Exercise the production key handler rather than only asserting source text.
const keyHandler=slice('function handleGameKeydown(e){',"addEventListener('keydown',handleGameKeydown);");
const keyboard=vm.runInNewContext(
 "let screen='game',fireHeld=false;const keys={};const calls={rocket:0,drone:0,special:0,reload:0,interact:0,pause:0};"+
 "const $=()=>({click(){calls.pause++}});"+
 "function launchRocket(){calls.rocket++}function droneStrike(){calls.drone++}"+
 "function special(){calls.special++}function reload(){calls.reload++}"+
 "function interactObjective(){calls.interact++}"+
 keyHandler+"({handleGameKeydown,keys,calls,setScreen:s=>screen=s,getFire:()=>fireHeld})"
);
const event=(code,repeat=false,target={tagName:'BODY'})=>({code,repeat,target,preventDefault(){this.prevented=true}});
keyboard.handleGameKeydown(event('KeyQ'));
keyboard.handleGameKeydown(event('KeyQ',true));
assert.equal(keyboard.calls.rocket,1,'held rocket shortcut must fire only once');
keyboard.handleGameKeydown(event('KeyE'));
keyboard.handleGameKeydown(event('KeyE',true));
assert.equal(keyboard.calls.drone,1,'held drone shortcut must fire only once');
keyboard.handleGameKeydown(event('KeyF'));
keyboard.handleGameKeydown(event('KeyF',true));
assert.equal(keyboard.calls.special,1,'held special shortcut must fire only once');
const space=event('Space');keyboard.handleGameKeydown(space);
assert.equal(space.prevented,true,'Space must not scroll the page while playing');
assert.equal(keyboard.getFire(),true,'Space must still hold primary fire');
keyboard.setScreen('home');
keyboard.handleGameKeydown(event('KeyQ'));
assert.equal(keyboard.calls.rocket,1,'home screen must not spend rockets');
keyboard.setScreen('game');
keyboard.handleGameKeydown(event('KeyQ',false,{tagName:'BUTTON'}));
assert.equal(keyboard.calls.rocket,1,'focused UI buttons must keep native keyboard behavior');
keyboard.handleGameKeydown(event('Escape'));
assert.equal(keyboard.calls.pause,1,'Escape must still pause active play');

console.log('RAMADAN_RUNTIME_INTEGRITY_PASS save-validation=13 stable-missiles controls visibility');

// Privacy modes can throw SecurityError on every storage operation.
const storageSource=slice('const storage={','let hero=');
const deniedStorage=new Proxy({}, {get(){throw new Error('SecurityError')}});
const blocked=vm.runInNewContext(storageSource+'storage',{localStorage:deniedStorage});
assert.equal(blocked.get('rwHero'),null,'privacy mode hero preference falls back safely');
assert.doesNotThrow(()=>blocked.set('rwHero',3),'privacy mode hero selection remains playable');
assert.doesNotThrow(()=>blocked.remove('rwNativeCampaign'),'privacy mode completion must not crash');
const values=new Map();
const allowed=vm.runInNewContext(storageSource+'storage',{localStorage:{
  getItem:key=>values.get(key)??null,
  setItem:(key,value)=>values.set(key,value),
  removeItem:key=>values.delete(key)
}});
allowed.set('rwHero',5);
assert.equal(allowed.get('rwHero'),'5','normal storage preserves hero choice');
allowed.remove('rwHero');
assert.equal(allowed.get('rwHero'),null,'normal storage supports cleanup');


// Mobile runtime regression: second fingers must not steal the joystick and zero-width layouts stay finite.
const stickSource=slice("const stick=$('#stick'),knob=$('#knob');","let aimY=0;");
const mobile=vm.runInNewContext(
 "let screen='game',joyId=null,joyF=0,joyS=0;"+
 "const knob={style:{transform:''}};"+
 "const stick={captures:[],getBoundingClientRect(){return {left:0,top:0,width:0,height:0}},setPointerCapture(id){this.captures.push(id)}};"+
 "const $=id=>id==='#stick'?stick:knob;"+
 stickSource+"({stick,knob,get:()=>({joyId,joyF,joyS}),setScreen:s=>screen=s})"
);
const touch=(pointerId,clientX=10,clientY=5)=>({pointerId,clientX,clientY});
mobile.stick.onpointerdown(touch(1));
assert.equal(mobile.get().joyId,1,'first finger must own the mobile joystick');
assert.ok(Number.isFinite(mobile.get().joyF)&&Number.isFinite(mobile.get().joyS),
 'zero-width mobile layout must never create NaN or Infinity steering');
mobile.stick.onpointerdown(touch(2));
assert.equal(mobile.get().joyId,1,'second finger must not hijack active joystick ownership');
assert.deepEqual(Array.from(mobile.stick.captures),[1],'only the first finger may capture the joystick');
mobile.stick.onpointerup(touch(2));
assert.equal(mobile.get().joyId,1,'unrelated finger release must not stop movement');
mobile.stick.onpointerup(touch(1));
assert.equal(mobile.get().joyId,null,'owner release must clear joystick ownership');
assert.equal(mobile.get().joyF,0,'owner release must clear forward steering');
assert.equal(mobile.get().joyS,0,'owner release must clear lateral steering');
mobile.setScreen('pausePanel');
mobile.stick.onpointerdown(touch(3));
assert.equal(mobile.get().joyId,null,'paused gameplay must not acquire joystick control');
console.log('RAMADAN_JOYSTICK_OWNERSHIP_PASS: multitouch isolation, finite axes, pause safety');
