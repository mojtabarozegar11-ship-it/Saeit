import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isInteractiveTarget, keyboardAction, isKeyboardOrAssistiveClick} from '../../games/ramadan-war/input-guard.mjs';

const arena = {closest: () => null};
const menuButton = {closest: selector => selector.includes('button') ? {} : null};
const textEntry = {closest: selector => selector.includes('input') ? {} : null};

test('shortcuts only operate during active gameplay', () => {
  const commands = {KeyQ: 'rocket', KeyE: 'drone', KeyF: 'special',
    KeyR: 'reload', KeyG: 'interact', Space: 'fire', Escape: 'pause'};
  for (const [key, action] of Object.entries(commands)) {
    assert.equal(keyboardAction(key, 'game', arena), action, key);
    for (const screen of ['home', 'pausePanel', 'upgradePanel', 'success', 'victory', 'over']) {
      assert.equal(keyboardAction(key, screen, arena), null, `${screen} / ${key}`);
    }
  }
  assert.equal(keyboardAction('KeyZ', 'game', arena), null);
});

test('menu focus preserves native keyboard and assistive controls', () => {
  assert.equal(isInteractiveTarget(menuButton), true);
  assert.equal(isInteractiveTarget(textEntry), true);
  assert.equal(isInteractiveTarget(arena), false);
  assert.equal(isInteractiveTarget(null), false);
  for (const key of ['Space', 'Escape', 'KeyQ', 'KeyE', 'KeyF', 'KeyR', 'KeyG']) {
    assert.equal(keyboardAction(key, 'game', menuButton), null);
    assert.equal(keyboardAction(key, 'game', textEntry), null);
  }
});

test('held keys do not repeatedly consume finite rockets, drones or abilities', () => {
  for (const key of ['KeyQ', 'KeyE', 'KeyF', 'KeyR', 'KeyG', 'Escape']) {
    assert.equal(keyboardAction(key, 'game', arena, true), null);
  }
  assert.equal(keyboardAction('Space', 'game', arena, true), 'fire');
});

test('all finite-resource actions and reload fail closed outside active gameplay', () => {
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  for (const fn of ['launchRocket', 'droneStrike', 'special', 'reload']) {
    assert.match(game, new RegExp(`function ${fn}\\([^)]*\\)\\{if\\(screen!=='game'\\|\\|!world\\|\\|`));
  }
  assert.match(game, /if\(screen!=='game'\|\|isInteractiveTarget\(e\.target\)\)return/);
  assert.match(game, /keyboardAction\(e\.code,screen,e\.target,e\.repeat\)/);
});

test('focus loss releases sticky movement and fire and pauses the active game', () => {
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.match(game, /function releaseGameInputs\(\)\{keys=\{\};fireHeld=false;joyId=null;aimId=null;joyF=joyS=0/);
  assert.match(game, /addEventListener\('blur',\(\)=>\{releaseGameInputs\(\);if\(screen==='game'\)/);
  assert.match(game, /visibilitychange.*document\.hidden/);
  assert.match(game, /function showScreen\(name\)\{if\(name!=='game'\)releaseGameInputs\(\)/);
});

test('reversible release includes the new browser module and checks its import', () => {
  const deploy = readFileSync(new URL('../../games/ramadan-war/deploy.py', import.meta.url), 'utf8');
  assert.match(deploy, /ASSETS=\[[^\n]*'input-guard\.mjs'/);
  assert.match(deploy, /b'\.\/input-guard\.mjs' in new\['game\.js'\]/);
});


test('keyboard and assistive button activation is accepted without replaying pointer clicks', () => {
  assert.equal(isKeyboardOrAssistiveClick({detail: 0}), true);
  assert.equal(isKeyboardOrAssistiveClick({detail: 1}), false);
  assert.equal(isKeyboardOrAssistiveClick({detail: 2}), false);
  assert.equal(isKeyboardOrAssistiveClick(null), false);
});

test('five HUD buttons preserve pointer activation and gain keyboard or screen-reader activation', () => {
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  for (const id of ['rocket', 'drone', 'special', 'fire', 'interact']) {
    assert.match(game, new RegExp(`\\$\\('#${id}'\\)\\.onpointerdown=`), `${id} pointer control`);
    assert.match(game, new RegExp(`\\$\\('#${id}'\\)\\.onclick=e=>\\{if\\(isKeyboardOrAssistiveClick\\(e\\)\\)`), `${id} keyboard/AT control`);
  }
  assert.match(game, /import \{[^}]*isKeyboardOrAssistiveClick[^}]*\} from '\.\/input-guard\.mjs'/);
});


test('scope toggle state and game feedback are exposed to assistive technology', () => {
  const html = readFileSync(new URL('../../games/ramadan-war/index.html', import.meta.url), 'utf8');
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.match(html, /id="toast"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/);
  assert.match(html, /id="scope"[^>]*aria-pressed="false"/);
  assert.ok(game.includes("$('#scope').setAttribute('aria-pressed',String(scoped))"), 'scope toggles expose state');
  assert.ok(game.includes("$('#scope').setAttribute('aria-pressed','false')"), 'new game resets scope state');
});


test('lost pointer capture releases mobile movement and continuous fire', () => {
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.ok(game.includes("stick.onlostpointercapture=endStick"), 'joystick stops after pointer capture loss');
  assert.ok(game.includes("$('#fire').onlostpointercapture=()=>fireHeld=false"), 'continuous fire stops after capture loss');
});
