// Shasta ONLY. There is deliberately no Mainnet deployment option.
// This script is NEVER invoked by CI. Running it can spend Shasta test TRX.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';
import {isAbsolute} from 'node:path';
import {createHash} from 'node:crypto';
import {openDeploymentJournal} from './deployment-journal.mjs';

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
  const prior = journal.verifiedAddress(name);
  if (prior) {
    await confirmCode(prior, name);
    return prior; // Reuses confirmed contracts, never rebroadcasts.
  }
  // Persist the ambiguity marker BEFORE starting a possibly irreversible broadcast.
  await journal.markBroadcastUncertain(name);
  const contract = await tronWeb.contract().new({
    abi: artifacts[name].abi,
    bytecode: artifacts[name].bytecode,
    parameters: [governance],
    feeLimit: 1_000_000_000,
    callValue: 0
  });
  const address = tronWeb.address.fromHex(contract.address);
  let found = false;
  for (let attempt = 0; attempt < 20; attempt++) {
    try {
      await confirmCode(address, name);
      found = true;
      break;
    } catch {
      // Shasta may not have indexed the deployment yet. Do NOT issue another deployment.
    }
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
  if (!found) {
    throw new Error(`Deployment uncertain for ${name}. Do not retry: reconcile journal and Shasta transaction externally.`);
  }
  await journal.markVerified(name, address);
  return address;
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
  const [escrowed, governanceOnChain] = await Promise.all([
    token.balanceOf(distributorAddress).call(),
    tronWeb.contract().at(distributorAddress).then(x => x.governance().call())
  ]);
  if (BigInt(escrowed.toString()) !== BigInt(supply.toString()) ||
      tronWeb.address.fromHex(String(governanceOnChain)) !== governance) {
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
