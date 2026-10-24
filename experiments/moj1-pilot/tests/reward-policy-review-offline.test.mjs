import test from 'node:test';
import assert from 'node:assert/strict';
import {TronWeb} from 'tronweb';
import {reviewSyntheticRewardEvidence as review} from '../scripts/reward-policy-review-offline.mjs';

const wallet = i => TronWeb.address.fromPrivateKey(BigInt(i).toString(16).padStart(64, '0'));
const row = (i, overrides = {}) => ({
  index: String(i), account: wallet(i + 10), subjectTag: 'TEST-SUBJECT-000' + i,
  eventRef: 'TEST-EVENT-000' + i, evidenceRef: 'TEST-EVIDENCE-000' + i,
  sourceType: 'TEST-RESEARCH', amountUnits: '5', ...overrides
});
function sample() {
  return {mode: 'SYNTHETIC_OFFLINE_REVIEW_ONLY', reviewStatus: 'UNREVIEWED',
    policy: {id: 'MOJ1-SYNTHETIC-REWARD-POLICY-DRAFT-1', status: 'DRAFT_UNAPPROVED',
      maxClaimUnits: '10', maxEpochUnits: '20', allowedSourceTypes: ['TEST-GAMEPLAY', 'TEST-RESEARCH']},
    epoch: '20', priorClaims: [], rows: [row(1), row(2)]};
}
const mutate = fn => { const x = sample(); fn(x); return x; };
const flags = x => review(x).riskFlags.join(',');

test('benign synthetic records are deterministic but never approved, funded, or publishable', () => {
  const x = sample(), a = review(x);
  assert.equal(a.riskFlags.length, 0);
  assert.equal(a.status, 'OFFLINE_SYNTHETIC_NO_GO');
  for (const key of ['identityVerified', 'sybilResistanceProven', 'entitlementApproved',
    'chainBalanceVerified', 'auditApproved', 'payoutAuthorized', 'shastaBroadcastAuthorized', 'mainnetAuthorized']) {
    assert.equal(a[key], false, key);
  }
  assert.equal(a.root, undefined);
  x.rows.reverse();
  assert.deepEqual(review(x), a);
});
test('flags two wallets attributed to the same test subject (not a proof of real identity)', () => {
  assert.match(flags(mutate(x => x.rows[1].subjectTag = x.rows[0].subjectTag)), /DUPLICATE_SUBJECT/);
});
test('flags one wallet claimed by two different test subjects', () => {
  assert.match(flags(mutate(x => x.rows[1].account = x.rows[0].account)), /DUPLICATE_WALLET/);
});
test('flags duplicate event evidence and index even when row accounts differ', () => {
  const found = flags(mutate(x => {x.rows[1].eventRef = x.rows[0].eventRef;
    x.rows[1].evidenceRef = x.rows[0].evidenceRef; x.rows[1].index = x.rows[0].index;}));
  for (const kind of ['DUPLICATE_EVENT', 'DUPLICATE_EVIDENCE', 'DUPLICATE_INDEX']) assert.match(found, new RegExp(kind));
});
test('flags repeated event against historical claims and same epoch entity replay', () => {
  const x = sample();
  x.priorClaims = [{epoch: '20', account: wallet(14), subjectTag: x.rows[0].subjectTag, eventRef: x.rows[0].eventRef}];
  const found = flags(x);
  assert.match(found, /EVENT_REPLAY_FROM_HISTORY/);
  assert.match(found, /SUBJECT_REPLAY_IN_EPOCH/);
});
test('flags wallet rotation across epochs for manual review', () => {
  const x = sample();
  x.priorClaims = [{epoch: '19', account: wallet(90), subjectTag: x.rows[0].subjectTag, eventRef: 'TEST-EVENT-HIST01'}];
  assert.match(flags(x), /SUBJECT_WALLET_ROTATION_REVIEW/);
});
test('flags wallet shared by distinct subjects, including cross-epoch history', () => {
  const x = sample();
  x.priorClaims = [{epoch: '19', account: x.rows[0].account, subjectTag: 'TEST-SUBJECT-OTHER', eventRef: 'TEST-EVENT-HIST01'}];
  assert.match(flags(x), /WALLET_SHARED_BY_SUBJECTS/);
});
test('checks per-claim and whole-epoch caps without truncating uint256', () => {
  assert.match(flags(mutate(x => x.rows[0].amountUnits = '11')), /CLAIM_CAP_EXCEEDED/);
  assert.match(flags(mutate(x => {x.rows.push(row(3), row(4), row(5));})), /EPOCH_CAP_EXCEEDED/);
  assert.throws(() => review(mutate(x => x.rows[0].amountUnits = (1n << 256n).toString())), /invalid bound/);
});
test('rejects forged approvals, real-mode input, unknown source and evidence', () => {
  assert.throws(() => review(mutate(x => x.reviewStatus = 'APPROVED')), /prohibited/);
  assert.throws(() => review(mutate(x => x.mode = 'LIVE')), /prohibited/);
  assert.throws(() => review(mutate(x => x.policy.status = 'APPROVED')), /unapproved/);
  assert.throws(() => review(mutate(x => x.rows[0].sourceType = 'LIVE-GAME')), /allowlist/);
  assert.throws(() => review(mutate(x => x.rows[0].evidenceRef = 'REAL-ID-123')), /synthetic/);
});
test('rejects PII, unsolicited fields, malformed amounts, zero amounts and empty batch', () => {
  assert.throws(() => review(mutate(x => x.rows[0].email = 'a@example.com')), /forbidden field/);
  assert.throws(() => review(mutate(x => x.rows[0].ip = '127.0.0.1')), /forbidden field/);
  assert.throws(() => review(mutate(x => x.rows[0].amountUnits = '01')), /canonical/);
  assert.throws(() => review(mutate(x => x.rows[0].amountUnits = '0')), /invalid bound/);
  assert.throws(() => review(mutate(x => x.rows = [])), /limit/);
});
test('canonical Base58 and TRON hex wallets detect the same duplicate', () => {
  const x = mutate(x => x.rows[1].account = TronWeb.address.toHex(x.rows[0].account));
  assert.match(flags(x), /DUPLICATE_WALLET/);
  const y = sample(), hash1 = review(y).reviewSha256;
  y.rows[0].account = TronWeb.address.toHex(y.rows[0].account);
  assert.equal(review(y).reviewSha256, hash1);
});
test('blocks mutated policy, oversized history and noncanonical epoch', () => {
  assert.throws(() => review(mutate(x => x.policy.allowedSourceTypes.push('OTHER'))), /policy/);
  assert.throws(() => review(mutate(x => x.epoch = '020')), /canonical/);
  assert.throws(() => review(mutate(x => x.policy.maxClaimUnits = '21')), /cannot exceed/);
  assert.throws(() => review(mutate(x => x.priorClaims = Array(10001).fill({}))), /limit/);
});
