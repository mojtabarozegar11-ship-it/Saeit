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
const treasury = process.env.MOJ_SHASTA_TREASURY;
if (!tronWeb.isAddress(treasury ?? '')) {
  throw new Error('Set MOJ_SHASTA_TREASURY to a checked test wallet address');
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
    parameters: [treasury],
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
console.log(JSON.stringify({network: 'Shasta', tokenAddress, nftAddress, name: String(name), symbol: String(symbol), supply: supply.toString()}, null, 2));
