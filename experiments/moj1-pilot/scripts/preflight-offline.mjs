// Offline only. Checks compiled contract artifacts before any Shasta transaction.
// This file does not create a wallet, read a private key, or use a network.
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const specs = [
  {name: 'MojCoin', args: 1, functions: ['name', 'symbol', 'decimals', 'totalSupply', 'balanceOf', 'transfer', 'approve', 'distributor']},
  {name: 'MojAssets', args: 1, functions: ['safeMint', 'tokenURI', 'owner', 'transferFrom']},
  {name: 'MojVestingVault', args: 6, functions: ['beneficiary', 'allocation', 'start', 'cliff', 'duration', 'released', 'vestedAt', 'fullyFunded', 'releasable', 'release']},
  {name: 'MojGenesisDistributor', args: 1, functions: ['governance', 'token', 'distributed', 'vaults', 'bucketAmount', 'distribute']},
  {name: 'MojApprovalReserve', args: 4, functions: ['beneficiary', 'releaseController', 'allocation', 'fullyFunded', 'scheduleRelease', 'cancelRelease', 'executeRelease']}
];

const contractReports = [];
for (const {name, args, functions} of specs) {
  const artifact = JSON.parse(await readFile(new URL(`../build/contracts/${name}.json`, import.meta.url), 'utf8'));
  if (artifact.contractName !== name || !artifact.compiler?.version?.startsWith('0.8.25')) {
    throw new Error(`${name}: unexpected contract or compiler version`);
  }
  const ctor = artifact.abi.find(x => x.type === 'constructor');
  if ((ctor?.inputs?.length ?? 0) !== args) throw new Error(`${name}: unexpected constructor`);
  if (!/^(?:0x)?(?:[0-9a-fA-F]{2})+$/.test(artifact.bytecode ?? '') || artifact.bytecode.length < 500) {
    throw new Error(`${name}: invalid or missing compiled bytecode`);
  }
  const abiFunctions = new Set(artifact.abi.filter(x => x.type === 'function').map(x => x.name));
  for (const functionName of functions) {
    if (!abiFunctions.has(functionName)) throw new Error(`${name}: missing ${functionName} function`);
  }
  if (name === 'MojCoin' && [...abiFunctions].some(x => /^(mint|setMinter|freeze|upgradeTo)$/.test(x))) {
    throw new Error('Token has a prohibited supply/admin function');
  }
  if (name === 'MojVestingVault' && [...abiFunctions].some(x => /^(revoke|recover|setBeneficiary|upgradeTo)$/.test(x))) {
    throw new Error('Vesting vault contains a privileged backdoor');
  }
  if (name === 'MojGenesisDistributor' && [...abiFunctions].some(x => /^(withdraw|recover|setGovernance|upgradeTo)$/.test(x))) {
    throw new Error('Genesis escrow contains a privileged bypass');
  }
  contractReports.push({name, compiler: artifact.compiler.version.split('+')[0], bytecodeSha256: createHash('sha256').update(artifact.bytecode).digest('hex')});
}

const deploySource = await readFile(new URL('./deploy-shasta.mjs', import.meta.url), 'utf8');
if (!deploySource.includes('https://api.shasta.trongrid.io') ||
    !deploySource.includes("MOJ1_DEPLOY_CONFIRM !== 'SHASTA_ONLY'") ||
    /https:\/\/api\.trongrid\.io(?!\.shasta)/.test(deploySource)) {
  throw new Error('Deployment is not strictly gated to Shasta');
}

console.log(JSON.stringify({status: 'OFFLINE_PREFLIGHT_PASS', network: 'SHASTA_ONLY', noBroadcast: true, contracts: contractReports}, null, 2));
