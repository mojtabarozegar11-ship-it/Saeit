// MOJ1 reward anti-abuse screening — synthetic evidence ONLY. No keys, PII, RPC, signing or roots.
// DRAFT checks do not establish a unique human or legal entitlement and NEVER authorize a payout.
import {TronWeb} from 'tronweb';
import {createHash} from 'node:crypto';

const UINT256 = (1n << 256n) - 1n;
const POLICY_ID = 'MOJ1-SYNTHETIC-REWARD-POLICY-DRAFT-1';
const SOURCE_TYPES = ['TEST-GAMEPLAY', 'TEST-RESEARCH'];

function exact(value, keys, label) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw Error(label + ': object required');
  const provided = Object.keys(value);
  for (const key of provided) if (!keys.includes(key)) throw Error(label + ': forbidden field ' + key);
  for (const key of keys) if (!Object.hasOwn(value, key)) throw Error(label + ': missing ' + key);
}
function uint(value, label, allowZero = false) {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]*)$/.test(value)) throw Error(label + ': canonical uint256 decimal required');
  const n = BigInt(value);
  if (n > UINT256 || (!allowZero && n === 0n)) throw Error(label + ': invalid bound');
  return n;
}
function tagged(value, label, prefix) {
  const expression = new RegExp('^TEST-' + prefix + '-[A-Z0-9-]{4,64}$');
  if (typeof value !== 'string' || !expression.test(value)) throw Error(label + ': synthetic test identifier required');
  return value;
}
function account(input) {
  if (typeof input !== 'string') throw Error('account: TRON address required');
  const candidate = /^(?:0x)?41[0-9a-fA-F]{40}$/.test(input)
    ? TronWeb.address.fromHex(input.replace(/^0x/, '')) : input;
  if (!TronWeb.isAddress(candidate)) throw Error('account: invalid TRON address');
  const hex = TronWeb.address.toHex(candidate).toLowerCase();
  if (!/^41[0-9a-f]{40}$/.test(hex) || /^410{40}$/.test(hex)) throw Error('account: invalid TRON hex');
  return hex;
}
const rowKey = (epoch, value) => epoch + ':' + value;
function mark(flags, type, index) { flags.add(type + ':' + index); }

