'use strict';
/* Dedicated real-logic regression, no blockchain, payment or external I/O. */
const assert = require('node:assert/strict');
const {
  transact, transactBatch, purchaseOnce, purchaseSequenceOnce
} = require('./resource_transaction_kernel.js');

const original = Object.freeze({coins:100, wood:5, stone:2, energy:8});
const plan = [
  {costs:{coins:20, wood:2}, rewards:{stone:1}},
  {costs:{stone:3, energy:4}, rewards:{wood:4}},
  {costs:{coins:30, wood:7}, rewards:{energy:5}}
];
const completed = transactBatch(original, plan);
assert.equal(completed.ok, true);
assert.deepEqual({...completed.resources}, {coins:50, wood:0, stone:0, energy:9});
assert.deepEqual({...original}, {coins:100, wood:5, stone:2, energy:8},
  'must not mutate authoritative source state');

const broken = [
  {costs:{coins:20, wood:2}, rewards:{stone:1}},
  {costs:{stone:4}, rewards:{energy:4}}
];
const insufficient = transactBatch(original, broken);
assert.equal(insufficient.ok, false);
assert.equal(insufficient.reason, 'INSUFFICIENT_RESOURCE');
assert.equal(insufficient.step, 1);
assert.equal(insufficient.resource, 'stone');
assert.deepEqual({...original}, {coins:100, wood:5, stone:2, energy:8});

const state = {resources:{...original}, applied:[]};
const first = purchaseSequenceOnce(state,'upgrade_A_009',plan);
assert.equal(first.ok, true);
assert.deepEqual(first.state.applied,['upgrade_A_009']);
assert.deepEqual({...first.state.resources},{coins:50,wood:0,stone:0,energy:9});
assert.deepEqual(state.applied,[]);
const second = purchaseSequenceOnce(first.state,'upgrade_A_009',plan);
assert.deepEqual(second,{ok:false,reason:'DUPLICATE_PURCHASE'});
const failing = purchaseSequenceOnce(state,'upgrade_B_010',broken);
assert.equal(failing.ok,false);
assert.deepEqual(state.applied,[], 'failed multi-step upgrade must not mark purchase');
assert.deepEqual({...state.resources},{...original},
  'failed upgrade must not debit resource state');

for (const badSteps of [[],new Array(33).fill({costs:{},rewards:{}}),null,{},'bad']) {
  assert.throws(() => transactBatch(original,badSteps), RangeError);
}
for (const badStep of [null,[],{}, {costs:{}}, {rewards:{}}, 42]) {
  assert.throws(() => transactBatch(original,[badStep]),TypeError);
}
assert.throws(() => transactBatch(original,[
  {costs:{coins:1},rewards:{phantom:1}}
]),/unknown reward resource/);
assert.throws(() => transactBatch(original,[
  {costs:{coins:1.5},rewards:{}}
]),/safe integer/);
assert.throws(() => transactBatch(
  {coins:Number.MAX_SAFE_INTEGER},
  [{costs:{},rewards:{coins:1}}]
),/overflow/);

const plainSingle=transact({coins:15},{coins:2},{coins:1});
assert.equal(plainSingle.resources.coins,14);
const onceSingle=purchaseOnce({resources:{coins:15},applied:[]},
  'single_2026',{coins:2},{coins:1});
assert.equal(onceSingle.state.resources.coins,14);
assert.equal(purchaseOnce(onceSingle.state,'single_2026',{coins:0},{coins:0}).reason,
  'DUPLICATE_PURCHASE');
console.log('MOJCOIN_ATOMIC_MULTI_STEP_UPGRADE_AND_IDEMPOTENCY=PASS');
