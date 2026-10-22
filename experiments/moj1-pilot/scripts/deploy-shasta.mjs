// Shasta ONLY. There is deliberately no Mainnet deployment option.
// This script is NEVER invoked by CI. Running it can spend Shasta test TRX.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';
import {isAbsolute} from 'node:path';
import {createHash} from 'node:crypto';
import {openDeploymentJournal} from './deployment-journal.mjs';
import {fingerprintRawTransaction, normalizedTronAddress, reconcileDeployment} from './deployment-reconciler.mjs';

if (process.env.MOJ1_DEPLOY_CONFIRM !== 'SHASTA_ONLY') {
  throw new Error('Deployment requires MOJ1_DEPLOY_CONFIRM=SHASTA_ONLY');
}
const testKey = process.env.TRON_PRIVATE_KEY;
if (!/^[a-fA-F0-9]{64}$/.test(testKey ?? '')) {
  throw new Error('Use a dedicated 64-hex-character Shasta-only test wallet key');
}
const journalPath = process.env.MOJ1_DEPLOY_JOURNAL_PATH;
if (!journalPath || !isAbsolute(journalPath)) {
  throw new Error('Set MOJ1_DEPLOY_JOURNAL_PATH to an absolute, private, persistent path outside GitHub and temporary storage');
}

const tronWeb = new TronWeb({fullHost: 'https://api.shasta.trongrid.io', privateKey: testKey});
const governance = process.env.MOJ_SHASTA_GOVERNANCE;
if (!tronWeb.isAddress(governance ?? '')) {
  throw new Error('Set MOJ_SHASTA_GOVERNANCE to an approved Shasta multisig contract address');
}
const governanceContract = await tronWeb.trx.getContract(governance);
if (!governanceContract?.bytecode) {
  throw new Error('Shasta governance must be a deployed contract, not a single-key wallet');
}
// Bytecode existence by itself does NOT prove a contract is our 2-of-3 governor.
// Require three explicitly pinned distinct Shasta test signer addresses and
// cross-check the three on-chain owners before deploying any token.
const ownerInput = (process.env.MOJ1_SHASTA_GOV_OWNERS ?? '').split(',').map(x => x.trim());
if (ownerInput.length !== 3 || ownerInput.some(x => !tronWeb.isAddress(x))) {
  throw new Error('MOJ1_SHASTA_GOV_OWNERS requires exactly three valid test-governance owner addresses');
}
const normalizedOwners = ownerInput.map(x => normalizedTronAddress(x, tronWeb));
if (new Set(normalizedOwners).size !== 3) {
  throw new Error('Duplicate Shasta governance owners');
}
let onchainGovernor;
try {
  onchainGovernor = await tronWeb.contract().at(governance);
  for (let i = 0; i < 3; ++i) {
    if (normalizedTronAddress(String(await onchainGovernor.owners(i).call()), tronWeb) !== normalizedOwners[i]) {
      throw new Error('Shasta governance owner mismatch');
    }
  }
  // Our pilot governor exposes this monotonic replay nonce. A generic deployed
  // contract without our governance interface is not a valid signing controller.
  if (!/^[0-9]+$/.test(String(await onchainGovernor.nonce().call()))) {
    throw new Error('Shasta governance lacks expected nonce');
  }
} catch (error) {
  throw new Error('Unverified Shasta 2-of-3 governance interface/owners: ' + error.message);
}

const names = ['MojCoin', 'MojAssets'];
const artifacts = {};
const artifactHashes = {};
for (const name of names) {
  const file = new URL(`../build/contracts/${name}.json`, import.meta.url);
  const artifact = JSON.parse(await readFile(file, 'utf8'));
  if (artifact.contractName !== name || !Array.isArray(artifact.abi) ||
      !/^(?:0x)?(?:[a-fA-F0-9]{2})+$/.test(artifact.bytecode ?? '')) {
    throw new Error(`Invalid compiled artifact for ${name}`);
  }
  artifacts[name] = artifact;
  artifactHashes[name] = createHash('sha256')
    .update(JSON.stringify({abi: artifact.abi, bytecode: artifact.bytecode})).digest('hex');
}

