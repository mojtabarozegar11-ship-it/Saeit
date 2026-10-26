'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=fs.readFileSync('games/ramadan-war/game.js','utf8');
const start=source.indexOf('function special(){');
const end=source.indexOf('function tick(dt){',start);
assert.ok(start>=0&&end>start,'real hero ability handler must be present');
const ability=source.slice(start,end);
const harness=vm.runInNewContext(
  "let world=null,screen='game',saves=0;const messages=[];"+
  "function toast(message){messages.push(message)}function sync(){}function save(){saves++}"+
  "function targetAim(){return world.enemies[0]||null}"+
  "function nearest(){return world.enemies[0]||null}"+
  ability+
  "({special,setWorld(w){world=w},setScreen(s){screen=s},getSaves(){return saves},messages})",
  {Math}
);
const makeWorld=hero=>({
  hero,skillTimer:0,skillFired:false,shield:0,hp:40,maxHp:100,
  x:0,y:0,freeze:0,drones:0,strikeTimer:0,strikeX:0,strikeY:0,
  missionPassed:false,hostile:[{x:1,y:0,life:4}],
  enemies:[{x:1,y:0,hp:410,life:1.5}]
});
const shield=makeWorld(0);harness.setWorld(shield);harness.special();
assert.equal(shield.shield,12,'energy shield must protect for twelve seconds');
const emp=makeWorld(1);harness.setWorld(emp);harness.special();
assert.equal(emp.enemies[0].stun,3.5,'EMP must stun rather than kill enemies');
assert.equal(emp.hostile.length,0,'EMP must neutralize incoming hostile fire');
assert.equal(emp.enemies[0].hp,410,'EMP must not grant free boss kills');
const repair=makeWorld(2);harness.setWorld(repair);harness.special();
assert.equal(repair.hp,95,'armor repair must restore health');
const storm=makeWorld(3);harness.setWorld(storm);harness.special();
assert.ok(storm.enemies[0].hp<410&&storm.enemies[0].hp>0,'pulse storm must deal finite area damage');
assert.equal(storm.hostile.length,0,'pulse storm must clear nearby enemy bullets');
const time=makeWorld(4);harness.setWorld(time);harness.special();
assert.equal(time.freeze,5,'time-stop must freeze enemy time rather than kill opponents');
assert.equal(time.enemies[0].life,1.5,'time-stop must preserve the enemy attack timer');
const orbital=makeWorld(5);harness.setWorld(orbital);harness.special();
assert.equal(orbital.strikeTimer,1.15,'orbital support must schedule a targeted strike');
assert.equal(orbital.drones,0,'hero orbital support must not secretly spend inventory drones');
assert.equal(orbital.strikeX,1);
const noTarget=makeWorld(5);noTarget.enemies=[];harness.setWorld(noTarget);harness.special();
assert.equal(noTarget.skillTimer,0,'failed orbital lock must not consume the cooldown');
assert.equal(noTarget.skillFired,false,'failed orbital lock must not count as a used ability');
const paused=makeWorld(0);harness.setWorld(paused);harness.setScreen('pausePanel');harness.special();
assert.equal(paused.skillTimer,0,'abilities must not fire while paused');
assert.ok(source.includes('world.freeze=Math.max(0,world.freeze-dt)'),'time-stop must expire');
assert.ok(source.includes('if(world.freeze>0||(e.stun||0)>0)'),'frozen or stunned enemies must not move or attack');
assert.ok(source.includes('if(world.freeze>0)continue;const nx='),'hostile bullets must freeze');
assert.ok(source.includes('if(world.freeze<=0&&world.enemyTimer<=0'),'enemy spawning must pause during time-stop');
assert.ok(source.includes('e.stun=Number.isFinite(e.stun)?clamp(e.stun,0,3.5):0'),'restored enemy stun must be sanitized');
assert.ok(source.includes("$('#pause').onclick=()=>pauseOnInterruption()"),'manual pause must release held controls');
assert.ok(source.includes("function launchRocket(){if(screen!=='game'"),'rockets cannot be spent from paused UI');
assert.ok(source.includes("function droneStrike(){if(screen!=='game'"),'drones cannot be spent from paused UI');
console.log('RAMADAN_HERO_SKILLS_PASS six distinct abilities, pause safety, cooldown and time-stop integrity');
