// Shasta ONLY. There is deliberately no Mainnet deployment option.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';

if (process.env.MOJ1_DEPLOY_CONFIRM !== 'SHASTA_ONLY') {
  throw new Error('Deployment requires MOJ1_DEPLOY_CONFIRM=SHASTA_ONLY');
}
const testKey = process.env.TRON_PRIVATE_KEY;
if (!/^[a-fA-F0-9]{64}$/.test(testKey ?? '')) {
  throw new Error('Use a dedicated 64-hex-character Shasta-only test wallet key');
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

async function deploy(name) {
  const file = new URL(`../build/contracts/${name}.json`, import.meta.url);
  const artifact = JSON.parse(await readFile(file, 'utf8'));
  if (!Array.isArray(artifact.abi) || !/^(0x)?[a-fA-F0-9]+$/.test(artifact.bytecode ?? '')) {
    throw new Error(`Invalid compiled artifact for ${name}`);
  }
  const contract = await tronWeb.contract().new({
    abi: artifact.abi,
    bytecode: artifact.bytecode,
    parameters: [governance],
    feeLimit: 1_000_000_000,
    callValue: 0
  });
  const address = tronWeb.address.fromHex(contract.address);
  for (let attempt = 0; attempt < 20; attempt++) {
    try {
      const result = await tronWeb.trx.getContract(address);
      if (result.contract_address && result.bytecode) return address;
    } catch { /* The Shasta node may not have indexed the transaction. */ }
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  throw new Error(`Cannot independently retrieve ${name} on Shasta: ${address}`);
}

const tokenAddress = await deploy('MojCoin');
const nftAddress = await deploy('MojAssets');
const token = await tronWeb.contract().at(tokenAddress);
const [name, symbol, supply] = await Promise.all([
  token.name().call(), token.symbol().call(), token.totalSupply().call()
]);
if (String(name) !== 'Moj 1' || String(symbol) !== 'MOJ1' || BigInt(supply.toString()) !== 100_000_000_000n * 10n ** 18n) {
  throw new Error('On-chain identity/supply verification failed');
}
const distributorHex = String(await token.distributor().call());
const distributorAddress = tronWeb.address.fromHex(distributorHex);
const [escrowed, governanceOnChain] = await Promise.all([
  token.balanceOf(distributorAddress).call(),
  tronWeb.contract().at(distributorAddress).then(x => x.governance().call())
]);
if (BigInt(escrowed.toString()) !== BigInt(supply.toString()) ||
    tronWeb.address.fromHex(String(governanceOnChain)) !== governance) {
  throw new Error('Genesis escrow/governance verification failed; do not proceed');
}
console.log(JSON.stringify({network: 'Shasta', tokenAddress, nftAddress, distributorAddress,
  name: String(name), symbol: String(symbol), supply: supply.toString(),
  escrowed: escrowed.toString(), distributed: false}, null, 2));
