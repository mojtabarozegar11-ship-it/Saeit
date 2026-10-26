import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isInteractiveTarget, keyboardAction} from '../../games/ramadan-war/input-guard.mjs';

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
