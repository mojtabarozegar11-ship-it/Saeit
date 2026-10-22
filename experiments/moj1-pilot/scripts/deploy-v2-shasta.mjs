// Shasta V2 PILOT ONLY: one new escrowed candidate, never Mainnet or a release.
// Private signing material comes only from the pre-existing restricted VPS pilot wallet.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {isAbsolute} from 'node:path';
import {openDeploymentJournal} from './deployment-journal.mjs';
import {normalizedTronAddress, fingerprintRawTransaction, reconcileDeployment} from './deployment-reconciler.mjs';
import {attestBytecode} from './bytecode-attestation.mjs';

if (process.env.MOJ1_V2_DEPLOY_CONFIRM !== 'SHASTA_V2_ESCROW_ONLY') {
  throw Error('V2 deployment requires SHASTA_V2_ESCROW_ONLY; never Mainnet or distribution');
}
const privateKey = process.env.TRON_PRIVATE_KEY;
if (!/^[0-9a-f]{64}$/i.test(privateKey ?? '')) throw Error('Dedicated Shasta pilot key required');
const journalPath = process.env.MOJ1_V2_DEPLOY_JOURNAL_PATH;
if (!journalPath || !isAbsolute(journalPath)) throw Error('Persistent absolute V2 deployment journal required');

const manifest = JSON.parse(await readFile(new URL('../shasta-deployment.json', import.meta.url), 'utf8'));
if (manifest.network !== 'Shasta' || manifest.rpc !== 'https://api.shasta.trongrid.io' ||
    manifest.chain_scope !== 'TESTNET_ONLY' || manifest.mainnet_deployed !== false ||
    manifest.allocation_distributed !== false || manifest.public_sale_enabled !== false ||
    manifest.real_payment_enabled !== false || manifest.mojplaywin_integration_mode !== 'READ_ONLY_STAGING' ||
    !Array.isArray(manifest.test_governance_owners) || manifest.test_governance_owners.length !== 3) {
  throw Error('SHASTA_TESTNET_NO_SALE_MANIFEST_REQUIRED');
}

const tron = new TronWeb({fullHost: manifest.rpc, privateKey});
const government = manifest.governance_contract;
if (!tron.isAddress(government) ||
    tron.address.toHex(tron.defaultAddress.base58) !== tron.address.toHex(manifest.deployer_public_wallet)) {
  throw Error('SHASTA_PILOT_GOVERNANCE_OR_WALLET_MISMATCH');
}
const governanceCode = await tron.trx.getContract(government);
if (!governanceCode?.bytecode) throw Error('2_OF_3_TEST_GOVERNANCE_NOT_DEPLOYED');
const governor = tron.contract((JSON.parse(await readFile(
  new URL('../build/contracts/MojPilotGovernance.json', import.meta.url),'utf8'))).abi, government);
const expectAddress = (actual, expected, label) => {
  if (normalizedTronAddress(String(actual), tron) !== normalizedTronAddress(expected, tron)) {
    throw Error(label + '_MISMATCH');
  }
};
const ownerHexes = manifest.test_governance_owners.map(x => normalizedTronAddress(x,tron));
if (new Set(ownerHexes).size !== 3) throw Error('DUPLICATE_TEST_GOVERNANCE_OWNER');
for (let i=0;i<3;i++) expectAddress(await governor.owners(i).call(),
  manifest.test_governance_owners[i], 'TEST_GOVERNANCE_OWNER_'+i);
if (!/^\d+$/.test(String(await governor.nonce().call()))) throw Error('TEST_GOVERNANCE_NONCE_MISSING');

