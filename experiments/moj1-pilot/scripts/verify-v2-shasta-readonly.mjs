// Public, keyless Shasta V2 attestation. Never imports keys, signs or broadcasts.
import {TronWeb} from 'tronweb';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {attestBytecode} from './bytecode-attestation.mjs';

const v1=JSON.parse(await readFile(new URL('../shasta-deployment.json',import.meta.url),'utf8'));
const v2=JSON.parse(await readFile(new URL('../shasta-v2-deployment.json',import.meta.url),'utf8'));
if(v1.network!=='Shasta' || v1.chain_scope!=='TESTNET_ONLY' ||
  v1.rpc!=='https://api.shasta.trongrid.io' || v1.mainnet_deployed!==false ||
  v1.public_sale_enabled!==false || v1.real_payment_enabled!==false ||
  v2.network!=='Shasta' || v2.chain_scope!=='TESTNET_ONLY' ||
  v2.version!=='V2_GUARDED_CANDIDATE' || v2.mainnet_deployed!==false ||
  v2.public_sale_enabled!==false || v2.real_payment_enabled!==false ||
  v2.distribution_enabled!==false ||
  v2.pilot_governance_contract!==v1.governance_contract ||
  v2.previous_V1_token_testnet!==v1.token_contract ||
  v2.candidate_token_contract===v1.token_contract) {
  throw Error('V2_SHASTA_TESTNET_ISOLATION_REQUIRED');
}
const tron=new TronWeb({fullHost:v1.rpc});
tron.setAddress(v1.deployer_public_wallet);
const artifactNames=['MojCoinGuarded','MojGenesisFactoryGuarded','MojCoin','MojGenesisDistributor','MojPilotGovernance'];
const a={};
for(const name of artifactNames){
  a[name]=JSON.parse(await readFile(new URL('../build/contracts/'+name+'.json',import.meta.url),'utf8'));
  if(a[name].contractName!==name || !a[name].abi?.length) throw Error('MISSING_COMPILED_ARTIFACT_'+name);
}
let lastRequest=0;
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function safeRead(label,fn){
  for(let i=0;i<6;i++){
    const delay=900-(Date.now()-lastRequest);
    if(delay>0)await pause(delay);
    lastRequest=Date.now();
    try{return await fn();}
    catch(e){
      if(!String(e?.message??e).includes('429') && e?.response?.status!==429)throw e;
      if(i===5)throw Error('SHASTA_RPC_RATE_LIMIT_'+label);
      await pause((i+1)*3500);
    }
  }
}
const at=(name,address)=>tron.contract(a[name].abi,address);
const view=(instance,name,...args)=>safeRead(name,()=>instance[name](...args).call());
const canonical=value=>tron.address.fromHex(tron.address.toHex(String(value)));
const checkAddr=(actual,expected,label)=>{
  if(canonical(actual)!==canonical(expected))throw Error(label+'_ADDRESS_MISMATCH');
};
const checkString=(actual,expected,label)=>{
  if(String(actual)!==String(expected))throw Error(label+'_MISMATCH');
};
const supply=100_000_000_000n*10n**18n;
const token=at('MojCoinGuarded',v2.candidate_token_contract);
const factory=at('MojGenesisFactoryGuarded',v2.candidate_genesis_factory);
const gov=at('MojPilotGovernance',v1.governance_contract);
const oldToken=at('MojCoin',v1.token_contract);
const oldEscrow=at('MojGenesisDistributor',v1.genesis_escrow);
for(let i=0;i<3;i++)checkAddr(await view(gov,'owners',i),v1.test_governance_owners[i],'PILOT_GOV_OWNER_'+i);
checkString(await view(token,'name'),'Moj 1','V2_NAME');
checkString(await view(token,'symbol'),'MOJ1','V2_SYMBOL');
checkString(await view(token,'decimals'),18,'V2_DECIMALS');
checkString(await view(token,'totalSupply'),supply.toString(),'V2_TOTAL_SUPPLY');
checkAddr(await view(token,'distributor'),v2.candidate_genesis_factory,'V2_ESCROW');
checkString(await view(token,'balanceOf',v2.candidate_genesis_factory),supply.toString(),'V2_ESCROW_BALANCE');
checkAddr(await view(factory,'token'),v2.candidate_token_contract,'V2_ESCROW_TOKEN');
checkAddr(await view(factory,'governance'),v1.governance_contract,'V2_ESCROW_GOVERNANCE');
checkString(await view(factory,'distributed'),false,'V2_DISTRIBUTED_FLAG');
for(let i=0;i<6;i++){
  const slot=tron.address.toHex(String(await view(factory,'vaults',i))).toLowerCase();
  if(slot!=='41'+'0'.repeat(40))throw Error('V2_VAULT_ALREADY_ASSIGNED_'+i);
}
checkString(await view(oldToken,'totalSupply'),supply.toString(),'V1_TOTAL_SUPPLY');
checkString(await view(oldToken,'balanceOf',v1.genesis_escrow),supply.toString(),'V1_ESCROW_BALANCE');
checkString(await view(oldEscrow,'distributed'),false,'V1_UNDISTRIBUTED_FLAG');
const bytecodes=[];
for(const part of [
  {name:'MojCoinGuarded',address:v2.candidate_token_contract,constructorAddresses:[v1.governance_contract],
   immutableAddresses:[v2.candidate_genesis_factory]},
  {name:'MojGenesisFactoryGuarded',address:v2.candidate_genesis_factory,
   constructorAddresses:[v1.governance_contract],
   immutableAddresses:[v2.candidate_token_contract,v1.governance_contract],
   factoryParentAttested:true}
]){
  const info=await safeRead('getContractInfo_'+part.name,()=>tron.trx.getContractInfo(part.address));
  bytecodes.push(attestBytecode({...part,artifact:a[part.name],chainInfo:info,
    addressToHex:addr=>tron.address.toHex(addr)}));
}
const evidence={
 status:'MOJ1_V2_PUBLIC_SHASTA_ATTESTED',network:'Shasta',mode:'PUBLIC_KEYLESS_READ_ONLY',
 token:v2.candidate_token_contract,factory:v2.candidate_genesis_factory,
 governance:v1.governance_contract,v1EscrowIntact:true,v2EscrowFullyFunded:true,
 wholeSupply:'100000000000',distributed:false,publicSale:false,mainnet:false,
 privateKeyUsed:false,broadcast:false,paymentsModified:false,bytecodeEvidence:bytecodes
};
await mkdir(new URL('../artifacts/',import.meta.url),{recursive:true});
await writeFile(new URL('../artifacts/v2-shasta-public-attestation.json',import.meta.url),
  JSON.stringify(evidence,null,2)+'\n',{mode:0o600});
console.log(JSON.stringify(evidence,null,2));
