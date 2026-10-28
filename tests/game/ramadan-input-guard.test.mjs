import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isInteractiveTarget, keyboardAction, isKeyboardOrAssistiveClick, isModifiedOrComposingKey, normalizeMovementAxes, recordPointerGestureMovement, shouldFireCanvasClick} from '../../games/ramadan-war/input-guard.mjs';

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
  assert.match(game, /function releaseGameInputs\(\)\{keys=\{\};fireHeld=false;fireId=null;joyId=null;aimId=null;joyF=joyS=0/);
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
  assert.ok(game.includes("$('#fire').onlostpointercapture=endFire"), 'fire release must handle capture loss');
  assert.match(game, /function endFire\(e\)\{if\(!isOwnedGameplayPointer\(fireId,e\.pointerId\)\)return;fireId=null;fireHeld=false\}/, 'only owning pointer releases continuous fire');
});

test('browser modifiers and IME composition never activate game shortcuts', () => {
  const unmodified = {ctrlKey:false, altKey:false, metaKey:false, isComposing:false, keyCode:81};
  assert.equal(isModifiedOrComposingKey(unmodified), false);
  for (const flag of ['ctrlKey','altKey','metaKey','isComposing']) {
    assert.equal(isModifiedOrComposingKey({...unmodified, [flag]:true}), true, flag);
  }
  assert.equal(isModifiedOrComposingKey({...unmodified, keyCode:229}), true, 'IME process key');
  assert.equal(isModifiedOrComposingKey(null), false);
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  const shortcutGuard='if(isModifiedOrComposingKey(e)){keys={};fireHeld=false;return;}';
  assert.ok(game.includes(shortcutGuard), 'modified key guard must release held movement/fire');
  assert.ok(game.indexOf(shortcutGuard) <
    game.indexOf('const action=keyboardAction(e.code,screen,e.target,e.repeat);'),
    'modified/composing keys must release held input before gameplay actions and preventDefault');
  assert.ok(game.includes("addEventListener('compositionstart',()=>{keys={};fireHeld=false});"),
    'IME start must release previously held keyboard movement/fire');
});


test('combined keyboard directions cannot exceed single-axis movement speed', () => {
  const straight = normalizeMovementAxes(1, 0);
  const diagonal = normalizeMovementAxes(1, 1);
  assert.equal(Math.hypot(straight.forward, straight.side), 1);
  assert.ok(Math.abs(Math.hypot(diagonal.forward, diagonal.side) - 1) < 1e-12);
  assert.ok(Math.abs(diagonal.forward - Math.SQRT1_2) < 1e-12);
  assert.ok(Math.abs(diagonal.side - Math.SQRT1_2) < 1e-12);
  assert.deepEqual(normalizeMovementAxes(0.3, -0.4), {forward: 0.3, side: -0.4});
  assert.deepEqual(normalizeMovementAxes(Infinity, 1), {forward: 0, side: 0});
  assert.deepEqual(normalizeMovementAxes(0, NaN), {forward: 0, side: 0});
  assert.equal(Math.hypot(...Object.values(normalizeMovementAxes(-20, 30))) <= 1, true);
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.ok(game.includes('const movement=normalizeMovementAxes(forward,side);forward=movement.forward;side=movement.side;move('), 'normalization is wired into engine movement');
});


test('tablet aiming and mouse drag cannot fire, while primary desktop click still works', () => {
  const mouse = {pointerType:'mouse',finished:true,cancelled:false,moved:0};
  const click = {button:0,detail:1,pointerType:'mouse'};
  const cases = [
    [click,'game',1365,mouse,true,'desktop click'],
    [click,'game',1024,mouse,true,'landscape desktop click'],
    [click,'game',699,mouse,false,'phone-width click'],
    [click,'home',1365,mouse,false,'menu click'],
    [{...click,pointerType:'touch'},'game',1024,mouse,false,'touch-synthesized click'],
    [click,'game',1024,{...mouse,pointerType:'touch'},false,'tablet touch'],
    [click,'game',1024,{...mouse,pointerType:'pen'},false,'pen aim'],
    [click,'game',1365,{...mouse,moved:60},false,'mouse drag'],
    [click,'game',1365,{...mouse,cancelled:true},false,'cancelled pointer'],
    [click,'game',1365,{...mouse,finished:false},false,'unfinished pointer'],
    [{...click,button:2},'game',1365,mouse,false,'right click'],
    [{...click,detail:0},'game',1365,mouse,false,'synthetic click'],
    [{button:0,detail:1},'game',1365,mouse,true,'legacy MouseEvent']
  ];
  for (const [event,screen,width,gesture,expected,label] of cases)
    assert.equal(shouldFireCanvasClick(event,screen,width,gesture),expected,label);
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.match(game,/canvas\.addEventListener\('click',e=>\{const eligible=shouldFireCanvasClick\(e,screen,innerWidth,aimGesture\)/);
  assert.match(game,/aimGesture\.moved=Math\.max\(aimGesture\.moved,Math\.hypot/);
  assert.ok(game.includes("function releaseGameInputs(){keys={};fireHeld=false;fireId=null;joyId=null;aimId=null;joyF=joyS=0;aimGesture=null"));
});


test('pointerup displacement blocks unintended shots even when pointermove was coalesced', () => {
  const click = {button:0, detail:1, pointerType:'mouse'};
  const fresh = () => ({pointerType:'mouse', startX:20, startY:20,
    moved:0, finished:false, cancelled:false});
  const noMoveEvent = fresh();
  recordPointerGestureMovement(noMoveEvent, {clientX:160, clientY:20});
  noMoveEvent.finished = true;
  assert.equal(noMoveEvent.moved, 140);
  assert.equal(shouldFireCanvasClick(click,'game',1366,noMoveEvent), false);

  const stationary = fresh();
  recordPointerGestureMovement(stationary,{clientX:22,clientY:24});
  stationary.finished = true;
  assert.equal(shouldFireCanvasClick(click,'game',1366,stationary), true);

  const outAndBack = fresh();
  recordPointerGestureMovement(outAndBack,{clientX:100,clientY:20});
  recordPointerGestureMovement(outAndBack,{clientX:20,clientY:20});
  outAndBack.finished = true;
  assert.equal(shouldFireCanvasClick(click,'game',1366,outAndBack), false);

  const invalid = fresh();
  recordPointerGestureMovement(invalid,{clientX:NaN,clientY:20});
  invalid.finished = true;
  assert.equal(shouldFireCanvasClick(click,'game',1366,invalid), false);

  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.ok(game.includes("canvas.addEventListener('pointerup',e=>{if(e.pointerId!==aimId)return;recordPointerGestureMovement(aimGesture,e);"), 'release must record final displacement');
  assert.ok(game.slice(game.indexOf("canvas.addEventListener('pointermove'"),game.indexOf("canvas.addEventListener('pointerup'")).includes('recordPointerGestureMovement(aimGesture,e);'), 'move must record displacement');
});
