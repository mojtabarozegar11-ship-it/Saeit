// MANUAL OPERATOR ONLY: Shasta testnet, two disposable contracts, never MOJ1 itself.
// This script is NOT invoked from CI; no Mainnet URL, public sale, funding or payout path.
// A dedicated Shasta-only key must be supplied locally, NEVER in GitHub/chat/logs.
import {TronWeb} from 'tronweb';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {isAbsolute} from 'node:path';
import {openDeploymentJournal} from './deployment-journal.mjs';
import {reconcileDeployment,fingerprintRawTransaction,normalizedTronAddress} from './deployment-reconciler.mjs';
import {validateShastaRewardPlan,REWARD_DEPLOYMENT_ARTIFACTS,
  REWARD_TEST_TOKEN_NAME,REWARD_TEST_TOKEN_SYMBOL} from './reward-shasta-deploy-policy.mjs';

const endpoint='https://api.shasta.trongrid.io';
const manifest=JSON.parse(await readFile(new URL('../shasta-v2-deployment.json',import.meta.url),'utf8'));
const privateKey=process.env.MOJ1_SHASTA_DISPOSABLE_PRIVATE_KEY;
if(!/^[a-f0-9]{64}$/i.test(privateKey??'')) {
  throw new Error('DEDICATED_SHASTA_TEST_KEY_REQUIRED_OUTSIDE_CI_NO_MAINNET_KEY');
}
const web=new TronWeb({fullHost:endpoint,privateKey});
const plan=validateShastaRewardPlan(manifest,{
  confirmation:process.env.MOJ1_REWARD_SHASTA_CONFIRM,
  network:'Shasta',mode:'DISPOSABLE_TEST_ONLY',
  operatorAddress:process.env.MOJ1_REWARD_SHASTA_OPERATOR,
  governanceAddress:process.env.MOJ1_REWARD_SHASTA_GOVERNANCE,
  tokenName:REWARD_TEST_TOKEN_NAME,tokenSymbol:REWARD_TEST_TOKEN_SYMBOL,
  feeLimitSun:process.env.MOJ1_REWARD_SHASTA_FEE_LIMIT_SUN
});
if(normalizedTronAddress(web.defaultAddress.base58,web)!==
    normalizedTronAddress(plan.operatorAddress,web)){
  throw new Error('TEST_SIGNER_DOES_NOT_MATCH_PUBLIC_OPERATOR_ADDRESS');
}
if(process.env.MOJ1_REWARD_SHASTA_DEDICATED_WALLET!=='NO_MAINNET_FUNDS_OR_KEYS') {
  throw new Error('DEDICATED_SHASTA_WALLET_ATTESTATION_REQUIRED');
}
const journalPath=process.env.MOJ1_REWARD_SHASTA_JOURNAL_PATH;
if(!journalPath||!isAbsolute(journalPath)||/^\/(?:tmp|var\/tmp)\//.test(journalPath)) {
  throw new Error('PRIVATE_PERSISTENT_ABSOLUTE_JOURNAL_REQUIRED');
}
// A contract with bytecode is not necessarily the approved 2-of-3 pilot governor.
const governorInfo=await web.trx.getContractInfo(plan.governanceAddress);
if(typeof governorInfo?.runtimecode!=='string'||governorInfo.runtimecode.length<4){
  throw new Error('SHASTA_GOVERNOR_RUNTIME_CODE_MISSING');
}
const govArtifact=JSON.parse(await readFile(
  new URL('../build/contracts/MojPilotGovernance.json',import.meta.url),'utf8'));
