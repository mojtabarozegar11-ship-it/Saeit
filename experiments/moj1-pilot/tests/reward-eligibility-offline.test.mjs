import test from 'node:test';
import assert from 'node:assert/strict';
import {TronWeb} from 'tronweb';
import {buildSyntheticEligibilityProposal, verifyCandidateProof} from '../scripts/reward-eligibility-offline.mjs';

const dummyAddress = i => TronWeb.address.fromPrivateKey(BigInt(i).toString(16).padStart(64, '0'));
function sample() {
  return {
    mode: 'SYNTHETIC_LOCAL_TEST_ONLY', reviewStatus: 'UNREVIEWED',
    domain: {chainId: '0', contractAddress: dummyAddress(4), epoch: '42'},
    budgetUnits: '18', fundedAvailableUnits: '40',
    rows: [
      {index: '2', account: dummyAddress(5), amountUnits: '7', evidenceRef: 'TEST-SYNTH-003'},
      {index: '0', account: dummyAddress(2), amountUnits: '5', evidenceRef: 'TEST-SYNTH-001'},
      {index: '1', account: dummyAddress(3), amountUnits: '6', evidenceRef: 'TEST-SYNTH-002'}
    ]
  };
}
test('3-leaf off-chain roots and proofs are deterministic, internally consistent, non-authorizing', () => {
  const input = sample();
  const result = buildSyntheticEligibilityProposal(input);
  assert.equal(result.claims.length, 3);
  assert.equal(result.budgetUnits, '18');
  assert.equal(result.status, 'OFFLINE_SYNTHETIC_UNREVIEWED');
  assert.equal(result.publicationAuthorized, false);
  assert.equal(result.chainVerified, false);
  assert.equal(result.sybilAndIdentityVerified, false);
  assert.equal(result.transactionBroadcast, false);
  assert.ok(result.root.startsWith('0x') && result.root.length === 66);
  for (const claim of result.claims) {
    assert.equal(verifyCandidateProof(claim.leaf, claim.proof, result.root), true);
    assert.equal(verifyCandidateProof(claim.leaf, claim.proof, '0x' + '00'.repeat(32)), false);
  }
  assert.deepEqual(result.claims.map(x => x.index), ['0', '1', '2']);
  input.rows.reverse();
  assert.deepEqual(buildSyntheticEligibilityProposal(input), result);
  input.domain.epoch = '43';
  assert.notEqual(buildSyntheticEligibilityProposal(input).root, result.root);
});
test('blocks duplicate account, index, evidence, invalid address, manipulated amounts and extra fields', () => {
  const mutation = fn => { const input = sample(); fn(input); return input; };
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows[1].account = x.rows[0].account)), /Duplicate/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows[1].index = x.rows[0].index)), /Duplicate/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows[1].evidenceRef = x.rows[0].evidenceRef)), /Duplicate/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows[1].account = 'Tfake')), /Invalid canonical/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows[1].amountUnits = '6.0')), /canonical decimal/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows[1].amountUnits = '8')), /budget must equal/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows[0].privateKey = 'must-not-accept')), /unsupported field/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows[0].evidenceRef = 'real-world-id')), /Synthetic/);
});
test('fails closed on unfunded epoch, live mode, pre-approved labels, invalid bounds', () => {
  const mutation = fn => {const x = sample(); fn(x); return x;};
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.fundedAvailableUnits = '17')), /Unfunded/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.mode = 'LIVE')), /Only unreviewed/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.reviewStatus = 'APPROVED')), /Only unreviewed/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.domain.chainId = '-1')), /canonical decimal/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.domain.epoch = '01')), /canonical decimal/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.rows = [])), /rows:/);
  assert.throws(() => buildSyntheticEligibilityProposal(mutation(x => x.budgetUnits = '0')), /uint256 bounds/);
});
