'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { quote, money, formatSun, getTronState } = require('./app.js');

test('fee uses exact integer cents at 0.1%', () => {
  assert.deepEqual(quote('1000.00'), { fee: 100n, net: 99900n });
  assert.deepEqual(quote('1999.99'), { fee: 200n, net: 199799n });
  assert.deepEqual(quote('5.00'), { fee: 1n, net: 499n });
  assert.deepEqual(quote('4.99'), { fee: 0n, net: 499n });
  assert.equal(money(199799n), '$1,997.99');
});

test('fee rejects malformed, negative and excessive decimal amounts', () => {
  for (const bad of ['-1', '0.001', '1e3', '1,000', 'Infinity', 'NaN', '01', '1000000000000']) {
    assert.throws(() => quote(bad));
  }
});

test('TRON SUN precision is preserved without floats', () => {
  assert.equal(formatSun('0'), '0 TRX');
  assert.equal(formatSun('1'), '0.000001 TRX');
  assert.equal(formatSun('1234567'), '1.234567 TRX');
  assert.equal(formatSun('1000000'), '1 TRX');
  assert.equal(formatSun('123456789012345678'), '123456789012.345678 TRX');
  assert.throws(() => formatSun('-1'));
});

test('TRON wallet requests permission and reads only native balance', async () => {
  const calls = [];
  const address = 'TMockAddressForControlledReadOnlyUnitTest';
  const wallet = {
    request: async ({ method }) => {
      calls.push(method);
      return [address];
    },
    tronWeb: {
      ready: true,
      defaultAddress: { base58: address },
      isAddress: input => input === address,
      trx: {
        getBalance: async input => {
          assert.equal(input, address);
          calls.push('getBalance');
          return '1234567';
        }
      }
    }
  };
  assert.deepEqual(await getTronState(wallet), { address, balance: '1.234567 TRX' });
  assert.deepEqual(calls, ['eth_requestAccounts', 'getBalance']);
});

test('TRON wallet fails closed when account changes mid-read', async () => {
  const wallet = {
    request: async () => ['TOriginalAddress'],
    tronWeb: {
      ready: true,
      defaultAddress: { base58: 'TOriginalAddress' },
      isAddress: () => true,
      trx: {
        getBalance: async () => {
          wallet.tronWeb.defaultAddress.base58 = 'TDifferentAddress';
          return '1000000';
        }
      }
    }
  };
  await assert.rejects(getTronState(wallet), /Wallet changed/);
});

test('TRON wallet refuses unavailable or invalid providers', async () => {
  await assert.rejects(getTronState(null), /compatible TRON wallet/);
  await assert.rejects(getTronState({ request: async () => [], tronWeb: false }), /not ready/);
});