if(govArtifact.contractName!=='MojPilotGovernance') throw new Error('BAD_GOVERNOR_ABI');
const gov=web.contract(govArtifact.abi,plan.governanceAddress);
const owners=(process.env.MOJ1_REWARD_SHASTA_GOV_OWNERS??'').split(',').map(s=>s.trim());
if(owners.length!==3||owners.some(a=>!TronWeb.isAddress(a))||
   new Set(owners.map(a=>normalizedTronAddress(a,web))).size!==3){
  throw new Error('EXACTLY_THREE_DISTINCT_GOVERNANCE_TEST_SIGNERS_REQUIRED');
}
for(let i=0;i<3;i++){
  const actual=String(await gov.owners(i).call());
  if(normalizedTronAddress(actual,web)!==normalizedTronAddress(owners[i],web)){
    throw new Error('SHASTA_GOVERNOR_OWNER_MISMATCH_'+i);
  }
}
if(!/^[0-9]+$/.test(String(await gov.nonce().call()))){
  throw new Error('SHASTA_GOVERNOR_NONCE_UNAVAILABLE');
}
const artifacts={};
const hashes={};
for(const name of REWARD_DEPLOYMENT_ARTIFACTS){
  const artifact=JSON.parse(await readFile(
    new URL('../build/contracts/'+name+'.json',import.meta.url),'utf8'));
  if(artifact.contractName!==name||!Array.isArray(artifact.abi)||
     !/^(?:0x)?(?:[a-f0-9]{2})+$/i.test(artifact.bytecode??'')){
    throw new Error('PINNED_REWARD_ARTIFACT_MISSING_'+name);
  }
  artifacts[name]=artifact;
  hashes[name]=createHash('sha256').update(
    JSON.stringify({abi:artifact.abi,bytecode:artifact.bytecode})).digest('hex');
}
const journal=await openDeploymentJournal(journalPath,{
  network:'Shasta',
  governance:normalizedTronAddress(plan.governanceAddress,web),
  artifacts:hashes
});
const fee=BigInt(plan.feeLimitSun);
async function deployOnce(name,params,remaining){
  if(journal.pending(name)){
    const result=await reconcileDeployment(journal,name,web);
    if(result.status==='VERIFIED') return web.address.fromHex(result.address);
    throw new Error('PRIOR_SHASTA_BROADCAST_UNRESOLVED_'+name+'_DO_NOT_REDEPLOY');
  }
  const prior=journal.verifiedAddress(name);
  if(prior){
    const info=await web.trx.getContractInfo(prior);
    if(!info?.runtimecode||info.runtimecode.length<4) throw new Error('PRIOR_CONTRACT_CODE_MISSING_'+name);
    return web.address.fromHex(normalizedTronAddress(prior,web));
  }
  const balance=BigInt(await web.trx.getBalance(plan.operatorAddress));
  if(balance<fee*BigInt(remaining)){
    throw new Error('SHASTA_TEST_TRX_BELOW_CONFIGURED_TWO_CONTRACT_FEE_CEILING');
  }
  const artifact=artifacts[name];
  const constructor=artifact.abi.find(x=>x.type==='constructor');
  if(!constructor||constructor.inputs?.length!==params.length||
     (params.length===2&&!constructor.inputs.every(x=>x.type==='address'))||
     (params.length===0&&name!=='MojRewardTestToken')){
    throw new Error('UNEXPECTED_TEST_ONLY_CONSTRUCTOR_'+name);
  }
  const unsigned=await web.transactionBuilder.createSmartContract({
    abi:artifact.abi,bytecode:artifact.bytecode.replace(/^0x/,''),
    name,feeLimit:Number(fee),callValue:0,userFeePercentage:100,
    originEnergyLimit:10_000_000,funcABIV2:constructor,parametersV2:params
  },plan.operatorAddress);
  const signed=await web.trx.sign(unsigned);
  if(!signed?.signature?.length||!/^[a-f0-9]{64}$/i.test(signed.txID??'')||
     signed.txID.toLowerCase()!==unsigned.txID?.toLowerCase()||
     signed.raw_data_hex!==unsigned.raw_data_hex||
     !unsigned.contract_address||typeof signed.raw_data?.expiration!=='number'||\n     signed.raw_data.expiration<=Date.now()){
    throw new Error('SHASTA_SIGNED_TX_ATTESTATION_FAILED_'+name);
  }
  const expectedAddress=normalizedTronAddress(unsigned.contract_address,web);
  await journal.markBroadcastUncertain(name,{
    txID:signed.txID,rawDataSha256:fingerprintRawTransaction(signed.raw_data_hex),
    expectedAddress
  });
  // The ONLY broadcast attempt for this txID. A timeout is ambiguous; never auto-repeat.
  let accepted;
  try{accepted=await web.trx.sendRawTransaction(signed)}
  catch(error){throw new Error('SHASTA_BROADCAST_UNCERTAIN_'+name+'_DO_NOT_REDEPLOY')}
  if(!accepted?.result&&accepted?.code!=='DUP_TRANSACTION_ERROR'){
    throw new Error('SHASTA_NODE_ACCEPTANCE_UNKNOWN_'+name+'_DO_NOT_REDEPLOY');
  }
  for(let attempt=0;attempt<20;attempt++){
    try{
      const result=await reconcileDeployment(journal,name,web);
      if(result.status==='VERIFIED') return web.address.fromHex(result.address);
    }catch(error){
      if(/CHAIN_ATTESTATION_MISMATCH|CHAIN_EXECUTION_FAILED|CHAIN_CODE_NOT_VERIFIED/.test(error.message)) throw error;
    }
    await new Promise(resolve=>setTimeout(resolve,3000));
  }
  throw new Error('SHASTA_RECEIPT_UNRESOLVED_'+name+'_DO_NOT_REDEPLOY');
}
try{
  const tokenAddress=await deployOnce('MojRewardTestToken',[],2);
  const token=web.contract(artifacts.MojRewardTestToken.abi,tokenAddress);
  const [name,symbol,supply]=await Promise.all([
    token.name().call(),token.symbol().call(),token.totalSupply().call()
  ]);
  if(String(name)!==REWARD_TEST_TOKEN_NAME||String(symbol)!==REWARD_TEST_TOKEN_SYMBOL||
     BigInt(supply.toString())!==1_000_000n*10n**18n){
    throw new Error('NON_MOJ1_TEST_TOKEN_IDENTITY_MISMATCH_STOP');
  }
  const escrowAddress=await deployOnce('MojRewardClaimsPilot',
    [tokenAddress,plan.governanceAddress],1);
  const escrow=web.contract(artifacts.MojRewardClaimsPilot.abi,escrowAddress);
  const [contractToken,contractGovernor,liability,available]=await Promise.all([
    escrow.token().call(),escrow.governance().call(),
    escrow.outstandingCommitments().call(),escrow.availableToCommit().call()
  ]);
  if(normalizedTronAddress(String(contractToken),web)!==normalizedTronAddress(tokenAddress,web)||
     normalizedTronAddress(String(contractGovernor),web)!==
       normalizedTronAddress(plan.governanceAddress,web)||
     BigInt(liability.toString())!==0n||BigInt(available.toString())!==0n){
    throw new Error('SHASTA_REWARD_ESCROW_CONSTRUCTOR_OR_ZERO_BALANCE_MISMATCH');
  }
  process.stdout.write(JSON.stringify({
    network:'Shasta',tokenKind:'DISPOSABLE_NON_MOJ1',testTokenAddress:tokenAddress,
    rewardEscrowAddress:escrowAddress,governanceAddress:plan.governanceAddress,
    artifactSha256:hashes,feeLimitSun:plan.feeLimitSun,
    stage:'TWO_CONTRACTS_DEPLOYED_NOT_FUNDED',noFunding:true,noClaims:true,
    mainnetAuthorized:false,independentAudit:'PENDING'
  },null,2)+'\n');
}finally{
  await journal.close();
}
