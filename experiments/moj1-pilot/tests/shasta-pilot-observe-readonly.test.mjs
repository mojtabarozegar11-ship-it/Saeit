import test from 'node:test';
import assert from 'node:assert/strict';
import {TronWeb} from 'tronweb';
import {observeExistingShastaPilot as observe} from '../scripts/shasta-pilot-observe-readonly.mjs';

const addr = i => TronWeb.address.fromPrivateKey(BigInt(i).toString(16).padStart(64, '0'));
const manifest = () => ({
  project:'MOJ1', version:'V2_GUARDED_CANDIDATE', network:'Shasta', chain_scope:'TESTNET_ONLY',
  mainnet_deployed:false, public_sale_enabled:false, real_payment_enabled:false,
  distribution_enabled:false, independent_security_audit:'PENDING',
  candidate_token_contract:addr(11), candidate_genesis_factory:addr(12),
  pilot_governance_contract:addr(13)
});
const client = () => ({
  trx: {
    getCurrentBlock: async () => ({blockID:'a'.repeat(64), block_header:{raw_data:{number:123456}}}),
    getContract: async () => ({bytecode:'6080604052'})
  }
});
test('reads three guarded V2 candidate contracts without authorizing reward payout or Mainnet', async () => {
  const result = await observe(manifest(),client());
  assert.equal(result.contracts.length,3);
  assert.equal(result.observedBlockNumber,123456);
  assert.equal(result.transactionBroadcast,false);
  assert.equal(result.privateKeyAccessed,false);
  assert.equal(result.rewardClaimsIntegration,'NOT_RUN');
  assert.equal(result.mainnetAuthorized,false);
  assert.equal(result.sourceBytecodeEquivalenceVerified,false);
});
test('rejects Mainnet endpoint, live distribution labels and duplicate contract addresses', async () => {
  const m = manifest();m.network='Mainnet';
  await assert.rejects(observe(m,client()),/Shasta-only/);
  m.network='Shasta';m.distribution_enabled=true;
  await assert.rejects(observe(m,client()),/Shasta-only/);
  m.distribution_enabled=false;m.pilot_governance_contract=m.candidate_token_contract;
  await assert.rejects(observe(m,client()),/Duplicate/);
});
test('rejects invalid chain observations, missing code and malformed manifest addresses', async () => {
  const c=client();c.trx.getCurrentBlock=async()=>({block_header:{raw_data:{number:100}}});
  await assert.rejects(observe(manifest(),c),/block/);
  c.trx.getCurrentBlock=client().trx.getCurrentBlock;
  c.trx.getContract=async()=>({bytecode:''});
  await assert.rejects(observe(manifest(),c),/bytecode/);
  const m=manifest();m.pilot_governance_contract='not-an-address';
  await assert.rejects(observe(m,client()),/pilot_governance_contract/);
});
