// Synthetic-only MOJ1 sum-tree proposal builder. No signing, identity verification, network or broadcast.
// A correct tree does not prove real-world reward eligibility or completeness of the source game ledger.
import {TronWeb, utils as TronWebUtils} from 'tronweb';
import {createHash} from 'node:crypto';

const MAX = (1n << 256n) - 1n;
const MAX_LEAVES = 1_000_000;
const keccak = hex => TronWebUtils.ethersUtils.keccak256(hex).toLowerCase();
const word = n => n.toString(16).padStart(64, '0');
const byteWord = n => n.toString(16).padStart(2, '0') + '0'.repeat(62);

function exactKeys(o, names, label) {
  if (!o || typeof o !== 'object' || Array.isArray(o)) throw Error(`${label}: object required`);
  for (const k of Object.keys(o)) if (!names.includes(k)) throw Error(`${label}: unsupported field ${k}`);
  for (const k of names) if (!Object.hasOwn(o, k)) throw Error(`${label}: missing ${k}`);
}
function uint(value, label, allowZero = false) {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]*)$/.test(value)) {
    throw Error(`${label}: canonical unsigned decimal string required`);
  }
  const n = BigInt(value);
  if (n > MAX || (!allowZero && n === 0n)) throw Error(`${label}: uint256 bounds`);
  return n;
}
function addressData(s) {
  if (typeof s !== 'string') throw Error('Invalid TRON address');
  const value = /^(?:0x)?41[0-9a-fA-F]{40}$/.test(s)
    ? TronWeb.address.fromHex(s.replace(/^0x/, '')) : s;
  if (!/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(value) || !TronWeb.isAddress(value)) {
    throw Error('Invalid canonical TRON address');
  }
  const h = TronWeb.address.toHex(value).toLowerCase();
  if (!/^41[0-9a-f]{40}$/.test(h) || /^410{40}$/.test(h)) throw Error('Invalid address word');
  return {address: value, word: h.slice(2).padStart(64, '0')};
}
function checkedAdd(a, b) {
  const c = a + b;
  if (c > MAX) throw Error('uint256 sum overflow');
  return c;
}
function combine(a, b) {
  if (a.sum <= 0n || b.sum <= 0n || a.count <= 0n || b.count <= 0n) throw Error('Empty sum node');
  const [lo, hi] = a.hash <= b.hash ? [a, b] : [b, a];
  return {
    hash: keccak('0x' + byteWord(1) + lo.hash.slice(2) + word(lo.sum) + word(lo.count) +
      hi.hash.slice(2) + word(hi.sum) + word(hi.count)),
    sum: checkedAdd(a.sum, b.sum), count: checkedAdd(a.count, b.count)
  };
}
function layersOf(leaves) {
  const layers = [leaves];
  while (layers.at(-1).length > 1) {
    const prev = layers.at(-1), next = [];
    for (let i = 0; i < prev.length; i += 2) {
      next.push(i + 1 < prev.length ? combine(prev[i], prev[i + 1]) : prev[i]);
    }
    layers.push(next);
    if (layers.length > 33) throw Error('Proof depth exceeds on-chain bound');
  }
  return layers;
}
function siblingsOf(layers, i) {
  const result = [];
  for (let depth = 0; depth + 1 < layers.length; depth++) {
    const sibling = i ^ 1;
    if (sibling < layers[depth].length) result.push(layers[depth][sibling]);
    i = Math.floor(i / 2);
  }
  return result;
}

export function verifySyntheticSumProof({domain, claim, root, budgetUnits, leafCount}) {
  try {
    exactKeys(domain, ['chainId', 'contractAddress', 'epoch'], 'domain');
    const chainId = uint(domain.chainId, 'chainId', true);
    const epoch = uint(domain.epoch, 'epoch', true);
    const contract = addressData(domain.contractAddress);
    const index = uint(claim.index, 'index', true);
    const amount = uint(claim.amountUnits, 'amountUnits');
    const beneficiary = addressData(claim.account);
    const p = claim.proof;
    if (!p || !Array.isArray(p.hashes) || !Array.isArray(p.sums) || !Array.isArray(p.counts) ||
        p.hashes.length !== p.sums.length || p.hashes.length !== p.counts.length || p.hashes.length > 32) return false;
    let cursor = {
      hash: keccak('0x' + byteWord(0) + word(chainId) + contract.word + word(epoch) + word(index) + beneficiary.word + word(amount)),
      sum: amount, count: 1n
    };
    for (let i = 0; i < p.hashes.length; i++) {
      if (!/^0x[0-9a-f]{64}$/.test(p.hashes[i])) return false;
      cursor = combine(cursor, {hash: p.hashes[i], sum: uint(p.sums[i], 'sibling sum'), count: uint(p.counts[i], 'sibling count')});
    }
    return cursor.hash === root && cursor.sum === uint(budgetUnits, 'budget') && cursor.count === uint(leafCount, 'leafCount');
  } catch { return false; }
}

