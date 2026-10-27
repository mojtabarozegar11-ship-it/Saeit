// Regression: the mobile pad must match WASD directions, not rotate controls 90 degrees.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');

(async () => {
  const {joystickAxes} = await import('./input-guard.mjs');
  const close = (a, b) => assert(Math.abs(a - b) < 1e-9, `expected ${b}, got ${a}`);
  const check = (dx, dy, forward, side) => {
    const value = joystickAxes(dx, dy, 50);
    close(value.forward, forward);
    close(value.side, side);
  };

  check(0, -50, 1, 0);   // up -> W / forward
  check(0, 50, -1, 0);   // down -> S / reverse
  check(50, 0, 0, 1);    // right -> D / strafe right
  check(-50, 0, 0, -1);  // left -> A / strafe left
  check(0, 0, 0, 0);     // released pad -> stationary
  check(0, -100, 1, 0); // beyond pad -> no speed boost
  check(100, -100, Math.SQRT1_2, Math.SQRT1_2); // diagonal normalized
  for (const bad of [NaN, Infinity, -Infinity]) {
    assert.deepEqual(joystickAxes(bad, 10, 50), {forward: 0, side: 0});
    assert.deepEqual(joystickAxes(10, bad, 50), {forward: 0, side: 0});
    assert.deepEqual(joystickAxes(10, 10, bad), {forward: 0, side: 0});
  }
  assert.deepEqual(joystickAxes(10, 10, 0), {forward: 0, side: 0});

  // Fail if the production handler silently regresses to the old x->forward mapping.
  const game = readFileSync(join(__dirname, 'game.js'), 'utf8');
  assert.match(game, /joystickAxes\(x,y,lim\)/);
  assert.match(game, /joyF=axes\.forward;joyS=axes\.side/);
  assert.doesNotMatch(game, /joyF=x\/lim;joyS=y\/lim/);
  console.log('RAMADAN_JOYSTICK_AXES_PASS directions=4 diagonal=normalized invalid=neutral integration=wired');
})().catch(error => {console.error(error);process.exitCode = 1;});
