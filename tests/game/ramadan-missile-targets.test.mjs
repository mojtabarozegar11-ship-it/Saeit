import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {removeEnemyAndRetargetMissiles} from '../../games/ramadan-war/missile-targets.mjs';

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
  assert.match(game,/import \{removeEnemyAndRetargetMissiles\} from '\.\/missile-targets\.mjs'/);
  assert.match(game,/removeEnemyAndRetargetMissiles\(world\.enemies,world\.missiles,i\)/);
  assert.match(deploy,/ASSETS=\[[^\n]*'missile-targets\.mjs'/);
  assert.match(deploy,/b'\.\/missile-targets\.mjs' in new\['game\.js'\]/);
});