export function buildSyntheticSumGuardProposal(input) {
  exactKeys(input, ['mode', 'reviewStatus', 'domain', 'budgetUnits', 'fundedAvailableUnits', 'rows'], 'proposal');
  if (input.mode !== 'SYNTHETIC_LOCAL_TEST_ONLY' || input.reviewStatus !== 'UNREVIEWED') {
    throw Error('Synthetic unreviewed inputs only');
  }
  exactKeys(input.domain, ['chainId', 'contractAddress', 'epoch'], 'domain');
  const chainId = uint(input.domain.chainId, 'chainId', true);
  const epoch = uint(input.domain.epoch, 'epoch', true);
  const contract = addressData(input.domain.contractAddress);
  const budget = uint(input.budgetUnits, 'budgetUnits');
  const available = uint(input.fundedAvailableUnits, 'fundedAvailableUnits', true);
  if (budget > available) throw Error('Unfunded liability');
  if (!Array.isArray(input.rows) || input.rows.length < 1 || input.rows.length > MAX_LEAVES) {
    throw Error('rows outside allowed range');
  }
  const indices = new Set(), accounts = new Set(), evidence = new Set();
  let sum = 0n;
  const rows = input.rows.map((row, i) => {
    exactKeys(row, ['index', 'account', 'amountUnits', 'evidenceRef'], `row ${i}`);
    const index = uint(row.index, 'index', true);
    const amount = uint(row.amountUnits, 'amountUnits');
    const beneficiary = addressData(row.account);
    if (typeof row.evidenceRef !== 'string' || !/^TEST-[A-Z0-9-]{4,80}$/.test(row.evidenceRef)) {
      throw Error('Synthetic TEST-* evidence required');
    }
    if (indices.has(index.toString()) || accounts.has(beneficiary.word) || evidence.has(row.evidenceRef)) {
      throw Error('Duplicate index, beneficiary or evidence');
    }
    indices.add(index.toString()); accounts.add(beneficiary.word); evidence.add(row.evidenceRef);
    sum = checkedAdd(sum, amount);
    return {
      index: index.toString(), account: beneficiary.address, amountUnits: amount.toString(),
      evidenceRef: row.evidenceRef,
      node: {hash: keccak('0x' + byteWord(0) + word(chainId) + contract.word + word(epoch) +
        word(index) + beneficiary.word + word(amount)), sum: amount, count: 1n}
    };
  });
  if (sum !== budget) throw Error('Budget must equal sum of all entitlements');
  rows.sort((a, b) => BigInt(a.index) < BigInt(b.index) ? -1 : BigInt(a.index) > BigInt(b.index) ? 1 : 0);
  const layers = layersOf(rows.map(r => r.node));
  const top = layers.at(-1)[0];
  if (top.sum !== budget || top.count !== BigInt(rows.length)) throw Error('Internal liability mismatch');
  const domain = {chainId: chainId.toString(), contractAddress: contract.address, epoch: epoch.toString()};
  const claims = rows.map((r, i) => {
    const siblings = siblingsOf(layers, i);
    const c = {
      index: r.index, account: r.account, amountUnits: r.amountUnits, evidenceRef: r.evidenceRef,
      leaf: r.node.hash,
      proof: {
        hashes: siblings.map(s => s.hash),
        sums: siblings.map(s => s.sum.toString()),
        counts: siblings.map(s => s.count.toString())
      }
    };
    if (!verifySyntheticSumProof({domain, claim:c, root:top.hash, budgetUnits:budget.toString(), leafCount:rows.length.toString()})) {
      throw Error('Synthetic proof failed internal check');
    }
    return c;
  });
  const payload = {domain, budgetUnits:budget.toString(), leafCount:rows.length.toString(), claims};
  const digest = '0x' + createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  return {
    project:'MOJ1',status:'OFFLINE_SYNTHETIC_UNREVIEWED',publicationAuthorized:false,
    transactionBroadcast:false,chainVerified:false,identityVerified:false,sourceLedgerVerified:false,
    domain,budgetUnits:budget.toString(),leafCount:rows.length.toString(),root:top.hash,
    manifestDigest:digest,claims
  };
}