const names = ['MojCoinGuarded','MojGenesisFactoryGuarded'];
const artifacts = {};
for (const name of names) {
  const a=JSON.parse(await readFile(new URL('../build/contracts/'+name+'.json', import.meta.url),'utf8'));
  if (a.contractName !== name || !a.compiler?.version?.startsWith('0.8.25') ||
      !Array.isArray(a.abi) || !/^(?:0x)?[0-9a-f]+$/i.test(a.bytecode ?? '')) {
    throw Error('V2_COMPILATION_INVALID_'+name);
  }
  artifacts[name]=a;
}
const expectedHash=createHash('sha256').update(JSON.stringify({
  abi:artifacts.MojCoinGuarded.abi,bytecode:artifacts.MojCoinGuarded.bytecode,
  factoryBytecode:artifacts.MojGenesisFactoryGuarded.bytecode
})).digest('hex');
const journal=await openDeploymentJournal(journalPath,{
  network:'Shasta',governance:normalizedTronAddress(government,tron),
  artifacts:{MojCoinGuarded:expectedHash}
});
const name='MojCoinGuarded';
async function deployOnce() {
  const pending=journal.pending(name);
  if (pending) {
    const r=await reconcileDeployment(journal,name,tron);
    if(r.status === 'VERIFIED') return tron.address.fromHex(r.address);
    throw Error('V2_TX_UNCERTAIN_DO_NOT_REDEPLOY_'+pending.txID);
  }
  const previous=journal.verifiedAddress(name);
  if(previous) return tron.address.fromHex(normalizedTronAddress(previous,tron));
  const available=BigInt(await tron.trx.getBalance(tron.defaultAddress.base58));
  if(available < 1_000_000_000n) throw Error('SHASTA_V2_BUDGET_NEEDS_1000_TEST_TRX');
  const constructor=artifacts[name].abi.find(x => x.type==='constructor');
  if(constructor?.inputs?.length!==1 || constructor.inputs[0].type!=='address') {
    throw Error('UNEXPECTED_V2_CONSTRUCTOR');
  }
  const unsigned=await tron.transactionBuilder.createSmartContract({
    abi:artifacts[name].abi,
    bytecode:artifacts[name].bytecode.replace(/^0x/,''),
    name, feeLimit:1_000_000_000, callValue:0, userFeePercentage:100,
    originEnergyLimit:10_000_000,funcABIV2:constructor,parametersV2:[government]
  },tron.defaultAddress.base58);
  const signed=await tron.trx.sign(unsigned);
  if(!signed?.signature?.length || !/^[0-9a-f]{64}$/i.test(signed.txID??'') ||
     signed.txID.toLowerCase()!==unsigned.txID?.toLowerCase() ||
     signed.raw_data_hex!==unsigned.raw_data_hex || !unsigned.contract_address ||
     typeof signed.raw_data?.expiration!=='number' || signed.raw_data.expiration<=Date.now()){
    throw Error('V2_TRANSACTION_SIGNING_OR_EXPIRY_INVALID');
  }
  await journal.markBroadcastUncertain(name,{
    txID:signed.txID,rawDataSha256:fingerprintRawTransaction(signed.raw_data_hex),
    expectedAddress:normalizedTronAddress(unsigned.contract_address,tron)
  });
  let reply;
  try {reply=await tron.trx.sendRawTransaction(signed);}
  catch(e){throw Error('V2_BROADCAST_OUTCOME_UNCERTAIN_DO_NOT_REDEPLOY_'+signed.txID);}
  if(!reply?.result && reply?.code!=='DUP_TRANSACTION_ERROR') {
    throw Error('V2_BROADCAST_UNCONFIRMED_DO_NOT_REDEPLOY_'+signed.txID);
  }
  for(let attempt=0;attempt<20;attempt++){
    try {
      const r=await reconcileDeployment(journal,name,tron);
      if(r.status==='VERIFIED') return tron.address.fromHex(r.address);
    } catch(error) {
      if(/CHAIN_ATTESTATION_MISMATCH|CHAIN_EXECUTION_FAILED|CHAIN_CODE_NOT_VERIFIED/.test(error.message)) {
        throw error;
      }
    }
    await new Promise(ok=>setTimeout(ok,3000));
  }
  throw Error('V2_FINALITY_NOT_VERIFIED_DO_NOT_REDEPLOY_'+signed.txID);
}
try {
  const tokenAddress=await deployOnce();
  const token=tron.contract(artifacts.MojCoinGuarded.abi,tokenAddress);
  const [nameValue,symbol,decimals,supply,factoryRaw]=await Promise.all([
    token.name().call(),token.symbol().call(),token.decimals().call(),
    token.totalSupply().call(),token.distributor().call()
  ]);
  const factoryAddress=tron.address.fromHex(normalizedTronAddress(String(factoryRaw),tron));
  const factory=tron.contract(artifacts.MojGenesisFactoryGuarded.abi,factoryAddress);
  const [balance,factoryToken,factoryGov,distributed]=await Promise.all([
    token.balanceOf(factoryAddress).call(),factory.token().call(),
    factory.governance().call(),factory.distributed().call()
  ]);
  const full=100_000_000_000n*10n**18n;
  if(String(nameValue)!=='Moj 1' || String(symbol)!=='MOJ1' ||
     String(decimals)!=='18' || BigInt(String(supply))!==full ||
     BigInt(String(balance))!==full || String(distributed)!=='false') {
    throw Error('V2_ESCROW_OR_SUPPLY_ATTESTATION_FAILED');
  }
  expectAddress(factoryToken,tokenAddress,'V2_FACTORY_TOKEN');
  expectAddress(factoryGov,government,'V2_FACTORY_GOVERNANCE');
  for(let i=0;i<6;i++){
    const slot=normalizedTronAddress(String(await factory.vaults(i).call()),tron);
    if(slot!=='41'+'0'.repeat(40)) throw Error('V2_DISTRIBUTION_VAULT_ALREADY_SET_'+i);
  }
  const tokenInfo=await tron.trx.getContractInfo(tokenAddress);
  const factoryInfo=await tron.trx.getContractInfo(factoryAddress);
  const tokenBytecode=attestBytecode({
    name:'MojCoinGuarded',artifact:artifacts.MojCoinGuarded,chainInfo:tokenInfo,
    constructorAddresses:[government],immutableAddresses:[factoryAddress],
    addressToHex:value=>tron.address.toHex(value)
  });
  const factoryBytecode=attestBytecode({
    name:'MojGenesisFactoryGuarded',artifact:artifacts.MojGenesisFactoryGuarded,
    chainInfo:factoryInfo,constructorAddresses:[government],
    immutableAddresses:[tokenAddress,government],factoryParentAttested:true,
    addressToHex:value=>tron.address.toHex(value)
  });
  console.log(JSON.stringify({
    result:'V2_SHASTA_ESCROW_ONLY_VERIFIED',network:'Shasta',
    tokenAddress,factoryAddress,governance:government,
    supplyWhole:'100000000000',escrowedWhole:'100000000000',distributed:false,
    bytecodeEvidence:[tokenBytecode,factoryBytecode],
    mainnet:false,publicSale:false,paymentTouched:false
  },null,2));
} finally {
  await journal.close();
}
