import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {openDeploymentJournal} from '../scripts/deployment-journal.mjs';
import {fingerprintRawTransaction, reconcileDeployment} from '../scripts/deployment-reconciler.mjs';

const txID = 'a'.repeat(64);
const address = '41' + 'c'.repeat(40);
const rawHex = 'deadbeef';
const identity = {network: 'Shasta', governance: 'TEST_MULTISIG',
  artifacts: {MojCoin: 'hash-1', MojAssets: 'hash-2'}};
const details = {txID, expectedAddress: address,
  rawDataSha256: fingerprintRawTransaction(rawHex)};

function chain(overrides = {}) {
  return {
    address: {toHex: x => x},
    trx: {
      getTransaction: async () => ({
        txID, raw_data_hex: rawHex, raw_data: {
          contract: [{type: 'CreateSmartContract'}]
        }, ...overrides.transaction
      }),
      getTransactionInfo: async () => ({
        id: txID, contract_address: address, receipt: {result: 'SUCCESS'},
        ...overrides.info
      }),
      getContract: async () => ({
        contract_address: address, bytecode: '60806040', ...overrides.contract
      })
    }
  };
}
async function createPending(t) {
  const dir = await mkdtemp(join(tmpdir(), 'moj1-reconcile-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  const journal = await openDeploymentJournal(join(dir, 'journal.json'), identity);
  await journal.markBroadcastUncertain('MojCoin', details);
  return journal;
}

test('solidified attested creation is recovered without a second broadcast', async t => {
  const journal = await createPending(t);
  try {
    const result = await reconcileDeployment(journal, 'MojCoin', chain());
    assert.equal(result.status, 'VERIFIED');
    assert.equal(result.txID, txID);
    assert.equal(journal.verifiedAddress('MojCoin'), address);
    assert.equal(journal.pending('MojCoin'), null);
    await assert.rejects(journal.markBroadcastUncertain('MojCoin', details), /Cannot repeat/);
  } finally { await journal.close(); }
});

test('missing chain transaction remains pending and blocks any new deployment', async t => {
  const journal = await createPending(t);
  try {
    const c = chain();
    c.trx.getTransaction = async () => ({});
    assert.equal((await reconcileDeployment(journal, 'MojCoin', c)).status, 'PENDING');
    await assert.rejects(journal.markBroadcastUncertain('MojAssets', details), /Cannot repeat/);
  } finally { await journal.close(); }
});

test('confirmed transaction without a solidified receipt stays uncertain', async t => {
  const journal = await createPending(t);
  try {
    assert.equal((await reconcileDeployment(journal, 'MojCoin',
      chain({info: {id: undefined}}))).status, 'PENDING');
    assert.equal(journal.pending('MojCoin').status, 'BROADCAST_UNCERTAIN');
  } finally { await journal.close(); }
});

test('tampered raw payload cannot be reconciled', async t => {
  const journal = await createPending(t);
  try {
    await assert.rejects(reconcileDeployment(journal, 'MojCoin',
      chain({transaction: {raw_data_hex: 'cafebabe'}})), /CHAIN_ATTESTATION_MISMATCH/);
    assert.ok(journal.pending('MojCoin'));
  } finally { await journal.close(); }
});

test('a different contract address cannot be accepted', async t => {
  const journal = await createPending(t);
  try {
    await assert.rejects(reconcileDeployment(journal, 'MojCoin',
      chain({info: {contract_address: '41' + 'd'.repeat(40)}})), /CHAIN_ATTESTATION_MISMATCH/);
    assert.ok(journal.pending('MojCoin'));
  } finally { await journal.close(); }
});

test('finalized on-chain execution failure does not unlock the journal', async t => {
  const journal = await createPending(t);
  try {
    await assert.rejects(reconcileDeployment(journal, 'MojCoin',
      chain({info: {receipt: {result: 'OUT_OF_ENERGY'}, result: 'FAILED'}})),
      /CHAIN_EXECUTION_FAILED/);
    assert.ok(journal.pending('MojCoin'));
  } finally { await journal.close(); }
});

test('missing code or a different on-chain contract address never validates', async t => {
  const journal = await createPending(t);
  try {
    await assert.rejects(reconcileDeployment(journal, 'MojCoin',
      chain({contract: {bytecode: ''}})), /CHAIN_CODE_NOT_VERIFIED/);
    await assert.rejects(reconcileDeployment(journal, 'MojCoin',
      chain({contract: {contract_address: '41' + 'd'.repeat(40)}})), /CHAIN_CODE_NOT_VERIFIED/);
    assert.ok(journal.pending('MojCoin'));
  } finally { await journal.close(); }
});

test('old pending entries without txID cannot be automatically cleared', async t => {
  const dir = await mkdtemp(join(tmpdir(), 'moj1-reconcile-legacy-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  const path = join(dir, 'journal.json');
  const journal = await openDeploymentJournal(path, identity);
  try {
    await journal.markBroadcastUncertain('MojCoin', details);
    // Simulate the legacy (pre-txID) payload through a read-only snapshot proxy.
    const legacy = {pending: () => ({status: 'BROADCAST_UNCERTAIN'})};
    await assert.rejects(reconcileDeployment(legacy, 'MojCoin', chain()), /LEGACY_UNRESOLVED/);
  } finally { await journal.close(); }
});

test('invalid raw transaction hex is rejected before any chain I/O', () => {
  assert.throws(() => fingerprintRawTransaction('not hex'), /canonical/);
});
