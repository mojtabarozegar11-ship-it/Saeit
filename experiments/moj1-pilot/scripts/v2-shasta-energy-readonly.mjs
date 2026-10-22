// Keyless Shasta energy simulation. ZERO private keys, signatures or transactions.
// Shasta may refuse to estimate contract creation; in that case output UNAVAILABLE.
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {TronWeb} from 'tronweb';
const root=fileURLToPath(new URL('..',import.meta.url));
const output=resolve(root,'artifacts','v2-shasta-energy-readonly.json');
const manifest=JSON.parse(await readFile(resolve(root,'shasta-deployment.json'),'utf8'));
const artifact=JSON.parse(await readFile(resolve(root,'build/contracts/MojCoinGuarded.json'),'utf8'));
if(process.env.MOJ1_SHASTA_ENERGY_READONLY!=='YES_KEYLESS_NO_BROADCAST')throw Error('EXPLICIT_READONLY_OPT_IN_REQUIRED');
if(manifest.rpc!=='https://api.shasta.trongrid.io'||
  manifest.chain_scope!=='TESTNET_ONLY'||manifest.network!=='Shasta'||
  manifest.mainnet_deployed!==false||manifest.public_sale_enabled!==false||
  manifest.real_payment_enabled!==false||manifest.allocation_distributed!==false)throw Error('TESTNET_ONLY_PILOT_MANIFEST_REQUIRED');
if(artifact.contractName!=='MojCoinGuarded'||!(/^(?:0x)?[0-9a-f]+$/i.test(artifact.bytecode)))throw Error('GUARDED_SOURCE_NOT_COMPILED');
const tron=new TronWeb({fullHost:manifest.rpc});
if(!tron.isAddress(manifest.deployer_public_wallet)||!tron.isAddress(manifest.governance_contract))throw Error('BAD_PUBLIC_ADDRESS');
const owner=tron.address.toHex(manifest.deployer_public_wallet);
const ctor=tron.address.toHex(manifest.governance_contract).slice(2).padStart(64,'0');
const data=artifact.bytecode.replace(/^0x/i,'')+ctor;
if(data.length>220000)throw Error('DEPLOYMENT_SIMULATION_DATA_TOO_LARGE');
const resultObj={
  mode:'KEYLESS_SHASTA_CONTRACT_CREATION_SIMULATION_ONLY',network:'Shasta',
  tokenCandidate:'MojCoinGuarded',
  constructorGovernancePublicAddress:manifest.governance_contract,
  invocation:'wallet/triggerconstantcontract',status:'UNAVAILABLE',
  energyUsed:null,costQuoteTrx:null,noSigning:true,noBroadcast:true,
  noFundsSpent:true,mainnet:false,realSale:false
};
try {
  const resp=await fetch(manifest.rpc+'/wallet/triggerconstantcontract',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({owner_address:owner,visible:false,data,call_value:0}),
    signal:AbortSignal.timeout(25000)
  });
  if(!resp.ok)throw Error('SHASTA_RPC_HTTP_'+resp.status);
  const body=await resp.json();
  const energy=Number(body?.energy_used);
  if(body?.result?.result===true && Number.isSafeInteger(energy) && energy>0){
    resultObj.status='SIMULATION_RETURNED_ENERGY';
    resultObj.energyUsed=energy;
  }else{
    const detail=body?.result?.message??body?.result?.code??'SIMULATOR_NO_SUCCESSFUL_ENERGY';
    resultObj.reason=String(detail).slice(0,160);
  }
}catch(error){resultObj.reason=String(error?.message??error).slice(0,160);}
await mkdir(dirname(output),{recursive:true});
await writeFile(output,JSON.stringify(resultObj,null,2)+'\n',{mode:0o600});
console.log(JSON.stringify(resultObj));
