import test from 'node:test';
import assert from 'node:assert/strict';
import {grantBattleReward, completeMissionOnce, REWARD_LIMITS} from './economy-reward.mjs';

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

test('mission completion pays exactly once even if called twice', () => {
  const state = {mission: 2, score: 450, points: 7, missionPassed: false};
  assert.deepEqual(completeMissionOnce(state), {completed: true, rewardGranted: true});
  assert.deepEqual(completeMissionOnce(state), {completed: false, rewardGranted: false});
  assert.equal(state.points, 8);
  assert.equal(state.missionPassed, true);
});

test('legacy saves with no missionPassed flag can finish safely', () => {
  const state = {mission: 1, score: 100, points: 0};
  assert.deepEqual(completeMissionOnce(state), {completed: true, rewardGranted: true});
  assert.equal(state.missionPassed, true);
  assert.equal(state.points, 1);
});

test('points cap never traps a completed mission', () => {
  const state = {mission: 5, score: 1, points: REWARD_LIMITS.points, missionPassed: false};
  assert.deepEqual(completeMissionOnce(state), {completed: true, rewardGranted: false});
  assert.equal(state.missionPassed, true);
  assert.equal(state.points, REWARD_LIMITS.points);
});

test('endless, invalid and already-completed states cannot earn mission reward', () => {
  for (const changes of [
    {endless: true}, {victory: true}, {gameOver: true}, {mission: 6},
    {missionPassed: true}, {missionPassed: 'yes'}, {score: NaN}
  ]) {
    const state = {mission: 3, score: 100, points: 1, missionPassed: false, ...changes};
    const before = {...state};
    assert.deepEqual(completeMissionOnce(state), {completed: false, rewardGranted: false});
    assert.deepEqual(state, before);
  }
});

test('new stage can earn one additional mission reward after deliberate reset', () => {
  const state = {mission: 0, score: 0, points: 0, missionPassed: false};
  assert.equal(completeMissionOnce(state).completed, true);
  state.mission = 1;
  state.missionPassed = false;
  assert.equal(completeMissionOnce(state).completed, true);
  assert.equal(state.points, 2);
});
