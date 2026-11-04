import test from 'node:test';
import assert from 'node:assert/strict';
import {TronWeb} from 'tronweb';
import {buildSyntheticSumGuardProposal, verifySyntheticSumProof} from '../scripts/reward-sum-guard-offline.mjs';

const wallet = i => TronWeb.address.fromPrivateKey(BigInt(i).toString(16).padStart(64, '0'));
function sample(n = 5) {
  const rows = Array.from({length:n}, (_, i) => ({
    index:String(i),account:wallet(i+5),amountUnits:String(i+1),evidenceRef:`TEST-EVENT-${i+1}`
  })).reverse();
  return {
    mode:'SYNTHETIC_LOCAL_TEST_ONLY',reviewStatus:'UNREVIEWED',
    domain:{chainId:'0',contractAddress:wallet(4),epoch:'42'},
    budgetUnits:String(n*(n+1)/2),fundedAvailableUnits:'1000',rows
  };
}
const build = x => buildSyntheticSumGuardProposal(x);
const valid = (proposal, claim) => verifySyntheticSumProof({
  domain:proposal.domain,claim,root:proposal.root,budgetUnits:proposal.budgetUnits,leafCount:proposal.leafCount
});

test('single, uneven 3-leaf and 5-leaf trees commit exact sum and count with complete proofs', () => {
  for (const count of [1, 2, 3, 5, 8]) {
    const s = sample(count), out = build(s);
    assert.equal(out.claims.length, count);
    assert.equal(out.leafCount, String(count));
    assert.equal(out.budgetUnits, String(count*(count+1)/2));
    assert.equal(out.publicationAuthorized, false);
    assert.equal(out.sourceLedgerVerified, false);
    assert.equal(out.transactionBroadcast, false);
    assert.match(out.root, /^0x[0-9a-f]{64}$/);
    assert.match(out.manifestDigest, /^0x[0-9a-f]{64}$/);
    for (const claim of out.claims) assert.equal(valid(out,claim),true);
    s.rows.reverse();
    assert.deepEqual(build(s),out);
  }
});

test('leaf binds chain, escrow address, epoch, index, beneficiary and amount', () => {
  const input=sample(3), a=build(input);
  for (const [field,value] of [['chainId','1'],['contractAddress',wallet(20)],['epoch','43']]) {
    const other=sample(3);other.domain[field]=value;
    assert.notEqual(build(other).root,a.root);
    assert.equal(verifySyntheticSumProof({domain:other.domain,claim:a.claims[0],root:a.root,budgetUnits:a.budgetUnits,leafCount:a.leafCount}),false);
  }
  const c=structuredClone(a.claims[0]);c.amountUnits='99';assert.equal(valid(a,c),false);
  c.amountUnits=a.claims[0].amountUnits;c.index='99';assert.equal(valid(a,c),false);
  c.index=a.claims[0].index;c.account=wallet(15);assert.equal(valid(a,c),false);
});

test('rejects proof tampering, partial budget and false leaf count', () => {
  const a=build(sample(5));
  const changed=structuredClone(a.claims[0]);
  assert.ok(changed.proof.hashes.length);
  changed.proof.sums[0]=(BigInt(changed.proof.sums[0])+1n).toString();
  assert.equal(valid(a,changed),false);
  assert.equal(verifySyntheticSumProof({domain:a.domain,claim:a.claims[0],root:a.root,budgetUnits:'14',leafCount:'5'}),false);
  assert.equal(verifySyntheticSumProof({domain:a.domain,claim:a.claims[0],root:a.root,budgetUnits:'15',leafCount:'4'}),false);
});

test('fails closed on duplicate index, address, evidence, unsupported keys and fake approval', () => {
  const mutate=fn=>{const x=sample(3);fn(x);return x;};
  assert.throws(()=>build(mutate(x=>x.rows[1].index=x.rows[0].index)),/Duplicate/);
  assert.throws(()=>build(mutate(x=>x.rows[1].account=x.rows[0].account)),/Duplicate/);
  assert.throws(()=>build(mutate(x=>x.rows[1].evidenceRef=x.rows[0].evidenceRef)),/Duplicate/);
  assert.throws(()=>build(mutate(x=>x.rows[0].privateKey='no')),/unsupported field/);
  assert.throws(()=>build(mutate(x=>x.mode='MAINNET')),/Synthetic unreviewed/);
  assert.throws(()=>build(mutate(x=>x.reviewStatus='APPROVED')),/Synthetic unreviewed/);
  assert.throws(()=>build(mutate(x=>x.rows[0].evidenceRef='REAL-IDENTITY-001')),/Synthetic TEST/);
  assert.throws(()=>build(mutate(x=>x.rows[0].account='invalid')),/Invalid canonical/);
});

test('rejects unfunded, mismatched, invalid or overflowing liabilities', () => {
  const mutate=fn=>{const x=sample(3);fn(x);return x;};
  assert.throws(()=>build(mutate(x=>x.budgetUnits='7')),/Budget must equal/);
  assert.throws(()=>build(mutate(x=>x.fundedAvailableUnits='2')),/Unfunded/);
  assert.throws(()=>build(mutate(x=>x.rows[0].amountUnits='0')),/uint256 bounds/);
  assert.throws(()=>build(mutate(x=>x.rows[0].amountUnits='1.2')),/canonical unsigned/);
  assert.throws(()=>build(mutate(x=>x.domain.chainId='01')),/canonical unsigned/);
  assert.throws(()=>build(mutate(x=>x.rows=[])),/outside allowed/);
  assert.throws(()=>build(mutate(x=>x.rows[0].amountUnits=(1n<<256n).toString())),/uint256 bounds/);
});

test('base58 and 41-prefixed addresses have identical onchain leaf domain', () => {
  const x=sample(3), a=build(x);
  x.domain.contractAddress=TronWeb.address.toHex(x.domain.contractAddress);
  x.rows[0].account=TronWeb.address.toHex(x.rows[0].account);
  assert.deepEqual(build(x),a);
});
