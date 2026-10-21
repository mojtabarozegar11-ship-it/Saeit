// Local disposable TVM only. Construct and sign, but NEVER broadcast.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {TronWeb} from 'tronweb';
import {fingerprintRawTransaction, normalizedTronAddress} from './deployment-reconciler.mjs';

const key = process.env.LOCAL_PRIVATE_KEY;
if (!/^[0-9a-f]{64}$/i.test(key ?? '')) {
  throw new Error('LOCAL_PRIVATE_KEY must be an isolated disposable TVM key');
}
const tronWeb = new TronWeb({fullHost: 'http://127.0.0.1:9090', privateKey: key});
const artifact = JSON.parse(await readFile(
  new URL('../build/contracts/MojAssets.json', import.meta.url), 'utf8'));
const governance = tronWeb.defaultAddress.base58;
const ctor = artifact.abi.find(item => item.type === 'constructor');
assert.equal(ctor.inputs.length, 1);
const unsigned = await tronWeb.transactionBuilder.createSmartContract({
  abi: artifact.abi, bytecode: artifact.bytecode.replace(/^0x/, ''),
  name: 'MojAssets', feeLimit: 1_000_000_000,
  callValue: 0, userFeePercentage: 100, originEnergyLimit: 10_000_000,
  funcABIV2: ctor, parametersV2: [governance]
}, governance);
assert.match(unsigned.txID, /^[a-f0-9]{64}$/i);
assert.match(normalizedTronAddress(unsigned.contract_address, tronWeb), /^41[a-f0-9]{40}$/);
const signed = await tronWeb.trx.sign(unsigned);
assert.equal(signed.txID, unsigned.txID);
assert.ok(signed.signature?.length);
assert.equal(signed.raw_data_hex, unsigned.raw_data_hex);
assert.match(fingerprintRawTransaction(signed.raw_data_hex), /^[a-f0-9]{64}$/);
console.log('MOJ1_TVM_TRANSACTION_BUILD_SIGN=PASS; BROADCAST=NEVER');
