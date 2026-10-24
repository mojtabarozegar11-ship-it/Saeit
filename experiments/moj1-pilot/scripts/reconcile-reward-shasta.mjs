// Keyless recovery of a Shasta-only disposable reward deployment journal.
// Only reads public Shasta RPC. No private keys, signing, funding or broadcasting.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {isAbsolute} from 'node:path';
import {openDeploymentJournal} from './deployment-journal.mjs';
import {reconcileDeployment,normalizedTronAddress} from './deployment-reconciler.mjs';
import {REWARD_DEPLOYMENT_ARTIFACTS} from './reward-shasta-deploy-policy.mjs';

const path=process.env.MOJ1_REWARD_SHASTA_JOURNAL_PATH;
if(!path||!isAbsolute(path)) throw new Error('PERSISTENT_ABSOLUTE_TESTNET_REWARD_JOURNAL_REQUIRED');
const stored=JSON.parse(await readFile(path,'utf8'));
const v2=JSON.parse(await readFile(new URL('../shasta-v2-deployment.json',import.meta.url),'utf8'));
const web=new TronWeb({fullHost:'https://api.shasta.trongrid.io'});
if(stored.version!==1||stored.network!=='Shasta'||v2.network!=='Shasta'||
   v2.distribution_enabled!==false||v2.mainnet_deployed!==false||
   normalizedTronAddress(stored.governance,web)!==
   normalizedTronAddress(v2.pilot_governance_contract,web)){
  throw new Error('SHASTA_REWARD_JOURNAL_NETWORK_OR_GOVERNOR_MISMATCH');
}
const hashes={};
for(const name of REWARD_DEPLOYMENT_ARTIFACTS){
  const artifact=JSON.parse(await readFile(
    new URL('../build/contracts/'+name+'.json',import.meta.url),'utf8'));
  if(artifact.contractName!==name||!artifact.abi||!artifact.bytecode){
    throw new Error('MISSING_PINNED_REWARD_ARTIFACT_'+name);
  }
  hashes[name]=createHash('sha256').update(
    JSON.stringify({abi:artifact.abi,bytecode:artifact.bytecode})).digest('hex');
}
const journal=await openDeploymentJournal(path,{
  network:'Shasta',governance:stored.governance,artifacts:hashes
});
try{
  const result=[];
  for(const name of REWARD_DEPLOYMENT_ARTIFACTS){
    if(journal.pending(name)) result.push({name,...await reconcileDeployment(journal,name,web)});
    else {
      const prior=journal.verifiedAddress(name);
      if(!prior) result.push({name,status:'NOT_STARTED'});
      else {
        const contract=await web.trx.getContractInfo(prior);
        if(!contract?.runtimecode||contract.runtimecode.length<4){
          throw new Error('VERIFIED_JOURNAL_ADDRESS_MISSING_SHASTA_RUNTIME_'+name);
        }
        result.push({name,status:'ALREADY_VERIFIED',address:prior});
      }
    }
  }
  process.stdout.write(JSON.stringify({
    network:'Shasta',mode:'DISPOSABLE_REWARD_READ_ONLY_RECONCILIATION',
    noPrivateKey:true,noTransactionBroadcast:true,realMOJ1Funded:false,
    mainnetAuthorized:false,result
  },null,2)+'\n');
}finally{await journal.close();}
