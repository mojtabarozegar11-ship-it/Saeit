// Disposable localhost-only TRE integration: broadcast ONCE, drop the response,
// recover using chain evidence, and prove that the journal blocks any redeploy.
// NEVER use this file with a public node or a non-disposable wallet.
import assert from 'node:assert/strict';
import {TronWeb} from 'tronweb';
import {createHash} from 'node:crypto';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {openDeploymentJournal} from './deployment-journal.mjs';
import {fingerprintRawTransaction, normalizedTronAddress, reconcileDeployment} from './deployment-reconciler.mjs';

const TEST_KEY = '0000000000000000000000000000000000000000000000000000000000000001';
if (process.env.MOJ1_LOCAL_TVM_ONLY !== '1' ||
    process.env.LOCAL_PRIVATE_KEY !== TEST_KEY) {
  throw new Error('Refusing to run outside the designated disposable localhost TVM');
}
const tronWeb = new TronWeb({fullHost: 'http://127.0.0.1:9090', privateKey: TEST_KEY});
const governance = tronWeb.defaultAddress.base58;
const hashes = {};
let nftArtifact;
for (const name of ['MojCoin', 'MojAssets']) {
  const artifact = JSON.parse(await readFile(new URL(
    `../build/contracts/${name}.json`, import.meta.url), 'utf8'));
  hashes[name] = createHash('sha256').update(JSON.stringify({
    abi: artifact.abi, bytecode: artifact.bytecode
  })).digest('hex');
  if (name === 'MojAssets') nftArtifact = artifact;
}
const context = {network: 'Shasta', governance: tronWeb.address.toHex(governance),
  artifacts: hashes};
const dirname = await mkdtemp(join(tmpdir(), 'moj1-local-recovery-'));
const journalPath = join(dirname, 'journal.json');
let journal;
try {
  const ctor = nftArtifact.abi.find(item => item.type === 'constructor');
  assert.deepEqual(ctor.inputs.map(x => x.type), ['address']);
  const unsigned = await tronWeb.transactionBuilder.createSmartContract({
    abi: nftArtifact.abi, bytecode: nftArtifact.bytecode.replace(/^0x/, ''),
    name: 'MojAssets', feeLimit: 1_000_000_000, callValue: 0,
    userFeePercentage: 100, originEnergyLimit: 10_000_000,
    funcABIV2: ctor, parametersV2: [governance]
  }, governance);
  const signed = await tronWeb.trx.sign(unsigned);
  assert.ok(signed.signature?.length);
  assert.equal(signed.txID, unsigned.txID);
  assert.equal(signed.raw_data_hex, unsigned.raw_data_hex);
  const expectedAddress = normalizedTronAddress(unsigned.contract_address, tronWeb);
  journal = await openDeploymentJournal(journalPath, context);
  await journal.markBroadcastUncertain('MojAssets', {
    txID: signed.txID, rawDataSha256: fingerprintRawTransaction(signed.raw_data_hex),
    expectedAddress
  });
  // Even before sending, all other deployment steps are blocked.
  await assert.rejects(journal.markBroadcastUncertain('MojCoin', {
    txID: 'a'.repeat(64), rawDataSha256: 'b'.repeat(64),
    expectedAddress
  }), /Cannot repeat/);

  // The ONLY broadcast is to the disposable 127.0.0.1 chain.
  const accepted = await tronWeb.trx.sendRawTransaction(signed);
  assert.ok(accepted?.result || accepted?.code === 'DUP_TRANSACTION_ERROR',
    'Local-only deployment transaction must be accepted');
  // Simulate lost application-level acknowledgement. No txID is extracted
  // from the network response; the durable record predates the broadcast.
  await journal.close();
  journal = await openDeploymentJournal(journalPath, context);
  assert.equal(journal.pending('MojAssets').txID, signed.txID.toLowerCase());

  let result;
  for (let attempt = 0; attempt < 30; attempt++) {
    result = await reconcileDeployment(journal, 'MojAssets', tronWeb);
    if (result.status === 'VERIFIED') break;
    assert.equal(result.status, 'PENDING');
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
  assert.equal(result.status, 'VERIFIED', 'Read-only recovery timed out');
  assert.equal(result.address, expectedAddress);
  assert.equal(journal.verifiedAddress('MojAssets'), expectedAddress);
  assert.equal((await reconcileDeployment(journal, 'MojAssets', tronWeb)).status,
    'NOT_PENDING');
  await assert.rejects(journal.markBroadcastUncertain('MojAssets', {
    txID: 'a'.repeat(64), rawDataSha256: 'b'.repeat(64),
    expectedAddress
  }), /Cannot repeat/);

  // Post-recovery semantic check: constructor owner is exactly the intended
  // local test account. No mint, treasury distribution or Mainnet operation.
  const nft = await tronWeb.contract().at(tronWeb.address.fromHex(expectedAddress));
  const owner = await nft.owner().call();
  assert.equal(normalizedTronAddress(String(owner), tronWeb),
    normalizedTronAddress(governance, tronWeb));
  console.log(JSON.stringify({
    status: 'MOJ1_LOCAL_REAL_TX_RECOVERY_PASS',
    mode: 'DISPOSABLE_LOCAL_TVM_ONLY',
    broadcasts: 1, retryBroadcasts: 0,
    journalRecovered: true, receiptVerified: true,
    mainnet: false, shasta: false, realWallet: false
  }));
} finally {
  if (journal) await journal.close();
  await rm(dirname, {recursive: true, force: true});
}