const journal = await openDeploymentJournal(journalPath, {
  network: 'Shasta', governance: tronWeb.address.toHex(governance), artifacts: artifactHashes
});

async function confirmCode(address, name) {
  if (!tronWeb.isAddress(address)) throw new Error(`Invalid journaled ${name} address`);
  const result = await tronWeb.trx.getContract(address);
  if (!result?.contract_address || !result?.bytecode) {
    throw new Error(`Cannot retrieve deployed ${name} contract on Shasta: ${address}`);
  }
}

async function deployOnce(name) {
  const pending = journal.pending(name);
  if (pending) {
    const reconciliation = await reconcileDeployment(journal, name, tronWeb);
    if (reconciliation.status === 'VERIFIED') {
      return tronWeb.address.fromHex(reconciliation.address);
    }
    throw new Error('Existing Shasta broadcast remains uncertain for ' + name +
      ' (txID ' + (pending.txID ?? 'UNKNOWN_LEGACY') + '): DO NOT REDEPLOY');
  }
  const prior = journal.verifiedAddress(name);
  if (prior) {
    await confirmCode(prior, name);
    return tronWeb.address.fromHex(normalizedTronAddress(prior, tronWeb));
  }

  // This is Shasta TEST money only. Never emit a deployment transaction when
  // the test wallet cannot cover its maximum configured fee limit.
  // In particular, a successful token deployment must not accidentally drain
  // the wallet before the separate NFT deployment.
  const availableSun = BigInt(await tronWeb.trx.getBalance(tronWeb.defaultAddress.base58));
  if (availableSun < 1_000_000_000n) {
    throw new Error('SHASTA_DEPLOYMENT_BUDGET_BELOW_1000_TRX_FOR_' + name +
      ': no transaction created or broadcast; replenish test TRX first');
  }

  // Build, sign and obtain the deterministic txID and contract address BEFORE
  // writing the intent. No network broadcast occurs in these two steps.
  const constructorABI = artifacts[name].abi.find(item => item.type === 'constructor');
  if (constructorABI?.inputs?.length !== 1 ||
      constructorABI.inputs[0].type !== 'address') {
    throw new Error('Unexpected constructor; refusing to create ' + name);
  }
  const unsigned = await tronWeb.transactionBuilder.createSmartContract({
    abi: artifacts[name].abi,
    bytecode: artifacts[name].bytecode.replace(/^0x/, ''),
    name,
    feeLimit: 1_000_000_000,
    callValue: 0,
    userFeePercentage: 100,
    originEnergyLimit: 10_000_000,
    funcABIV2: constructorABI,
    parametersV2: [governance]
  }, tronWeb.defaultAddress.base58);
  const signed = await tronWeb.trx.sign(unsigned);
  if (!signed?.signature?.length ||
      !/^[a-f0-9]{64}$/i.test(signed.txID ?? '') ||
      signed.txID.toLowerCase() !== unsigned.txID?.toLowerCase() ||
      !unsigned.contract_address || signed.raw_data_hex !== unsigned.raw_data_hex) {
    throw new Error('Unsigned or inconsistent Shasta contract creation; refusing broadcast');
  }
  if (typeof signed.raw_data?.expiration !== 'number' ||
      signed.raw_data.expiration <= Date.now()) {
    throw new Error('Pre-signed deployment transaction expired before journaling');
  }
  const expectedAddress = normalizedTronAddress(unsigned.contract_address, tronWeb);
  // Any process or I/O failure here MUST abort before sending. The journal
  // stores hashes and IDs only — NEVER the key, signature, or signed payload.
  await journal.markBroadcastUncertain(name, {
    txID: signed.txID,
    rawDataSha256: fingerprintRawTransaction(signed.raw_data_hex),
    expectedAddress
  });

  // Exactly one attempt with exactly this signed txID. Even an RPC error or
  // rejection remains ambiguous: we never create or transmit a replacement.
  let response;
  try {
    response = await tronWeb.trx.sendRawTransaction(signed);
  } catch (error) {
    throw new Error('Shasta broadcast outcome unknown for ' + name +
      ' txID ' + signed.txID + ': DO NOT REDEPLOY (' + error.message + ')');
  }
  if (!response?.result && response?.code !== 'DUP_TRANSACTION_ERROR') {
    throw new Error('Shasta node did not confirm acceptance of ' + signed.txID +
      ': DO NOT REDEPLOY; read-only reconciliation required');
  }

  for (let attempt = 0; attempt < 20; attempt++) {
    try {
      const result = await reconcileDeployment(journal, name, tronWeb);
      if (result.status === 'VERIFIED') return tronWeb.address.fromHex(result.address);
    } catch (error) {
      // An attestation mismatch or a confirmed failure must not be retried.
      if (/CHAIN_ATTESTATION_MISMATCH|CHAIN_EXECUTION_FAILED|CHAIN_CODE_NOT_VERIFIED/.test(error.message)) {
        throw error;
      }
      // Transient RPC errors must also never cause a second broadcast.
    }
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
  throw new Error('Shasta deployment unresolved for ' + name +
    ' txID ' + signed.txID + ': DO NOT REDEPLOY; run read-only reconciliation');
}

try {
  const tokenAddress = await deployOnce('MojCoin');
  const token = await tronWeb.contract().at(tokenAddress);
  const [name, symbol, supply] = await Promise.all([
    token.name().call(), token.symbol().call(), token.totalSupply().call()
  ]);
  if (String(name) !== 'Moj 1' || String(symbol) !== 'MOJ1' ||
      BigInt(supply.toString()) !== 100_000_000_000n * 10n ** 18n) {
    throw new Error('On-chain identity/supply verification failed; do not deploy NFT');
  }
  const distributorHex = String(await token.distributor().call());
  const distributorAddress = tronWeb.address.fromHex(distributorHex);
  // MojGenesisDistributor is CREATEd inside the MojCoin constructor. Its
  // ABI is not automatically published in Shasta getcontract, so attach the
  // compiled local ABI explicitly for read-only verification.
  const genesisArtifact = JSON.parse(await readFile(
    new URL('../build/contracts/MojGenesisDistributor.json', import.meta.url), 'utf8'));
  if (genesisArtifact.contractName !== 'MojGenesisDistributor' ||
      !genesisArtifact.abi?.some(x => x.type === 'function' && x.name === 'governance') ||
      !genesisArtifact.abi?.some(x => x.type === 'function' && x.name === 'distributed')) {
    throw new Error('Missing compiled genesis ABI; do not deploy NFT');
  }
  const distributor = tronWeb.contract(genesisArtifact.abi, distributorAddress);
  const [escrowed, governanceOnChain, distributed] = await Promise.all([
    token.balanceOf(distributorAddress).call(),
    distributor.governance().call(),
    distributor.distributed().call()
  ]);
  if (BigInt(escrowed.toString()) !== BigInt(supply.toString()) ||
      tronWeb.address.fromHex(String(governanceOnChain)) !== governance ||
      String(distributed) !== 'false') {
    throw new Error('Genesis escrow/governance verification failed; do not deploy NFT');
  }

  const nftAddress = await deployOnce('MojAssets');
  const nft = await tronWeb.contract().at(nftAddress);
  const nftOwner = tronWeb.address.fromHex(String(await nft.owner().call()));
  if (nftOwner !== governance) throw new Error('NFT owner verification failed');

  console.log(JSON.stringify({
    network: 'Shasta', tokenAddress, nftAddress, distributorAddress,
    name: String(name), symbol: String(symbol), supply: supply.toString(),
    escrowed: escrowed.toString(), distributed: false,
    journal: journalPath, state: 'BOTH_CONTRACTS_VERIFIED_NO_DISTRIBUTION'
  }, null, 2));
} finally {
  // A BROADCAST_UNCERTAIN journal entry survives errors and blocks any automatic retry.
  await journal.close();
}
