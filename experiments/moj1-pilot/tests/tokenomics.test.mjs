import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const spec = JSON.parse(readFileSync(new URL('../tokenomics.json', import.meta.url), 'utf8'));
const token = readFileSync(new URL('../contracts/MojCoin.sol', import.meta.url), 'utf8');
const nft = readFileSync(new URL('../contracts/MojAssets.sol', import.meta.url), 'utf8');

test('all allocations equal exactly the fixed supply', () => {
  assert.equal(spec.allocation.reduce((sum, item) => sum + item.percent, 0), 100);
  assert.equal(spec.allocation.reduce((sum, item) => sum + item.tokens, 0), spec.totalWholeTokens);
  for (const item of spec.allocation) assert.equal(item.tokens * 100, item.percent * spec.totalWholeTokens);
});

test('testnet-only provisional design and source guardrails', () => {
  assert.equal(spec.status, 'PROVISIONAL_TESTNET_ONLY');
  assert.equal(spec.fixedSupply, true);
  assert.ok(spec.mainnetBlockers.length >= 5);
  assert.match(token, /MAX_SUPPLY\s*=\s*100_000_000_000/);
  assert.equal(spec.name, 'Moj 1');
  assert.equal(spec.symbol, 'MOJ1');
  assert.equal(spec.totalWholeTokens, 100_000_000_000);
  assert.equal(spec.ownerApproval.nameApproved, true);
  assert.equal(spec.ownerApproval.symbolApproved, true);
  assert.equal(spec.ownerApproval.supplyApproved, true);
  assert.equal(spec.ownerApproval.allocationApproved, false);
  assert.equal(spec.ownerApproval.mainnetReleaseApproved, false);
  assert.doesNotMatch(token, /function\s+mint\s*\(/);
  assert.match(nft, /onlyOwner/);
  assert.match(nft, /MAX_ITEMS\s*=\s*10_000/);
});
