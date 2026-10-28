'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { quote, money, formatSun, formatTokenUnits, getTronState, getErc20Usdt, getTrc20Usdt } = require('./app.js');

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

test('token amount formatting is exact for large 6-decimal balances', () => {
  assert.equal(formatTokenUnits('1', 6, 'USDT'), '0.000001 USDT');
  assert.equal(formatTokenUnits('123456789012345678', 6, 'USDT'), '123456789012.345678 USDT');
  assert.equal(formatTokenUnits('1230000', 6, 'USDT'), '1.23 USDT');
  assert.throws(() => formatTokenUnits(Number.MAX_SAFE_INTEGER + 2, 6, 'USDT'));
});

test('Ethereum mainnet USDT reads ERC20 using only eth_call', async () => {
  const address = '0x' + 'a'.repeat(40);
  const methods = [];
  const wallet = {
    request: async ({ method, params }) => {
      methods.push(method);
      if (method === 'eth_chainId') return '0x1';
      if (method === 'eth_accounts') return [address];
      if (method === 'eth_call') {
        assert.equal(params[0].to, '0xdac17f958d2ee523a2206206994597c13d831ec7');
        if (params[0].data === '0x313ce567') return '0x06';
        assert.equal(params[0].data, '0x70a08231' + 'a'.repeat(40).padStart(64, '0'));
        return '0x12d687';
      }
      throw Error('Unexpected wallet method');
    }
  };
  assert.equal(await getErc20Usdt(wallet, address), '1.234567 USDT');
  assert.deepEqual(methods, ['eth_chainId', 'eth_call', 'eth_call', 'eth_chainId', 'eth_accounts']);
});

test('Ethereum USDT refuses non-mainnet and unexpected decimals', async () => {
  const address = '0x' + 'b'.repeat(40);
  await assert.rejects(getErc20Usdt({request:async()=> '0x89'},address),/only on Ethereum mainnet/);
  const wallet = { request:async({method,params})=>{
    if(method==='eth_chainId')return '0x1';
    if(method==='eth_call')return params[0].data==='0x313ce567'?'0x12':'0x01';
    return [address];
  }};
  await assert.rejects(getErc20Usdt(wallet,address),/Unexpected USDT contract precision/);
});

test('TRON TRC20 USDT reads official contract without signing', async () => {
  const methods = [];
  const address = 'TReadOnlyWalletAddress';
  const tronWeb = {
    contract: () => ({
      at: async contractAddress => {
        assert.equal(contractAddress,'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t');
        return {
          balanceOf: walletAddress => {
            assert.equal(walletAddress,address);
            methods.push('balanceOf');
            return {call:async()=>({toString:()=> '12345678'})};
          },
          decimals: () => {
            methods.push('decimals');
            return {call:async()=>({toString:()=> '6'})};
          }
        };
      }
    })
  };
  assert.equal(await getTrc20Usdt(tronWeb,address),'12.345678 USDT');
  assert.deepEqual(methods,['balanceOf','decimals']);
});
