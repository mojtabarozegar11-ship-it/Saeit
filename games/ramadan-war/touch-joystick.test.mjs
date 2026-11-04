import test from 'node:test';
import assert from 'node:assert/strict';
import { joystickAxes } from './input-guard.mjs';

test('tiny involuntary touch does not move the player', () => {
  assert.deepEqual(joystickAxes(3, 4, 50, .12), {forward: 0, side: 0});
});

test('movement ramps smoothly after the deadzone', () => {
  const halfway = joystickAxes(0, -28, 50, .12);
  assert.ok(Math.abs(halfway.forward - .5) < 1e-9);
  assert.equal(halfway.side, 0);
});

test('full joystick reach retains full speed', () => {
  assert.deepEqual(joystickAxes(50, 0, 50, .12), {forward: 0, side: 1});
});

test('diagonal movement never exceeds one unit', () => {
  const diagonal = joystickAxes(50, 50, 50, .12);
  assert.ok(Math.hypot(diagonal.forward, diagonal.side) <= 1.000001);
});

test('old three-argument joystick behavior remains unchanged', () => {
  assert.deepEqual(joystickAxes(30, 40, 50), {forward: -.8, side: .6});
});

test('invalid input fails closed', () => {
  assert.deepEqual(joystickAxes(NaN, 0, 50, .12), {forward: 0, side: 0});
  assert.deepEqual(joystickAxes(0, -20, 50, Infinity), {forward: 0, side: 0});
});
