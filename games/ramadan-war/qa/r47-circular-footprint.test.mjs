import test from 'node:test';
import assert from 'node:assert/strict';
import {playerSpaceClear, movePlayerWithCollision} from '../input-guard.mjs';

const oneWall = (x,y) => x === 3 && y === 2;

test('true circular footprint permits safe diagonal corner clearance', () => {
  assert.equal(playerSpaceClear(2.85, 1.85, oneWall), true);
  assert.equal(playerSpaceClear(2.86, 1.86, oneWall), false);
});
test('radius remains solid along a wall face', () => {
  assert.equal(playerSpaceClear(2.8, 2.5, oneWall), false);
  assert.equal(playerSpaceClear(2.78, 2.5, oneWall), true);
});
test('movement sweeps around a wall corner without tunneling', () => {
  const p={x:2.5,y:1.5};
  assert.equal(movePlayerWithCollision(p,.35,.35,oneWall),true);
  assert.equal(playerSpaceClear(p.x,p.y,oneWall),true);
  assert.ok(p.x>2.8 && p.y>1.8,'safe diagonal movement must not be square-clipped');
});
test('invalid or oversized radius fails closed without unbounded tile scanning', () => {
  for (const r of [0,-1,NaN,Infinity,1e9]) assert.equal(playerSpaceClear(2.5,2.5,oneWall,r),false);
});
