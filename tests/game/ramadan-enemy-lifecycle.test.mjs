import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {canEnemyAct, restoreEnemyRuntime} from '../../games/ramadan-war/enemy-action-policy.mjs';

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
  assert.match(client,/import \{canEnemyAct,restoreEnemyRuntime\} from '\.\/enemy-action-policy\.mjs'/);
  assert.match(client,/world\.enemies\.forEach\(\(e,i\)=>restoreEnemyRuntime\(e,i\)\)/);
  assert.match(client,/for\(const e of world\.enemies\)\{if\(!canEnemyAct\(e\)\)continue;let dx=/);
  assert.match(client,/for\(let i=world\.enemies\.length-1;i>=0;i--\)\{const e=world\.enemies\[i\];if\(e\.hp<=0\|\|e\.life< -4\)/);
});

test('reversible deployment manifest includes the imported enemy policy module',()=>{
  const deploy=readFileSync(new URL('../../games/ramadan-war/deploy.py',import.meta.url),'utf8');
  assert.match(deploy,/ASSETS=\[[^\n]*'enemy-action-policy\.mjs'/);
  assert.match(deploy,/b'\.\/enemy-action-policy\.mjs' in new\['game\.js'\]/);
});