export function reviewSyntheticRewardEvidence(input) {
  exact(input, ['mode', 'reviewStatus', 'policy', 'epoch', 'priorClaims', 'rows'], 'input');
  if (input.mode !== 'SYNTHETIC_OFFLINE_REVIEW_ONLY' || input.reviewStatus !== 'UNREVIEWED')
    throw Error('Real, approved or live reward screening is prohibited');
  exact(input.policy, ['id', 'status', 'maxClaimUnits', 'maxEpochUnits', 'allowedSourceTypes'], 'policy');
  if (input.policy.id !== POLICY_ID || input.policy.status !== 'DRAFT_UNAPPROVED' ||
      JSON.stringify(input.policy.allowedSourceTypes) !== JSON.stringify(SOURCE_TYPES))
    throw Error('Only the fixed, unapproved synthetic policy is permitted');
  const maxClaim = uint(input.policy.maxClaimUnits, 'maxClaimUnits');
  const maxEpoch = uint(input.policy.maxEpochUnits, 'maxEpochUnits');
  if (maxClaim > maxEpoch) throw Error('maxClaimUnits cannot exceed maxEpochUnits');
  const epoch = uint(input.epoch, 'epoch', true).toString();
  if (!Array.isArray(input.priorClaims) || input.priorClaims.length > 10000 ||
      !Array.isArray(input.rows) || input.rows.length < 1 || input.rows.length > 10000)
    throw Error('History or batch row limit exceeded');

  const flags = new Set();
  const priorEvents = new Set();
  const priorSubjects = new Map();
  const priorWallets = new Map();
  const history = input.priorClaims.map((r, i) => {
    exact(r, ['epoch', 'account', 'subjectTag', 'eventRef'], 'history ' + i);
    const entry = {
      epoch: uint(r.epoch, 'history epoch', true).toString(),
      account: account(r.account),
      subjectTag: tagged(r.subjectTag, 'subjectTag', 'SUBJECT'),
      eventRef: tagged(r.eventRef, 'eventRef', 'EVENT')
    };
    if (priorEvents.has(entry.eventRef)) mark(flags, 'DUPLICATE_HISTORY_EVENT', i);
    priorEvents.add(entry.eventRef);
    const earlierSubject = priorSubjects.get(entry.subjectTag) ?? [];
    earlierSubject.push(entry);
    priorSubjects.set(entry.subjectTag, earlierSubject);
    const earlierWallet = priorWallets.get(entry.account) ?? [];
    earlierWallet.push(entry);
    priorWallets.set(entry.account, earlierWallet);
    return entry;
  });

  const wallets = new Set(), subjects = new Set(), events = new Set();
  const evidence = new Set(), indices = new Set();
  let total = 0n;
  const rows = input.rows.map((r, i) => {
    exact(r, ['index', 'account', 'subjectTag', 'eventRef', 'evidenceRef', 'sourceType', 'amountUnits'], 'row ' + i);
    const entry = {
      index: uint(r.index, 'row index', true).toString(),
      account: account(r.account),
      subjectTag: tagged(r.subjectTag, 'subjectTag', 'SUBJECT'),
      eventRef: tagged(r.eventRef, 'eventRef', 'EVENT'),
      evidenceRef: tagged(r.evidenceRef, 'evidenceRef', 'EVIDENCE'),
      sourceType: r.sourceType,
      amountUnits: uint(r.amountUnits, 'row amount').toString()
    };
    if (!SOURCE_TYPES.includes(entry.sourceType)) throw Error('sourceType: not in synthetic allowlist');
    for (const [type, value, seen] of [
      ['DUPLICATE_INDEX', entry.index, indices],
      ['DUPLICATE_WALLET', entry.account, wallets],
      ['DUPLICATE_SUBJECT', entry.subjectTag, subjects],
      ['DUPLICATE_EVENT', entry.eventRef, events],
      ['DUPLICATE_EVIDENCE', entry.evidenceRef, evidence]
    ]) {
      if (seen.has(value)) mark(flags, type, i);
      seen.add(value);
    }
    if (priorEvents.has(entry.eventRef)) mark(flags, 'EVENT_REPLAY_FROM_HISTORY', i);
    for (const old of priorSubjects.get(entry.subjectTag) ?? []) {
      if (old.epoch === epoch) mark(flags, 'SUBJECT_REPLAY_IN_EPOCH', i);
      if (old.account !== entry.account) mark(flags, 'SUBJECT_WALLET_ROTATION_REVIEW', i);
    }
    for (const old of priorWallets.get(entry.account) ?? []) {
      if (old.epoch === epoch) mark(flags, 'WALLET_REPLAY_IN_EPOCH', i);
      if (old.subjectTag !== entry.subjectTag) mark(flags, 'WALLET_SHARED_BY_SUBJECTS', i);
    }
    const amount = BigInt(entry.amountUnits);
    if (amount > maxClaim) mark(flags, 'CLAIM_CAP_EXCEEDED', i);
    total += amount;
    if (total > UINT256) throw Error('total: uint256 overflow');
    return entry;
  });
  if (total > maxEpoch) mark(flags, 'EPOCH_CAP_EXCEEDED', 'BATCH');
  rows.sort((a, b) => BigInt(a.index) < BigInt(b.index) ? -1 : BigInt(a.index) > BigInt(b.index) ? 1 : 0);
  history.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
  const reviewSha256 = createHash('sha256').update(JSON.stringify({
    policy: input.policy, epoch, history, rows
  })).digest('hex');
  return {
    project: 'MOJ1', status: 'OFFLINE_SYNTHETIC_NO_GO', policyId: POLICY_ID,
    riskAssessment: flags.size ? 'HOLD_FOR_MANUAL_REVIEW' : 'SYNTHETIC_CHECKS_PASSED_ONLY',
    riskFlags: [...flags].sort(), epoch, candidateCount: rows.length,
    totalCandidateUnits: total.toString(), reviewSha256,
    identityVerified: false, sybilResistanceProven: false, entitlementApproved: false,
    sourceEvidenceIndependentlyVerified: false, chainBalanceVerified: false,
    auditApproved: false, payoutAuthorized: false, shastaBroadcastAuthorized: false,
    mainnetAuthorized: false
  };
}
