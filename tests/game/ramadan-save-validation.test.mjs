import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateCampaignSave, resumeCampaignScreen, readHeroChoice, storageRead, storageWrite, storageRemove} from '../../games/ramadan-war/save-validation.mjs';

const fresh = () => ({
  hero: 0, mission: 0, lives: 100, x: 2.5, y: 7.5, angle: 0,
  hp: 100, maxHp: 100, ammo: 8, magazine: 8, rockets: 12, drones: 3,
  score: 0, points: 0, kills: 0, missionKills: 0, enemies: [],
  hostile: [], missiles: [], pickups: [],
  objective: {done: 0, hold: 0, bossDefeated: false}, endless: false
});

test('accepts an ordinary campaign save and a legacy save without optional arrays', () => {
  assert.equal(validateCampaignSave(fresh()), true);
  const legacy = fresh();
  delete legacy.pickups; delete legacy.hostile; delete legacy.missiles;
  assert.equal(validateCampaignSave(legacy), true);
});
test('rejects broken player positions and numeric progress before engine initialization', () => {
  for (const patch of [
    {x: null}, {x: NaN}, {x: Infinity}, {y: -1}, {angle: '0'},
    {hero: 30}, {mission: 6}, {lives: 0}, {hp: -1},
    {maxHp: 0}, {ammo: 9}, {magazine: 0}, {rockets: -1},
    {drones: 100}, {score: -1}, {score: 1.2}, {points: Infinity}
  ]) assert.equal(validateCampaignSave({...fresh(), ...patch}), false, JSON.stringify(patch));
});
test('rejects invalid enemy routes and oversized or malformed entity arrays', () => {
  const enemy = {x: 8, y: 7, type: 1, hp: 30, route: [6.5, 7.5]};
  assert.equal(validateCampaignSave({...fresh(), enemies: [enemy]}), true);
  for (const enemies of [
    [null], [{...enemy, x: '8'}], [{...enemy, route: 'not-a-route'}],
    [{...enemy, route: [NaN, 3]}], Array(31).fill(enemy)
  ]) assert.equal(validateCampaignSave({...fresh(), enemies}), false);
  for (const patch of [
    {hostile: {}}, {missiles: [null]}, {pickups: [{x: 2, y: 3, life: 20, type: 'unknown'}]},
    {pickups: Array(61).fill({x: 2, y: 3, life: 20, type: 'ammo'})}
  ]) assert.equal(validateCampaignSave({...fresh(), ...patch}), false);
});
test('preserves valid objective progress while refusing corrupted mission completion', () => {
  assert.equal(validateCampaignSave({...fresh(), objective: {done: 2, hold: 18.5, bossDefeated: false}}), true);
  for (const objective of [[], 'done', {done: 999, hold: 0, bossDefeated: false},
    {done: 1, hold: Infinity, bossDefeated: false},
    {done: 1, hold: 0, bossDefeated: 'yes'}])
    assert.equal(validateCampaignSave({...fresh(), objective}), false);
  assert.equal(validateCampaignSave({...fresh(), endless: true}), false);
  assert.equal(validateCampaignSave({...fresh(), gameOver: true}), false);
});

