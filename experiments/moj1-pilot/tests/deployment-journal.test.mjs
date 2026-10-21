import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {openDeploymentJournal} from '../scripts/deployment-journal.mjs';

const identity = {network: 'Shasta', governance: 'TEST_MULTISIG', artifacts: {
  MojCoin: 'sha256-token-artifact', MojAssets: 'sha256-nft-artifact'
}};

async function fixture(t) {
  const dir = await mkdtemp(join(tmpdir(), 'moj1-shasta-journal-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  return join(dir, 'state.json');
}

test('journal requires a persistent absolute path and Shasta identity', async () => {
  await assert.rejects(openDeploymentJournal('relative.json', identity), /absolute persistent/);
  await assert.rejects(openDeploymentJournal('/tmp/moj1-unused-invalid.json',
    {...identity, network: 'Mainnet'}), /Invalid Shasta/);
});

test('completed confirmed steps are idempotently reused without new deployment', async t => {
  const path = await fixture(t);
  const first = await openDeploymentJournal(path, identity);
  await first.markBroadcastUncertain('MojCoin');
  let snapshot = JSON.parse(await readFile(path, 'utf8'));
  assert.equal(snapshot.steps.MojCoin.status, 'BROADCAST_UNCERTAIN');
  await first.markVerified('MojCoin', 'TEST_ADDRESS');
  await first.close();

  const resumed = await openDeploymentJournal(path, identity);
  assert.equal(resumed.verifiedAddress('MojCoin'), 'TEST_ADDRESS');
  assert.equal(resumed.verifiedAddress('MojAssets'), null);
  await assert.rejects(resumed.markBroadcastUncertain('MojCoin'), /Cannot repeat/);
  await resumed.markBroadcastUncertain('MojAssets');
  await resumed.markVerified('MojAssets', 'TEST_NFT');
  snapshot = resumed.snapshot();
  assert.equal(snapshot.steps.MojAssets.address, 'TEST_NFT');
  await resumed.close();
});

test('possible broadcast is permanently blocked from automatic retry until reconciled', async t => {
  const path = await fixture(t);
  const first = await openDeploymentJournal(path, identity);
  await first.markBroadcastUncertain('MojCoin');
  await first.close();
  await assert.rejects(openDeploymentJournal(path, identity), /DO NOT REDEPLOY/);
});

test('journal refuses another compiled binary, governance address, or concurrent runner', async t => {
  const path = await fixture(t);
  const first = await openDeploymentJournal(path, identity);
  await assert.rejects(openDeploymentJournal(path, identity), /journal lock exists/);
  await first.close();
  await assert.rejects(openDeploymentJournal(path, {...identity,
    governance: 'DIFFERENT_GOVERNANCE'}), /identity mismatch/);
  await assert.rejects(openDeploymentJournal(path, {...identity,
    artifacts: {...identity.artifacts, MojCoin: 'new-binary'}}), /identity mismatch/);
});
