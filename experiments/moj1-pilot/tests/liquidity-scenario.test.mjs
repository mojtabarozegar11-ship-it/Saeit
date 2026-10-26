import test from 'node:test';
import assert from 'node:assert/strict';
import { parseUnits, formatUnits, simulateSell } from '../tools/liquidity-scenario.mjs';

test('18-decimal parsing and formatting remain exact', () => {
  assert.equal(formatUnits(parseUnits('100000000000.123456789012345678')), '100000000000.123456789012345678');
  assert.equal(formatUnits(parseUnits('0.000000000000000001')), '0.000000000000000001');
  assert.equal(formatUnits(parseUnits('0')), '0');
});

test('constant-product sell conserves token/quote reserves and decreases price', () => {
  const result = simulateSell({
    tokenReserve: '100', quoteReserve: '100', tokensSold: '10', feeBps: 0,
  });
  assert.equal(result.tokenReserveAfter, '110');
  assert.equal(result.spotQuotePerTokenBefore, '1');
  assert.equal(result.quoteReceived, '9.090909090909090909');
  assert.equal(result.quoteReserveAfter, '90.909090909090909091');
  assert.ok(Number(result.spotQuotePerTokenAfter) < 1);
  assert.equal(result.noOnchainExecution, true);
  assert.equal(result.liveMarketVerified, false);
  assert.equal(result.liquidityProvided, false);
});

test('larger sells and fees reduce effective quote per token', () => {
  const small = simulateSell({ tokenReserve:'100', quoteReserve:'100', tokensSold:'1', feeBps:0 });
  const large = simulateSell({ tokenReserve:'100', quoteReserve:'100', tokensSold:'20', feeBps:0 });
  const withFee = simulateSell({ tokenReserve:'100', quoteReserve:'100', tokensSold:'1', feeBps:30 });
  assert.ok(Number(large.executionQuotePerToken) < Number(small.executionQuotePerToken));
  assert.ok(Number(withFee.quoteReceived) < Number(small.quoteReceived));
});

test('zero liquidity, negative values, excessive fee, overly precise values are rejected', () => {
  const valid = { tokenReserve:'100', quoteReserve:'100', tokensSold:'1' };
  assert.throws(() => simulateSell({ ...valid, tokenReserve:'0' }), /ZERO_RESERVE/);
  assert.throws(() => simulateSell({ ...valid, tokensSold:'-1' }), /AMOUNT_MUST/);
  assert.throws(() => simulateSell({ ...valid, feeBps:10000 }), /INVALID_FEE/);
  assert.throws(() => simulateSell({ ...valid, tokensSold:'0.0000000000000000001' }), /AMOUNT_MUST/);
});

test('fixed supply does not imply a redeemable balance', () => {
  const result = simulateSell({
    tokenReserve:'15000000000', quoteReserve:'10000', tokensSold:'1000000', feeBps:30,
  });
  assert.ok(Number(result.quoteReceived) < 1);
  assert.equal(result.quoteAsset, 'USDT_ASSUMED_FOR_SCENARIO_ONLY');
});