test('reversible release manifest ships and checks every new imported save module', () => {
  const deploy = readFileSync(new URL('../../games/ramadan-war/deploy.py', import.meta.url), 'utf8');
  const client = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.match(client, /import \{validateCampaignSave, resumeCampaignScreen, readHeroChoice, storageRead, storageWrite, storageRemove\} from '\.\/save-validation\.mjs'/);
  assert.match(deploy, /ASSETS=\[[^\n]*'save-validation\.mjs'/);
  assert.match(deploy, /b'\.\/save-validation\.mjs' in new\['game\.js'\]/);
});

test('completed campaign stage resumes to its result panel; ongoing stage resumes to play', () => {
  const active = fresh();
  assert.equal(resumeCampaignScreen(active), 'game');
  assert.equal(resumeCampaignScreen({...active, missionPassed: false}), 'game');
  const cleared = {...active, missionPassed: true};
  assert.equal(validateCampaignSave(cleared), true);
  assert.equal(resumeCampaignScreen(cleared), 'success');
});

test('rejects malformed completion flags and impossible cleared stage with living enemies', () => {
  for (const missionPassed of [null, 'true', 1, [], {}])
    assert.equal(validateCampaignSave({...fresh(), missionPassed}), false);
  const enemy = {x: 8, y: 7, type: 1, hp: 30};
  assert.equal(validateCampaignSave({...fresh(), missionPassed: true, enemies: [enemy]}), false);
});

test('restore branch presents completed stage results instead of trapping player in arena', () => {
  const client = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.match(client, /if\(resumeCampaignScreen\(world\)==='success'\)\{showResult\(/);
  assert.match(client, /showResult\('منطقه پاکسازی شد'/);
  assert.match(client, /showScreen\('game'\);last=performance\.now\(\);requestAnimationFrame\(frame\)/);
});


test('accepts live projectiles and rejects projectiles with invalid movement or damage', () => {
  const hostile = {x: 4, y: 6, life: 3, vx: 2, vy: -3, hp: 8};
  const missile = {x: 2.5, y: 7.5, life: 2, vx: 7.5, vy: 0, targetId: 0};
  assert.equal(validateCampaignSave({...fresh(), hostile: [hostile], missiles: [missile]}), true);
  for (const bad of [{...hostile, vx: undefined}, {...hostile, vy: Infinity},
    {...hostile, hp: '8'}, {...hostile, vx: 1000}]) {
    assert.equal(validateCampaignSave({...fresh(), hostile: [bad]}), false);
  }
  for (const bad of [{...missile, vx: undefined}, {...missile, vy: NaN},
    {...missile, targetId: 30}, {...missile, targetId: '0'}]) {
    assert.equal(validateCampaignSave({...fresh(), missiles: [bad]}), false);
  }
});

test('rejects corrupt saved clocks and drone impact coordinates without breaking legacy saves', () => {
  assert.equal(validateCampaignSave({...fresh(), time: 37.5, enemyTimer: -.5, strikeX: 8, strikeY: 7}), true);
  for (const field of ['time', 'enemyTimer', 'shotTimer', 'reloadTimer', 'comboTimer',
    'rocketTimer', 'droneTimer', 'skillTimer', 'shield', 'strikeTimer', 'hitFlash',
    'explosionTimer', 'muzzle', 'freeze']) {
    assert.equal(validateCampaignSave({...fresh(), [field]: Infinity}), false, field);
    assert.equal(validateCampaignSave({...fresh(), [field]: '0'}), false, field);
  }
  for (const patch of [{strikeX: NaN}, {strikeY: Infinity}, {strikeX: '5'}])
    assert.equal(validateCampaignSave({...fresh(), ...patch}), false);
});

test('corrupt or manipulated hero preference never breaks initial character rendering', () => {
  for (const [input,expected] of [['0',0],['5',5],['29',29],[8,8],[' 2 ',2]])
    assert.equal(readHeroChoice(input),expected,String(input));
  for (const input of [null,undefined,'','30','-1','NaN','Infinity','1e1','3.5',{},[],1/0])
    assert.equal(readHeroChoice(input),0,String(input));
  const game = readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(game,/let hero=readHeroChoice\(storageRead\('rwHero'\)\),world=null/);
});

test('blocked or absent Web Storage cannot crash startup, pause, win or hero selection', () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  try {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true, get() { throw new Error('SecurityError: storage denied'); }
    });
    assert.equal(storageRead('rwHero'), null);
    assert.equal(storageWrite('rwHero', 2), false);
    assert.equal(storageRemove('rwNativeCampaign'), false);
    Object.defineProperty(globalThis, 'localStorage', {configurable: true, value: undefined});
    assert.equal(storageRead('rwWin'), null);
    assert.equal(storageWrite('rwWin', '1'), false);
    assert.equal(storageRemove('rwWin'), false);
    const data = new Map();
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        getItem: key => data.has(key) ? data.get(key) : null,
        setItem: (key, value) => data.set(key, value),
        removeItem: key => data.delete(key)
      }
    });
    assert.equal(storageWrite('rwHero', 7), true);
    assert.equal(storageRead('rwHero'), '7');
    assert.equal(storageRemove('rwHero'), true);
    assert.equal(storageRead('rwHero'), null);
  } finally {
    if (original) Object.defineProperty(globalThis, 'localStorage', original);
    else delete globalThis.localStorage;
  }
});

test('game contains no direct localStorage access outside guarded helpers', () => {
  const game = readFileSync(new URL('../../games/ramadan-war/game.js', import.meta.url), 'utf8');
  assert.doesNotMatch(game, /localStorage/);
  assert.match(game, /storageRead\('rwWin'\)/);
  assert.match(game, /storageWrite\('rwHero',hero\)/);
  assert.match(game, /storageRemove\(saveKey\)/);
});
