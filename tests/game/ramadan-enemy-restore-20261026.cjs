'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('games/ramadan-war/game.js', 'utf8');
const start = source.indexOf('world.enemies.forEach((e,i)=>{');
const end = source.indexOf('});enemySerial=', start);
assert.ok(start >= 0 && end > start, 'checkpoint enemy normalization must exist');
const normalization = source.slice(start, end + 2);
const world = { enemies: [
  { uid: 7, hp: 40, max: 0, type: 99, life: Infinity, hit: NaN, flash: -5, stun: NaN, strafe: NaN },
  { uid: 7, hp: 80, max: 20, type: 3, life: -5, hit: 1, flash: Infinity, stun: 1, strafe: 1 },
  { uid: 9, hp: 30, max: 60, type: 2, life: 2, hit: .5, flash: .25, stun: .5, strafe: -1 }
]};
vm.runInNewContext(normalization, {
  world, seenEnemyIds: new Set(),
  clamp: (value, low, high) => Math.max(low, Math.min(high, value)),
  Number, Math
});
const [legacy, corrupted, valid] = world.enemies;
assert.equal(legacy.max, 40, 'missing/zero max HP must not corrupt health bar');
assert.equal(legacy.type, 0, 'unknown enemy type must normalize');
assert.equal(legacy.life, 1.5, 'nonfinite attack cooldown must normalize');
assert.equal(legacy.hit, 0, 'NaN hit timer must normalize');
assert.equal(legacy.flash, 0, 'negative flash timer must normalize');
assert.equal(legacy.stun, 0, 'NaN stun timer must normalize');
assert.equal(corrupted.max, 80, 'restored max HP must cover current HP');
assert.equal(corrupted.life, 0, 'negative attack timer must clamp');
assert.equal(corrupted.flash, 0, 'infinite flash timer must normalize');
assert.notEqual(corrupted.uid, legacy.uid, 'duplicate enemy IDs must remain unique');
assert.equal(valid.max, 60, 'valid max HP must survive');
assert.equal(valid.type, 2, 'valid enemy type must survive');
assert.equal(valid.life, 2, 'valid attack cooldown must survive');
assert.equal(valid.hit, .5, 'valid hit feedback must survive');
assert.equal(valid.flash, .25, 'valid flash feedback must survive');
console.log('RAMADAN_ENEMY_RESTORE=PASS: legacy HP, attack timers, visuals and identity');
