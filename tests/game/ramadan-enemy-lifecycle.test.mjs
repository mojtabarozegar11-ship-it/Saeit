import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {canEnemyAct, restoreEnemyRuntime, advanceHostileProjectile} from '../../games/ramadan-war/enemy-action-policy.mjs';

const enemy = () => ({x:8.5,y:7.5,type:1,hp:30,max:50,life:1.5,strafe:1,pathTimer:.4});

test('only living enemies may move, fire or inflict contact damage', () => {
  assert.equal(canEnemyAct(enemy()), true);
  assert.equal(canEnemyAct({...enemy(),life:-.1}), true, 'negative attack cooldown is normal');
  for (const e of [
    {...enemy(),hp:0}, {...enemy(),hp:-5},
    {...enemy(),life:-5}, {...enemy(),hp:NaN},
    {...enemy(),life:Infinity}, null, {}
  ]) assert.equal(canEnemyAct(e), false, 'defeated/corrupt enemy must be inert');
});

test('legacy transient enemy fields recover without granting kills or health', () => {
  const old = {x:8.5,y:7.5,type:1,hp:25,boss:true};
  const restored = restoreEnemyRuntime(old,0);
  assert.equal(restored,old);
  assert.equal(restored.hp,25);
  assert.equal(restored.boss,true);
  assert.equal(restored.life,1.5);
  assert.equal(restored.max,25);
  assert.equal(restored.strafe,-1);
  assert.equal(restored.pathTimer,0);
  assert.equal(restoreEnemyRuntime(old,0),old,'idempotent');
  const defeated = {hp:-5,life:-5,max:410,strafe:1,pathTimer:2};
  restoreEnemyRuntime(defeated,1);
  assert.equal(canEnemyAct(defeated),false);
  assert.equal(defeated.hp,-5);
  assert.equal(defeated.life,-5,'do not revive a defeated boss');
});

test('runtime guard precedes the movement and attack loop, but not the reward cleanup', () => {
  const client=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(client,/import \{canEnemyAct,restoreEnemyRuntime,advanceHostileProjectile\} from '\.\/enemy-action-policy\.mjs'/);
  assert.match(client,/world\.enemies\.forEach\(\(e,i\)=>restoreEnemyRuntime\(e,i\)\)/);
  assert.match(client,/for\(const e of world\.enemies\)\{if\(!canEnemyAct\(e\)\)continue;let dx=/);
  assert.match(client,/for\(let i=world\.enemies\.length-1;i>=0;i--\)\{const e=world\.enemies\[i\];if\(e\.hp<=0\|\|e\.life< -4\)/);
});

test('reversible deployment manifest includes the imported enemy policy module',()=>{
  const deploy=readFileSync(new URL('../../games/ramadan-war/deploy.py',import.meta.url),'utf8');
  assert.match(deploy,/ASSETS=\[[^\n]*'enemy-action-policy\.mjs'/);
  assert.match(deploy,/b'\.\/enemy-action-policy\.mjs' in new\['game\.js'\]/);
});


test('hostile projectile striking solid cover cannot damage the player behind it', () => {
  const bullet={x:2.9,y:3.5,vx:5,vy:0,life:5,hp:14};
  const player={x:3.1,y:3.5};
  const hit=advanceHostileProjectile(bullet,.04,player,(x,y)=>x===3&&y===3);
  assert.equal(hit,false);
  assert.equal(bullet.life,-1,'wall impact consumes projectile');
  assert.equal(bullet.x,2.9,'do not move through cover');
  assert.equal(advanceHostileProjectile(bullet,.04,player,()=>false),false,'no second hit');
});

test('expired and malformed enemy projectiles never damage or move the player', () => {
  const player={x:3.1,y:3.5};
  for(const patch of [{life:0},{life:-2},{life:.01},{vx:NaN},{life:Infinity}]) {
    const bullet={x:2.9,y:3.5,vx:5,vy:0,life:5,hp:14,...patch};
    assert.equal(advanceHostileProjectile(bullet,.04,player,()=>false),false);
    assert.equal(bullet.life,-1);
  }
});

test('unblocked live enemy projectile hits exactly once, with no duplicate damage', () => {
  const bullet={x:2.9,y:3.5,vx:5,vy:0,life:5,hp:14};
  const player={x:3.1,y:3.5};
  assert.equal(advanceHostileProjectile(bullet,.04,player,()=>false),true);
  assert.equal(bullet.life,-1);
  assert.equal(advanceHostileProjectile(bullet,.04,player,()=>false),false);
});

test('enemy projectile collision policy is called before hurt and old unsafe loop is absent', () => {
  const client=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(client,/if\(advanceHostileProjectile\(b,dt,world,\(x,y\)=>tile\(x,y\)!==0\)\)hurt\(b\.hp\)/);
  assert.doesNotMatch(client,/b\.x\+=b\.vx\*dt;b\.y\+=b\.vy\*dt/);
});
