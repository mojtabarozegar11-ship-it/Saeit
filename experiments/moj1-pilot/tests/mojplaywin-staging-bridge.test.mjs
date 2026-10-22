import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  validateStagingManifest, makeSyntheticGuestOrder, previewSyntheticCheckout
} from '../staging/mojplaywin-readonly-bridge.mjs';

const manifest = JSON.parse(readFileSync(
  new URL('../shasta-deployment.json', import.meta.url), 'utf8'));
const hash = 'a'.repeat(64);
const contractNames = ['MojPilotGovernance','MojCoin','MojGenesisDistributor','MojAssets'];
const proof = () => ({
  mode: 'MOJ1_SHASTA_PUBLIC_READ_ONLY', status: 'PASS',
  token: manifest.token_contract, escrow: manifest.genesis_escrow,
  governance: manifest.governance_contract, nft: manifest.nft_contract,
  totalWholeTokens: manifest.total_supply_whole,
  escrowFullyFunded: true, distributed: false, mainnet: false,
  privateKeyUsed: false, paymentsModified: false,
  bytecodeEvidence: contractNames.map(contract => ({
    contract, method: contract === 'MojGenesisDistributor' ?
      'ATTESTED_PARENT_PLUS_RUNTIME_MATCH_WITH_VERIFIED_IMMUTABLE_ADDRESS_SLOTS' :
      'CREATION_AND_EXACT_RUNTIME_MATCH',
    runtimeSha256: hash,
    creationSha256: contract === 'MojGenesisDistributor' ? null : hash
  }))
});
const render = (overrides = {}) => previewSyntheticCheckout({
  manifest, order: makeSyntheticGuestOrder(), chainProof: proof(), ...overrides
});

test('testnet-only manifest and synthetic order are accepted', () => {
  assert.equal(validateStagingManifest(manifest), true);
  const out = render();
  assert.equal(out.status, 'PASS');
  assert.equal(out.tokenNetwork, 'Shasta');
  assert.equal(out.orderState, 'NOT_A_REAL_ORDER');
  for (const name of ['paymentEnabled','deliveryEnabled','orderWriteEnabled',
    'mainnetEnabled','keysUsed','realMojPlayWinGatewayChanged']) {
    assert.equal(out[name], false, name);
  }
  assert.equal(out.tokenContract, manifest.token_contract);
  assert.equal('status_paid' in out, false);
});

test('mainnet, sale, distribution and real payment flags are fail-closed', () => {
  const forbidden = [
    ['network','Mainnet'], ['chain_scope','MAINNET'],
    ['rpc','https://api.trongrid.io'], ['mainnet_deployed',true],
    ['public_sale_enabled',true], ['real_payment_enabled',true],
    ['allocation_distributed',true], ['mojplaywin_integration_mode','LIVE'],
    ['total_supply_whole','999'], ['genesis_escrow',manifest.token_contract]
  ];
  for (const [key, value] of forbidden) {
    assert.throws(() => render({manifest: {...manifest,[key]: value}}),
      /MOJ1_STAGING_MANIFEST/, key);
  }
});

test('real-looking paid or positive-ID orders cannot enter bridge', () => {
  const changes = [
    ['status','paid'], ['id',1], ['product_id',42], ['amount_sun',1000000],
    ['usd','17.00'], ['sender','TRealSender'], ['receiver','TRealReceiver'],
    ['claim_sha','secret'], ['txid',hash], ['synthetic',false]
  ];
  for (const [key,value] of changes) {
    assert.throws(() => render({order:{...makeSyntheticGuestOrder(),[key]:value}}),
      /REAL_ORDER_OR_PAYMENT_REJECTED/, key);
  }
  assert.throws(() => render({order:{...makeSyntheticGuestOrder(),extra:'x'}}),
    /ORDER_FIELDS_REJECTED/);
});

test('fail closed for forged, incomplete or wrong-chain evidence', () => {
  const variants = [
    {...proof(),status:'FAIL'}, {...proof(),mainnet:true},
    {...proof(),privateKeyUsed:true}, {...proof(),paymentsModified:true},
    {...proof(),escrowFullyFunded:false}, {...proof(),distributed:true},
    {...proof(),token:manifest.nft_contract}, {...proof(),totalWholeTokens:'0'},
    {...proof(),bytecodeEvidence:[]},
    {...proof(),bytecodeEvidence:[...proof().bytecodeEvidence.slice(0,3),
      {...proof().bytecodeEvidence[3],contract:'MojCoin'}]},
    {...proof(),bytecodeEvidence:[{...proof().bytecodeEvidence[0],runtimeSha256:'bad'},
      ...proof().bytecodeEvidence.slice(1)]}
  ];
  for (const variant of variants) {
    assert.throws(()=>render({chainProof:variant}), /MOJ1_STAGING_/);
  }
});

test('caller order and chain proof remain untouched', () => {
  const order = {...makeSyntheticGuestOrder()};
  const chainProof = proof();
  const before = JSON.stringify({order,chainProof});
  const receipt = render({order,chainProof});
  assert.equal(JSON.stringify({order,chainProof}), before);
  assert.equal(Object.isFrozen(receipt), true);
  assert.equal(receipt.orderId,'MOJ1-READONLY-TEST-ONLY');
});
