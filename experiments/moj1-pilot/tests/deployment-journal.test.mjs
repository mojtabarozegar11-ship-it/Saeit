import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {openDeploymentJournal} from '../scripts/deployment-journal.mjs';

const identity = {network: 'Shasta', governance: 'TEST_MULTISIG', artifacts: {
  MojCoin: 'sha256-token-artifact', MojAssets: 'sha256-nft-artifact'
}};
const details = {txID: 'a'.repeat(64), rawDataSha256: 'b'.repeat(64),
  expectedAddress: '41' + 'c'.repeat(40)};

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

test('confirmed steps can be reused without new deployment', async t => {
  const path = await fixture(t);
  const first = await openDeploymentJournal(path, identity);
  await first.markBroadcastUncertain('MojCoin', details);
  assert.equal(JSON.parse(await readFile(path, 'utf8')).steps.MojCoin.txID, details.txID);
  await first.markVerified('MojCoin', details.expectedAddress, details.txID);
  await first.close();

  const resumed = await openDeploymentJournal(path, identity);
  assert.equal(resumed.verifiedAddress('MojCoin'), details.expectedAddress);
  assert.equal(resumed.verifiedAddress('MojAssets'), null);
  await assert.rejects(resumed.markBroadcastUncertain('MojCoin', details), /Cannot repeat/);
  await resumed.markBroadcastUncertain('MojAssets', {...details, txID: 'd'.repeat(64)});
  await resumed.markVerified('MojAssets', details.expectedAddress, 'd'.repeat(64));
  assert.equal(resumed.snapshot().steps.MojAssets.status, 'VERIFIED');
  await resumed.close();
});

test('pending broadcast survives restart and blocks every fresh deployment', async t => {
  const path = await fixture(t);
  const first = await openDeploymentJournal(path, identity);
  await first.markBroadcastUncertain('MojCoin', details);
  await first.close();
  const resumed = await openDeploymentJournal(path, identity);
  assert.deepEqual(resumed.pending('MojCoin').txID, details.txID);
  assert.throws(() => resumed.verifiedAddress('MojCoin'), /DO NOT REDEPLOY/);
  await assert.rejects(resumed.markBroadcastUncertain('MojAssets', details), /Cannot repeat/);
  await resumed.close();
});

test('journal refuses wrong txID, wrong address, malformed attestation and secret material', async t => {
  const path = await fixture(t);
  const journal = await openDeploymentJournal(path, identity);
  await assert.rejects(journal.markBroadcastUncertain('MojCoin',
    {...details, txID: 'bad'}), /complete signed txID/);
  await journal.markBroadcastUncertain('MojCoin', details);
  await assert.rejects(journal.markVerified('MojCoin', details.expectedAddress, 'f'.repeat(64)),
    /matching journaled/);
  await assert.rejects(journal.markVerified('MojCoin', '41'+'e'.repeat(40), details.txID),
    /matching journaled/);
  const raw = await readFile(path, 'utf8');
  assert.doesNotMatch(raw, /privateKey|signature|signedTransaction|TRON_PRIVATE_KEY/);
  await journal.close();
});

test('journal refuses changed artifacts, governance address, or a concurrent runner', async t => {
  const path = await fixture(t);
  const first = await openDeploymentJournal(path, identity);
  await assert.rejects(openDeploymentJournal(path, identity), /journal lock exists/);
  await first.close();
  await assert.rejects(openDeploymentJournal(path, {...identity,
    governance: 'DIFFERENT_GOVERNANCE'}), /identity mismatch/);
  await assert.rejects(openDeploymentJournal(path, {...identity,
    artifacts: {...identity.artifacts, MojCoin: 'new-binary'}}), /identity mismatch/);
});

test('independent Shasta governance journal refuses double broadcast and altered owners', async t => {
  const path = await fixture(t);
  const govIdentity = {network: 'Shasta', governance: 'SHA256_OF_THREE_TEST_OWNERS',
    artifacts: {MojPilotGovernance: 'governance-build-hash'}};
  const journal = await openDeploymentJournal(path, govIdentity);
  await journal.markBroadcastUncertain('MojPilotGovernance', details);
  await assert.rejects(journal.markBroadcastUncertain('MojPilotGovernance', details), /Cannot repeat/);
  await assert.rejects(journal.markBroadcastUncertain('MojCoin', details), /Cannot repeat/);
  await journal.close();
  const resumed = await openDeploymentJournal(path, govIdentity);
  assert.equal(resumed.pending('MojPilotGovernance').txID, details.txID);
  await resumed.markVerified('MojPilotGovernance', details.expectedAddress, details.txID);
  assert.equal(resumed.verifiedAddress('MojPilotGovernance'), details.expectedAddress);
  await resumed.close();
  await assert.rejects(openDeploymentJournal(path, {...govIdentity,
    governance: 'DIFFERENT_TEST_OWNERS'}), /identity mismatch/);
});

test('Shasta journal rejects unsupported deployment manifest', async t => {
  const path = await fixture(t);
  await assert.rejects(openDeploymentJournal(path, {network: 'Shasta', governance: 'x',
    artifacts: {MojCoin: 'a'}}), /Invalid Shasta deployment journal identity/);
});

test('separate disposable reward journal blocks second deployment while first receipt is uncertain',async t=>{
  const path=await fixture(t);
  const rewardIdentity={network:'Shasta',governance:'41'+'a'.repeat(40),artifacts:{
    MojRewardTestToken:'hash-test-token',MojRewardClaimsPilot:'hash-test-reward'
  }};
  const first=await openDeploymentJournal(path,rewardIdentity);
  await first.markBroadcastUncertain('MojRewardTestToken',details);
  await assert.rejects(first.markBroadcastUncertain('MojRewardClaimsPilot',{
    ...details,txID:'d'.repeat(64)
  }),/Cannot repeat/);
  await first.close();
  const second=await openDeploymentJournal(path,rewardIdentity);
  assert.ok(second.pending('MojRewardTestToken'));
  await second.markVerified('MojRewardTestToken',details.expectedAddress,details.txID);
  await second.markBroadcastUncertain('MojRewardClaimsPilot',{
    ...details,txID:'d'.repeat(64)
  });
  await second.close();
  await assert.rejects(openDeploymentJournal(path,{...rewardIdentity,
    artifacts:{...rewardIdentity.artifacts,MojRewardTestToken:'tampered'}
  }),/identity mismatch/);
});
