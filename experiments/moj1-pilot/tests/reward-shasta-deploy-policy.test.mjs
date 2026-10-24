import test from 'node:test';
import assert from 'node:assert/strict';
import {TronWeb} from 'tronweb';
import {validateShastaRewardPlan as validate,
  SHASTA_REWARD_CONFIRMATION,REWARD_TEST_TOKEN_NAME,REWARD_TEST_TOKEN_SYMBOL}
from '../scripts/reward-shasta-deploy-policy.mjs';

const addr = n => TronWeb.address.fromPrivateKey(BigInt(n).toString(16).padStart(64,'0'));
const manifest = () => ({
  project:'MOJ1',version:'V2_GUARDED_CANDIDATE',network:'Shasta',chain_scope:'TESTNET_ONLY',
  mainnet_deployed:false,distribution_enabled:false,public_sale_enabled:false,
  real_payment_enabled:false,independent_security_audit:'PENDING',
  candidate_token_contract:addr(11),candidate_genesis_factory:addr(12),
  pilot_governance_contract:addr(13)
});
const plan = () => ({
  confirmation:SHASTA_REWARD_CONFIRMATION,network:'Shasta',mode:'DISPOSABLE_TEST_ONLY',
  operatorAddress:addr(20),governanceAddress:addr(13),
  tokenName:REWARD_TEST_TOKEN_NAME,tokenSymbol:REWARD_TEST_TOKEN_SYMBOL,
  feeLimitSun:'500000000'
});

test('accepts only keyless, non-MOJ1 Shasta plan with bounded fee', () => {
  const result=validate(manifest(),plan());
  assert.equal(result.preflightOnly,true);
  assert.equal(result.mainnetAuthorized,false);
  assert.equal(result.fundingAuthorized,false);
  assert.equal(result.rewardClaimAuthorized,false);
  assert.equal(result.rewardEscrowDeployed,false);
  assert.equal(result.maxDeployments,2);
  assert.equal(result.tokenSymbol,'TTEST');
});

test('rejects wrong network, unguarded distributions and claims of audit', () => {
  for (const change of [
    {network:'Mainnet'}, {mainnet_deployed:true}, {distribution_enabled:true},
    {public_sale_enabled:true},{real_payment_enabled:true},
    {independent_security_audit:'COMPLETE'}
  ]) assert.throws(()=>validate({...manifest(),...change},plan()),/SHASTA_LOCK/);
});

test('requires explicit disposable mode and operator, not a generic deploy request',()=>{
  for (const change of [
    {confirmation:'YES'}, {network:'Mainnet'}, {mode:'PUBLIC_REWARDS'},
    {operatorAddress:'not-tron'}, {governanceAddress:'not-tron'}
  ]) assert.throws(()=>validate(manifest(),{...plan(),...change}));
});

test('rejects protected V2 MOJ1 funding, fake labels and arbitrary metadata',()=>{
  for (const change of [
    {tokenName:'Moj 1'}, {tokenSymbol:'MOJ1'},
    {tokenContractAddress:addr(11)}, {rewardEscrowAddress:addr(15)},
    {beneficiaries:['real-person']}, {deployMainnet:true}
  ]) assert.throws(()=>validate(manifest(),{...plan(),...change}));
});

test('pins governor, prevents confusion with existing contracts',()=>{
  assert.throws(()=>validate(manifest(),{...plan(),governanceAddress:addr(18)}),/GOVERNANCE_MUST_MATCH/);
  for (const operatorAddress of [addr(11),addr(12),addr(13)]) {
    assert.throws(()=>validate(manifest(),{...plan(),operatorAddress}),/TEST_OPERATOR_MUST_NOT/);
  }
});

test('fee limit is explicit, bounded and strictly decimal',()=>{
  for (const feeLimitSun of ['0','1','9999999','1000000001','1e9','01',
    '-1000','', '500.5',100000000]) {
    assert.throws(()=>validate(manifest(),{...plan(),feeLimitSun}));
  }
  assert.equal(validate(manifest(),{...plan(),feeLimitSun:'1000000000'}).feeLimitSun,'1000000000');
});

test('missing or mutated protected manifest addresses are rejected',()=>{
  for(const change of [
    {candidate_token_contract:'bad'},
    {pilot_governance_contract:'bad'},
    {candidate_genesis_factory:undefined}
  ]) assert.throws(()=>validate({...manifest(),...change},plan()),/ADDRESS/);
});
