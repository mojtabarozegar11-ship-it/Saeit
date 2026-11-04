import test from 'node:test';
import assert from 'node:assert/strict';
import { joystickAxes, shouldFireCanvasClick } from './input-guard.mjs';

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

// A real mouse remains a valid firing input even when its browser window is narrow.
// Touch and pen aim must not accidentally spend ammunition at any screen size.
const mouseGesture = (overrides = {}) => ({
  pointerType: 'mouse', finished: true, cancelled: false, moved: 2, ...overrides
});
const mouseClick = (overrides = {}) => ({button: 0, detail: 1, pointerType: 'mouse', ...overrides});

test('short desktop mouse click fires in narrow and wide viewports', () => {
  for (const width of [320, 699, 700, 1440]) {
    assert.equal(shouldFireCanvasClick(mouseClick(), 'game', width, mouseGesture()), true);
  }
});

test('touch and pen aiming never fire through canvas click', () => {
  for (const type of ['touch', 'pen']) {
    assert.equal(shouldFireCanvasClick(mouseClick({pointerType: type}), 'game', 900, mouseGesture({pointerType: type})), false);
    assert.equal(shouldFireCanvasClick(mouseClick({pointerType: type}), 'game', 320, mouseGesture({pointerType: type})), false);
  }
});

test('dragged, unfinished, cancelled and missing mouse gestures cannot fire', () => {
  for (const gesture of [
    mouseGesture({moved: 9}), mouseGesture({finished: false}),
    mouseGesture({cancelled: true}), null
  ]) {
    assert.equal(shouldFireCanvasClick(mouseClick(), 'game', 320, gesture), false);
  }
});

test('non-game and non-primary/synthetic clicks cannot fire', () => {
  assert.equal(shouldFireCanvasClick(mouseClick(), 'pause', 320, mouseGesture()), false);
  assert.equal(shouldFireCanvasClick(mouseClick({button: 2}), 'game', 320, mouseGesture()), false);
  assert.equal(shouldFireCanvasClick(mouseClick({detail: 0}), 'game', 320, mouseGesture()), false);
});
