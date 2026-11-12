/* Moj Coin: authoritative integer-only resource transaction kernel.
 * Server integration must persist the returned state under a row lock;
 * client-supplied balances and rewards are never authoritative.
 */
'use strict';
const MAX = Number.MAX_SAFE_INTEGER;
function integer(value, name) {
  if (!Number.isSafeInteger(value) || value < 0) throw new RangeError(name + ' must be a nonnegative safe integer');
  return value;
}
function normalizedResources(resources) {
  if (!resources || typeof resources !== 'object' || Array.isArray(resources)) throw new TypeError('resources object required');
  const out = Object.create(null);
  for (const [name, amount] of Object.entries(resources)) {
    if (!/^[a-z][a-z0-9_]{0,39}$/.test(name)) throw new TypeError('invalid resource name');
    out[name] = integer(amount, name);
  }
  return out;
}
function transact(resources, costs, rewards) {
  const state = normalizedResources(resources);
  const debit = normalizedResources(costs);
  const credit = normalizedResources(rewards);
  for (const [name, amount] of Object.entries(debit)) {
    if (!Object.hasOwn(state, name) || state[name] < amount) return {ok:false, reason:'INSUFFICIENT_RESOURCE', resource:name};
  }
  const next = Object.assign(Object.create(null), state);
  for (const [name, amount] of Object.entries(debit)) next[name] -= amount;
  for (const [name, amount] of Object.entries(credit)) {
    if (!Object.hasOwn(next, name)) throw new RangeError('unknown reward resource: ' + name);
    if (amount > MAX - next[name]) throw new RangeError('resource overflow: ' + name);
    next[name] += amount;
  }
  return {ok:true, resources:next};
}
function purchaseOnce(state, purchaseId, costs, rewards) {
  if (!state || typeof state !== 'object' || !Array.isArray(state.applied) ||
      !/^[A-Za-z0-9_-]{8,128}$/.test(purchaseId)) throw new TypeError('invalid purchase state/id');
  if (state.applied.includes(purchaseId)) return {ok:false, reason:'DUPLICATE_PURCHASE'};
  const result = transact(state.resources, costs, rewards);
  if (!result.ok) return result;
  return {ok:true, state:{resources:result.resources, applied:[...state.applied, purchaseId]}};
}
const api = {integer, normalizedResources, transact, purchaseOnce};
if (typeof module !== 'undefined' && module.exports) module.exports = api;
