import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {removeEnemyAndRetargetMissiles,missilePathBlocked} from '../../games/ramadan-war/missile-targets.mjs';

test('removing an earlier enemy preserves missile homing on the original surviving target', () => {
  const enemies = [{name:'a'}, {name:'b'}, {name:'c'}];
  const missiles = [{targetId:2}, {targetId:1}, {targetId:0}];
  assert.equal(removeEnemyAndRetargetMissiles(enemies,missiles,0).name,'a');
  assert.deepEqual(enemies.map(e=>e.name),['b','c']);
  assert.deepEqual(missiles.map(m=>m.targetId),[1,0,-1]);
  assert.equal(enemies[missiles[0].targetId].name,'c');
});

test('removing a locked enemy clears only its own missile lock', () => {
  const enemies = [{name:'a'}, {name:'b'}, {name:'c'}];
  const missiles = [{targetId:0}, {targetId:1}, {targetId:2}, {targetId:-1}];
  removeEnemyAndRetargetMissiles(enemies,missiles,1);
  assert.deepEqual(missiles.map(m=>m.targetId),[0,-1,1,-1]);
});

test('multiple removals and legacy index-based saves remain deterministic', () => {
  const enemies = [{name:'a'}, {name:'b'}, {name:'c'}, {name:'d'}];
  const missiles = [{targetId:3}, {targetId:2}, {targetId:1}];
  removeEnemyAndRetargetMissiles(enemies,missiles,2);
  removeEnemyAndRetargetMissiles(enemies,missiles,0);
  assert.deepEqual(enemies.map(e=>e.name),['b','d']);
  assert.deepEqual(missiles.map(m=>m.targetId),[1,-1,0]);
});

test('invalid removal does not mutate active world or missile targets', () => {
  const enemies = [{name:'a'}], missiles = [{targetId:0}];
  for (const index of [-1,1,0.5,NaN]) assert.equal(removeEnemyAndRetargetMissiles(enemies,missiles,index),null);
  assert.equal(enemies.length,1);
  assert.equal(missiles[0].targetId,0);
});

test('game cleanup uses target-preserving removal and reversible deployment includes helper', () => {
  const game = readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  const deploy = readFileSync(new URL('../../games/ramadan-war/deploy.py',import.meta.url),'utf8');
  assert.match(game,/import \{removeEnemyAndRetargetMissiles,missilePathBlocked\} from '\.\/missile-targets\.mjs'/);
  assert.match(game,/removeEnemyAndRetargetMissiles\(world\.enemies,world\.missiles,i\)/);
  assert.match(deploy,/ASSETS=\[[^\n]*'missile-targets\.mjs'/);
  assert.match(deploy,/b'\.\/missile-targets\.mjs' in new\['game\.js'\]/);
});

test('dead enemies cannot absorb aim, sniper hits, rockets or drone inventory', () => {
  const game=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  const names=['targetAim','nearest','visibleAttack','launchRocket','droneStrike'];
  const functions=names.map(name=>{
    const line=game.split('\n').find(row=>row.startsWith('function '+name+'('));
    assert.ok(line,'targeting function '+name+' exists');
    return line;
  }).join('\n');
  const defeated={x:2,y:0,hp:0};
  const world={x:0,y:0,angle:0,enemies:[defeated],rockets:2,rocketTimer:0,
    missiles:[],drones:2,droneTimer:0,missionPassed:false};
  let saves=0;
  const ctx={world,screen:'game',engine:{pitch:()=>-.13},blocked:()=>false,
    toast:()=>{},playTone:()=>{},sync:()=>{},save:()=>{saves++}};
  vm.runInNewContext(functions,ctx);
  assert.equal(ctx.targetAim(13),null);
  assert.equal(ctx.nearest(13),null);
  assert.equal(ctx.visibleAttack(),null);
  ctx.launchRocket();
  assert.equal(world.rockets,2,'rocket is not spent on a defeated enemy');
  assert.equal(world.missiles.length,0);
  assert.equal(ctx.droneStrike(),false);
  assert.equal(world.drones,2,'drone is not spent on a defeated enemy');
  assert.equal(saves,0);
  const active={x:4,y:0,hp:50};
  world.enemies.push(active);
  assert.equal(ctx.targetAim(13),active,'aim ignores closer defeated target');
  assert.equal(ctx.nearest(13),active);
  assert.equal(ctx.visibleAttack(),active,'sniper cannot repeatedly score on dead enemy');
  ctx.launchRocket();
  assert.equal(world.rockets,1);
  assert.equal(world.missiles[0].targetId,1);
  assert.equal(ctx.droneStrike(),true);
  assert.equal(world.drones,1);
  assert.equal(saves,2,'both valid actions persist exactly once');
});

test('homing rockets cannot tunnel through a wall even when endpoint is passable', () => {
  const missile={x:2.9,y:2.9,vx:30,vy:30,life:4,targetId:0};
  assert.equal(missilePathBlocked(missile,.04,(x,y)=>x===3&&y===3),true);
  assert.equal(missile.x,2.9,'collision query does not mutate rocket state');
});

test('a normal unobstructed rocket trajectory remains playable', () => {
  const missile={x:2.5,y:7.5,vx:8,vy:0,life:4,targetId:0};
  assert.equal(missilePathBlocked(missile,.04,()=>false),false);
  assert.equal(missilePathBlocked(missile,.04,(x,y)=>x===2&&y===7),true);
});

test('corrupted rocket velocities and missing collision callback fail closed', () => {
  for(const vx of [NaN,Infinity,100000]) {
    assert.equal(missilePathBlocked({x:2.5,y:7.5,vx,vy:0},.04,()=>false),true);
  }
  assert.equal(missilePathBlocked({x:2.5,y:7.5,vx:8,vy:0},.04,null),true);
});

test('live-target and targetless missiles both use wall policy before moving', () => {
  const game=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  const loop=game.slice(game.indexOf('for(const m of world.missiles){'),game.indexOf('for(let i=world.enemies.length-1;'));
  assert.match(loop,/if\(missilePathBlocked\(m,dt,\(x,y\)=>tile\(x,y\)!==0\)\)/);
  assert.doesNotMatch(loop,/else if\(tile\(\(m\.x\+m\.vx\*dt\)/);
  assert.ok(loop.indexOf('missilePathBlocked(')<loop.indexOf('m.x+=m.vx*dt'),'wall check precedes missile movement');
});
