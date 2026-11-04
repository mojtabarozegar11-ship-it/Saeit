import test from 'node:test';
import assert from 'node:assert/strict';
import {grantBattleReward, REWARD_LIMITS} from './economy-reward.mjs';

test('combat score and upgrade points increase together', () => {
  const state = {score: 100, points: 3, unrelated: 9};
  assert.equal(grantBattleReward(state, 250, 2), true);
  assert.deepEqual(state, {score: 350, points: 5, unrelated: 9});
});

test('score-only and points-only gameplay awards are valid', () => {
  const state = {score: 0, points: 0};
  assert.equal(grantBattleReward(state, 100), true);
  assert.equal(grantBattleReward(state, 0, 1), true);
  assert.deepEqual(state, {score: 100, points: 1});
});

test('invalid, negative and fractional rewards fail without mutation', () => {
  for (const args of [[-1, 1], [1, -1], [NaN, 1], [Infinity, 0], [1.5, 1], [0, 0]]) {
    const state = {score: 40, points: 5};
    assert.equal(grantBattleReward(state, ...args), false);
    assert.deepEqual(state, {score: 40, points: 5});
  }
});

test('an over-limit award never partially changes score or points', () => {
  const state = {score: REWARD_LIMITS.score - 1, points: 4};
  assert.equal(grantBattleReward(state, 2, 1), false);
  assert.deepEqual(state, {score: REWARD_LIMITS.score - 1, points: 4});
  const other = {score: 20, points: REWARD_LIMITS.points};
  assert.equal(grantBattleReward(other, 100, 1), false);
  assert.deepEqual(other, {score: 20, points: REWARD_LIMITS.points});
});

test('already invalid state is never written', () => {
  for (const state of [null, {score: 0}, {score: 0, points: -1}, {score: NaN, points: 0}]) {
    assert.equal(grantBattleReward(state, 100, 1), false);
  }
});
