// Regression: the mobile pad must match WASD directions, not rotate controls 90 degrees.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');

(async () => {
  const {joystickAxes, canCaptureGameplayPointer} = await import('./input-guard.mjs');
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
  // Multi-touch: a second finger may aim while the first moves, but may not
  // replace the active pointer within either control. Pointer id 0 is valid.
  assert.equal(canCaptureGameplayPointer(null, 0, 'game'), true);
  assert.equal(canCaptureGameplayPointer(null, 3, 'game'), true);
  assert.equal(canCaptureGameplayPointer(0, 3, 'game'), false);
  assert.equal(canCaptureGameplayPointer(3, 3, 'game'), false);
  assert.equal(canCaptureGameplayPointer(null, 3, 'pausePanel'), false);
  assert.equal(canCaptureGameplayPointer(null, -1, 'game'), false);
  assert.equal(canCaptureGameplayPointer(null, NaN, 'game'), false);
  assert.equal(canCaptureGameplayPointer(null, 1.5, 'game'), false);
  assert.match(game, /canCaptureGameplayPointer\(joyId,e\.pointerId,screen\)/);
  assert.match(game, /canCaptureGameplayPointer\(aimId,e\.pointerId,screen\)/);
  assert.match(game, /canvas\.addEventListener\('lostpointercapture'/);
  assert.match(game, /stick\.setPointerCapture\(e\.pointerId\)/);
  // The fire button must reject a second finger without stealing capture.
  const {isOwnedGameplayPointer} = await import('./input-guard.mjs');
  assert.equal(isOwnedGameplayPointer(0, 0), true);
  assert.equal(isOwnedGameplayPointer(2, 2), true);
  assert.equal(isOwnedGameplayPointer(2, 3), false);
  assert.equal(isOwnedGameplayPointer(null, 0), false);
  assert.equal(isOwnedGameplayPointer(-1, -1), false);
  assert.equal(isOwnedGameplayPointer(2, NaN), false);
  assert.match(game, /canCaptureGameplayPointer\\(fireId,e\\.pointerId,screen\\)/);
  assert.match(game, /isOwnedGameplayPointer\\(fireId,e\\.pointerId\\)/);
  assert.match(game, /fireId=null;fireHeld=false/);
  assert.match(game, /function releaseGameInputs\\(\\)\\{keys=\\{\\};fireHeld=false;fireId=null/);
  assert.match(game, /catch\\(_\\)\\{fireId=null;return\\}fireHeld=true;fire\\(\\)/);
  console.log('RAMADAN_JOYSTICK_AXES_PASS directions=4 diagonal=normalized multitouch=capture-isolated fire=pointer-owned lostcapture=handled integration=wired');
})().catch(error => {console.error(error);process.exitCode = 1;});
