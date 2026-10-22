// Keyless, read-only verification of MOJ1's published Shasta deployment.
// Never sign, broadcast, distribute, mint or access the MojPlayWin payment database.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';
import {attestBytecode} from './bytecode-attestation.mjs';

const manifest = JSON.parse(await readFile(new URL('../shasta-deployment.json', import.meta.url),'utf8'));
if (manifest.network !== 'Shasta' || manifest.chain_scope !== 'TESTNET_ONLY' ||
    manifest.rpc !== 'https://api.shasta.trongrid.io' ||
    manifest.public_sale_enabled !== false || manifest.real_payment_enabled !== false ||
    manifest.mojplaywin_integration_mode !== 'READ_ONLY_STAGING') {
  throw Error('Shasta-only no-sale staging manifest required');
}
const tron = new TronWeb({fullHost:'https://api.shasta.trongrid.io'});
// Constant eth_call on TRON needs a public owner_address, even for unsigned reads.
// setAddress never imports a key or signs a transaction.
if (!tron.isAddress(manifest.deployer_public_wallet)) throw Error('PUBLIC_CALLER_INVALID');
tron.setAddress(manifest.deployer_public_wallet);
const artifacts = {};
for (const contract of ['MojPilotGovernance','MojCoin','MojGenesisDistributor','MojAssets']) {
  const a = JSON.parse(await readFile(new URL('../build/contracts/'+contract+'.json',import.meta.url),'utf8'));
  if(a.contractName!==contract || !Array.isArray(a.abi)) throw Error('ABI_MISSING_'+contract);
  artifacts[contract]=a;
}
const canonical = value => tron.address.fromHex(tron.address.toHex(String(value)));
const requireSame = (a,b,label) => { if(canonical(a)!==canonical(b)) throw Error(label+'_MISMATCH'); };
const requireEqual = (a,b,label) => { if(String(a)!==String(b)) throw Error(label+'_MISMATCH'); };
const contract = (name,address) => tron.contract(artifacts[name].abi,address);
// The public Shasta RPC rate-limits bursty GitHub runner IPs. Read sequentially,
 // retrying only transient 429s; never issue transactions.
const pause = ms => new Promise(resolve => setTimeout(resolve,ms));
let lastRead = 0;
async function readOnlyWithRetry(fn,label) {
  for (let attempt=0;attempt<6;attempt++) {
    const remaining = 850-(Date.now()-lastRead);
    if (remaining>0) await pause(remaining);
    lastRead=Date.now();
    try { return await fn(); }
    catch (error) {
      if (Number(error?.response?.status)!==429 && !String(error?.message??'').includes('429')) throw error;
      if (attempt===5) throw Error('SHASTA_RPC_RATE_LIMIT_'+label);
      await pause(3500*(attempt+1));
    }
  }
}
const view = (instance,method,...args) =>
  readOnlyWithRetry(()=>instance[method](...args).call(),method);
const governor = contract('MojPilotGovernance',manifest.governance_contract);
const token = contract('MojCoin',manifest.token_contract);
const escrow = contract('MojGenesisDistributor',manifest.genesis_escrow);
const nft = contract('MojAssets',manifest.nft_contract);
// Require exact source-to-chain creation code and runtime code (with validated
// immutable address slots). This also covers the constructor-created escrow.
const bytecodeEvidence = [];
const deployed = [
  {name:'MojPilotGovernance', address:manifest.governance_contract,
   constructorAddresses:manifest.test_governance_owners, immutableAddresses:[]},
  {name:'MojCoin', address:manifest.token_contract,
   constructorAddresses:[manifest.governance_contract], immutableAddresses:[manifest.genesis_escrow]},
  {name:'MojGenesisDistributor', address:manifest.genesis_escrow,
   constructorAddresses:[manifest.governance_contract],
   immutableAddresses:[manifest.token_contract,manifest.governance_contract]},
  {name:'MojAssets', address:manifest.nft_contract,
   constructorAddresses:[manifest.governance_contract], immutableAddresses:[]}
];
for (const item of deployed) {
  const info = await readOnlyWithRetry(
    () => tron.trx.getContractInfo(item.address), 'CODE_'+item.name);
  bytecodeEvidence.push(attestBytecode({
    ...item, artifact:artifacts[item.name], chainInfo:info,
    addressToHex:address => tron.address.toHex(address)
  }));
}
for(let i=0;i<3;i++) requireSame(await view(governor,'owners',i),manifest.test_governance_owners[i],'GOVERNANCE_OWNER_'+i);
requireEqual(await view(governor,'nonce'),0,'GOVERNANCE_NONCE');
const name=await view(token,'name');
const symbol=await view(token,'symbol');
const decimals=await view(token,'decimals');
const supply=await view(token,'totalSupply');
const dist=await view(token,'distributor');
const escrowAmount=await view(token,'balanceOf',manifest.genesis_escrow);
const govAddress=await view(escrow,'governance');
const distributed=await view(escrow,'distributed');
const nftName=await view(nft,'name');
const nftSymbol=await view(nft,'symbol');
const nftOwner=await view(nft,'owner');
const maxItems=await view(nft,'MAX_ITEMS');
requireEqual(name,manifest.name,'TOKEN_NAME');
requireEqual(symbol,manifest.symbol,'TOKEN_SYMBOL');
requireEqual(decimals,manifest.decimals,'TOKEN_DECIMALS');
const expected = BigInt(manifest.total_supply_whole)*10n**BigInt(manifest.decimals);
requireEqual(supply.toString(),expected.toString(),'FIXED_SUPPLY');
requireEqual(escrowAmount.toString(),expected.toString(),'GENESIS_ESCROW_CONSERVATION');
requireSame(dist,manifest.genesis_escrow,'DISTRIBUTOR');
requireSame(govAddress,manifest.governance_contract,'DISTRIBUTOR_GOVERNANCE');
requireEqual(distributed,false,'GENESIS_NOT_DISTRIBUTED');
requireEqual(nftName,'Moj Digital Assets','NFT_NAME');
requireEqual(nftSymbol,'MOJA','NFT_SYMBOL');
requireSame(nftOwner,manifest.governance_contract,'NFT_OWNER');
requireEqual(maxItems,10000,'NFT_LIMIT');
console.log(JSON.stringify({
  mode:'MOJ1_SHASTA_PUBLIC_READ_ONLY',status:'PASS',token:manifest.token_contract,
  escrow:manifest.genesis_escrow,governance:manifest.governance_contract,
  nft:manifest.nft_contract,totalWholeTokens:manifest.total_supply_whole,
  escrowFullyFunded:true,distributed:false,bytecodeEvidence,mainnet:false,privateKeyUsed:false,
  paymentsModified:false
},null,2));
