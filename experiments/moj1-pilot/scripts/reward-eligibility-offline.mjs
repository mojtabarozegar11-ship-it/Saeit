// MOJ1 experimental reward eligibility — OFFLINE SYNTHETIC PROPOSALS ONLY.
// No keys, network access, deployment, external identity assertions or payouts.
// This is NOT an anti-Sybil service. A Merkle inclusion proof cannot establish a real person.
import {TronWeb} from 'tronweb';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const LIMIT = (1n << 256n) - 1n;
const hash = hex => TronWeb.utils.ethersUtils.keccak256(hex).toLowerCase();

function exactKeys(value, allowed, name) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error(name + ': expected object');
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) throw Error(name + ': unsupported field ' + key);
  }
  for (const key of allowed) {
    if (!(key in value)) throw Error(name + ': missing ' + key);
  }
}
function uint(value, label, allowZero = false) {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]*)$/.test(value)) {
    throw Error(label + ': canonical decimal string required');
  }
  const parsed = BigInt(value);
  if (parsed > LIMIT || (!allowZero && parsed === 0n)) throw Error(label + ': outside uint256 bounds');
  return parsed;
}
const word = n => n.toString(16).padStart(64, '0');
function addressWord(account) {
  if (typeof account !== 'string' || !/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(account) ||
      !TronWeb.isAddress(account)) throw Error('Invalid canonical Base58 TRON address');
  const hex = TronWeb.address.toHex(account).toLowerCase();
  if (!/^41[0-9a-f]{40}$/.test(hex)) throw Error('Invalid TRON hex address');
  return hex.slice(2).padStart(64, '0');
}
function combine(a, b) {
  const values = [a.toLowerCase(), b.toLowerCase()].sort();
  return hash('0x' + values.map(x => x.slice(2)).join(''));
}
function layersFor(leaves) {
  const layers = [leaves];
  while (layers[layers.length - 1].length > 1) {
    const cur = layers[layers.length - 1];
    const next = [];
    for (let i = 0; i < cur.length; i += 2) {
      next.push(i + 1 === cur.length ? cur[i] : combine(cur[i], cur[i + 1]));
    }
    layers.push(next);
  }
  return layers;
}
function proofFor(layers, index) {
  const proof = [];
  for (let depth = 0; depth < layers.length - 1; ++depth) {
    const sibling = index ^ 1;
    if (sibling < layers[depth].length) proof.push(layers[depth][sibling]);
    index = Math.floor(index / 2);
  }
  return proof;
}
export function verifyCandidateProof(leaf, siblings, expectedRoot) {
  if (typeof leaf !== 'string' || !/^0x[0-9a-f]{64}$/.test(leaf) ||
      !Array.isArray(siblings) || !siblings.every(s => /^0x[0-9a-f]{64}$/.test(s))) return false;
  let current = leaf;
  for (const s of siblings) current = combine(current, s);
  return current === expectedRoot;
}
export function buildSyntheticEligibilityProposal(input) {
  exactKeys(input, ['mode', 'reviewStatus', 'domain', 'budgetUnits', 'fundedAvailableUnits', 'rows'], 'proposal');
  if (input.mode !== 'SYNTHETIC_LOCAL_TEST_ONLY' || input.reviewStatus !== 'UNREVIEWED') {
    throw Error('Only unreviewed synthetic test proposals are accepted');
  }
  exactKeys(input.domain, ['chainId', 'contractAddress', 'epoch'], 'domain');
  const chainId = uint(input.domain.chainId, 'chainId', true);
  const epoch = uint(input.domain.epoch, 'epoch', true);
  const contract = addressWord(input.domain.contractAddress);
  const budget = uint(input.budgetUnits, 'budgetUnits');
  const available = uint(input.fundedAvailableUnits, 'fundedAvailableUnits', true);
  if (budget > available) throw Error('Unfunded proposed epoch');
  if (!Array.isArray(input.rows) || input.rows.length < 1 || input.rows.length > 10000) {
    throw Error('rows: expected 1 to 10000 synthetic records');
  }
  const indices = new Set(), accounts = new Set(), evidence = new Set();
  let sum = 0n;
  const rows = input.rows.map((r, line) => {
    exactKeys(r, ['index', 'account', 'amountUnits', 'evidenceRef'], 'row ' + line);
    const index = uint(r.index, 'index', true);
    const amount = uint(r.amountUnits, 'amountUnits');
    const beneficiary = addressWord(r.account);
    if (typeof r.evidenceRef !== 'string' || !/^TEST-[A-Z0-9-]{4,80}$/.test(r.evidenceRef)) {
      throw Error('Synthetic TEST-* evidence reference required');
    }
    const indexKey = index.toString();
    if (indices.has(indexKey) || accounts.has(beneficiary) || evidence.has(r.evidenceRef)) {
      throw Error('Duplicate index, beneficiary or evidence reference');
    }
    indices.add(indexKey); accounts.add(beneficiary); evidence.add(r.evidenceRef);
    sum += amount;
    if (sum > LIMIT) throw Error('Sum overflow');
    const encoded = [word(chainId), contract, word(epoch), word(index), beneficiary, word(amount)].join('');
    const leaf = hash(hash('0x' + encoded));
    return {index: indexKey, account: r.account, amountUnits: amount.toString(), evidenceRef: r.evidenceRef, leaf};
  });
  if (sum !== budget) throw Error('Proposed budget must equal total leaf claims (no stranded remainder)');
  rows.sort((a, b) => (BigInt(a.index) < BigInt(b.index) ? -1 : BigInt(a.index) > BigInt(b.index) ? 1 : 0));
  const layers = layersFor(rows.map(r => r.leaf));
  const root = layers[layers.length - 1][0];
  const claims = rows.map((row, index) => {
    const proof = proofFor(layers, index);
    if (!verifyCandidateProof(row.leaf, proof, root)) throw Error('Internal proof verification failed');
    return {...row, proof};
  });
  const proposalDigest = createHash('sha256').update(JSON.stringify({
    domain: input.domain, budgetUnits: budget.toString(), claims
  })).digest('hex');
  return {
    project: 'MOJ1', status: 'OFFLINE_SYNTHETIC_UNREVIEWED', publicationAuthorized: false,
    transactionBroadcast: false, privateKeyAccessed: false, chainVerified: false,
    sybilAndIdentityVerified: false, eligiblePeopleVerified: false,
    domain: input.domain, budgetUnits: budget.toString(),
    root, proposalSha256: proposalDigest, claims
  };
}

// Explicit input file only; CLI never contacts a chain or broadcasts a transaction.
const invokedAs = process.argv[1] ? resolve(process.argv[1]) : '';
if (invokedAs && invokedAs === fileURLToPath(import.meta.url)) {
  if (process.argv.length !== 3) {
    console.error('Usage: node scripts/reward-eligibility-offline.mjs <SYNTHETIC_INPUT.json>');
    process.exitCode = 2;
  } else {
    try {
      const proposal = buildSyntheticEligibilityProposal(JSON.parse(readFileSync(process.argv[2], 'utf8')));
      process.stdout.write(JSON.stringify(proposal, null, 2) + '\n');
    } catch (e) {
      console.error('REWARD_PROPOSAL_DENIED:', e.message);
      process.exitCode = 2;
    }
  }
}
