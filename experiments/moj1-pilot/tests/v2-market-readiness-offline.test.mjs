import test from 'node:test';
import assert from 'node:assert/strict';
import { assessV2MarketGate, isValidTronAddress } from '../scripts/v2-market-readiness-offline.mjs';

function fixtures() {
  return {
    policy: {
      fixedSupply:true, decimals:18, totalWholeTokens:100000000000,
      ownerApproval: {
        releaseScheduleApproved:false, beneficiariesApproved:false,
        multisigApproved:false, mainnetReleaseApproved:false,
      },
      allocation: [
        {bucket:'player_rewards_and_ecosystem', percent:35, tokens:35000000000},
        {bucket:'product_and_security_development', percent:20, tokens:20000000000},
        {bucket:'future_liquidity_reserve', percent:15, tokens:15000000000},
        {bucket:'team_and_contributors', percent:10, tokens:10000000000},
        {bucket:'partners_and_creators', percent:15, tokens:15000000000},
        {bucket:'contingency_and_audit_reserve', percent:5, tokens:5000000000},
      ],
    },
    v1: {
      network:'Shasta',chain_scope:'TESTNET_ONLY',
      token_contract:'TKg1oVb91qHzeLC74djmeeAnMMmb9PYJ6F',
      allocation_distributed:false,public_sale_enabled:false,
      real_payment_enabled:false,mainnet_deployed:false,
    },
    v2: {
      project:'MOJ1',version:'V2_GUARDED_CANDIDATE',
      network:'Shasta',chain_scope:'TESTNET_ONLY',contractStandard:'TRC-20',
      candidate_token_contract:'TA8dcG3b9GByaY9vZ1LVjsFohZrZ4CveAY',
      candidate_genesis_factory:'TCBNLE1ZgEcAWXRZ6jjYPSyUH7WiHpLyBm',
      pilot_governance_contract:'TPvMW5cSHKfCuttghjWqmUEScH33vaA1Yy',
      previous_V1_token_testnet:'TKg1oVb91qHzeLC74djmeeAnMMmb9PYJ6F',
      distribution_enabled:false,public_sale_enabled:false,real_payment_enabled:false,
      mainnet_deployed:false,total_supply_whole:'100000000000',
      escrow_balance_whole:'100000000000',
      source_audit_anchor_commit:'4411b28325be44c54d7917b4c67786348521b6a9',
      independent_security_audit:'PENDING',production_custody:'PENDING',
      legal_market_review:'PENDING',
    },
  };
}

test('current V1/V2 evidence agrees but does not grant Mainnet or market release', () => {
  const {policy,v1,v2}=fixtures();
  const r=assessV2MarketGate(policy,v1,v2);
  assert.equal(r.status,'NO_GO');
  assert.equal(r.marketOrMainnetAuthorized,false);
  assert.equal(r.transactionBroadcast,false);
  assert.deepEqual(r.inconsistencies,[]);
  assert.ok(r.blockers.includes('INDEPENDENT_AUDIT_NOT_ATTESTED'));
  assert.ok(r.blockers.includes('NO_VERIFIED_REAL_USDT_TRX_LIQUIDITY_OR_BUYERS'));
});

test('V2 Mainnet, public sale, real payments or distribution flag fail closed', () => {
  for(const key of ['mainnet_deployed','public_sale_enabled','real_payment_enabled','distribution_enabled']) {
    const {policy,v1,v2}=fixtures(); v2[key]=true;
    const r=assessV2MarketGate(policy,v1,v2);
    assert.ok(r.inconsistencies.includes('V2_TRANSACTION_FLAGS_NOT_CLOSED'),key);
    assert.equal(r.marketOrMainnetAuthorized,false);
  }
});

test('100bn supply and all six exact allocations must match', () => {
  for(const mutate of [
    f=>{f.v2.escrow_balance_whole='99999999999';},
    f=>{f.policy.allocation[0].tokens=35000000001;},
    f=>{f.policy.allocation[1].bucket=f.policy.allocation[0].bucket;},
    f=>{f.policy.allocation.pop();},
  ]) {
    const f=fixtures(); mutate(f);
    const r=assessV2MarketGate(f.policy,f.v1,f.v2);
    assert.ok(r.inconsistencies.length>0);
    assert.equal(r.status,'NO_GO');
  }
});

test('old V1 cannot be mistaken for guarded V2 and audit anchor must stay exact', () => {
  const f=fixtures();
  f.v2.candidate_token_contract=f.v1.token_contract;
  f.v2.source_audit_anchor_commit='untrusted';
  const r=assessV2MarketGate(f.policy,f.v1,f.v2);
  assert.ok(r.inconsistencies.includes('V2_V1_IDENTITY_COLLISION'));
  assert.ok(r.inconsistencies.includes('FROZEN_AUDIT_ANCHOR_MISMATCH'));
});

test('claimed audit and newly toggled owner flags cannot self-authorize a release', () => {
  const f=fixtures();
  f.v2.independent_security_audit='PASS';
  f.policy.ownerApproval.mainnetReleaseApproved=true;
  const r=assessV2MarketGate(f.policy,f.v1,f.v2);
  assert.ok(r.inconsistencies.includes('EXTERNAL_REVIEW_STATUS_NOT_PENDING'));
  assert.ok(r.inconsistencies.includes('UNVERIFIED_OWNER_RELEASE_STATE'));
  assert.equal(r.marketOrMainnetAuthorized,false);
});

test('all recorded Shasta contract addresses have valid TRON Base58Check checksums', () => {
  const {v1,v2} = fixtures();
  for (const address of [
    v1.token_contract, v2.candidate_token_contract,
    v2.candidate_genesis_factory, v2.pilot_governance_contract,
  ]) {
    assert.equal(isValidTronAddress(address), true, address);
  }
  assert.equal(isValidTronAddress('T' + '1'.repeat(33)), false);
  assert.equal(isValidTronAddress('T0' + '1'.repeat(32)), false);
});

test('tampered or duplicate contract addresses fail the V2 market gate closed', () => {
  const modified = fixtures();
  modified.v2.candidate_token_contract =
    modified.v2.candidate_token_contract.slice(0, -1) + '1';
  const invalid = assessV2MarketGate(modified.policy, modified.v1, modified.v2);
  assert.ok(invalid.inconsistencies.includes('TRON_ADDRESS_CHECKSUM_INVALID'));
  assert.equal(invalid.marketOrMainnetAuthorized, false);

  const duplicated = fixtures();
  duplicated.v2.candidate_genesis_factory = duplicated.v2.candidate_token_contract;
  const collision = assessV2MarketGate(duplicated.policy, duplicated.v1, duplicated.v2);
  assert.ok(collision.inconsistencies.includes('TRON_ADDRESS_ROLE_COLLISION'));
  assert.equal(collision.marketOrMainnetAuthorized, false);

  const missing = fixtures();
  delete missing.v2.pilot_governance_contract;
  const noGovernor = assessV2MarketGate(missing.policy, missing.v1, missing.v2);
  assert.ok(noGovernor.inconsistencies.includes('TRON_ADDRESS_CHECKSUM_INVALID'));
});

test('missing manifest rejects without exceptions and without permits', () => {
  const f=fixtures();
  const r=assessV2MarketGate(f.policy,f.v1,null);
  assert.deepEqual(r.inconsistencies,['MISSING_OR_INVALID_INPUT_MANIFEST']);
  assert.equal(r.marketOrMainnetAuthorized,false);
});
