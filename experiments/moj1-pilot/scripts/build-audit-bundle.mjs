// Deterministic, keyless input packet for an external contract auditor.
// This copies only an explicit allowlist of public source, TVM evidence, and compiled output.
// It is NOT an audit, signature, acceptance, or Mainnet deployment authorization.
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {join,dirname,resolve,sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('..',import.meta.url));
const out=resolve(root,'artifacts','audit-bundle');
const names=[
  'contracts/MojCoin.sol','contracts/MojGenesisDistributor.sol',
  'contracts/MojCoinGuarded.sol','contracts/MojGenesisFactoryGuarded.sol',
  'contracts/MojVestingVault.sol','contracts/MojApprovalReserve.sol',
  'contracts/MojPilotGovernance.sol','contracts/MojAssets.sol',
  'contracts/test/MojVestingLookalike.sol',
  'contracts/test/MojApprovalReserveClockHarness.sol',
  'tests/tronbox/vesting.integration.js',
  'tests/tronbox/genesis-guarded.integration.js',
  'tests/guarded-factory-policy.test.mjs',
  'tests/release-readiness-offline.test.mjs',
  'scripts/preflight-offline.mjs',
  'scripts/release-readiness-offline.mjs',
  'F08_GENESIS_DESTINATION_FORGERY_AND_V2_2026-10-22.md',
  'V2_AUDIT_HANDOFF_AND_ENERGY_2026-10-22.md',
  'SECURITY_REVIEW_2026-10-21.md','LEGAL_AND_RISK.md',
  'RELEASE_SCHEDULE_PROPOSAL_2026-10-21.md',
  'tokenomics.json','shasta-deployment.json',
  'tronbox-config.js','package.json','package-lock.json',
  'artifacts/moj1-v2-local-energy.json'
];
for(const n of [
  'MojCoin','MojGenesisDistributor','MojCoinGuarded','MojGenesisFactoryGuarded',
  'MojVestingVault','MojApprovalReserve','MojPilotGovernance','MojAssets',
  'MojVestingLookalike','MojApprovalReserveClockHarness'
]) names.push('build/contracts/'+n+'.json');
names.push('artifacts/v2-shasta-energy-readonly.json');
const files=[];
for(const name of names.sort()) {
  if(name.includes('..')||name.startsWith('/'))throw Error('UNSAFE_AUDIT_PATH');
  let data;
  try {data=await readFile(resolve(root,name));}
  catch(error) {
    // Unavailable keyless Shasta RPC must be recorded as unavailable, not invented.
    if(name==='artifacts/v2-shasta-energy-readonly.json' && error?.code==='ENOENT')continue;
    throw error;
  }
  const destination=resolve(out,name);
  if(!destination.startsWith(out+sep))throw Error('AUDIT_DESTINATION_ESCAPE');
  await mkdir(dirname(destination),{recursive:true});
  await writeFile(destination,data,{mode:0o600});
  files.push({path:name,sha256:createHash('sha256').update(data).digest('hex'),bytes:data.length});
}
const commit=process.env.GITHUB_SHA??null;
const evidence={
  project:'MOJ1',packet:'GUARDED_V2_INDEPENDENT_AUDITOR_INTAKE',
  createdAt:new Date().toISOString(),sourceCommit:commit,
  environment:'PUBLIC_GITHUB_ACTIONS_DISPOSABLE_LOCAL_TVM',
  status:'INTERNAL_EVIDENCE_ONLY__NOT_THIRD_PARTY_AUDITED',
  shastaV1ImmutableUnchanged:true,
  shastaV2Deployed:false,mainnetDeployed:false,realSaleEnabled:false,
  independentSecurityAudit:false,legalApproval:false,
  externalSignaturesIncluded:false,
  sourceFiles:files
};
await writeFile(join(out,'MANIFEST.json'),JSON.stringify(evidence,null,2)+'\n',{mode:0o600});
await writeFile(join(out,'SHA256SUMS'),files.map(f=>f.sha256+'  '+f.path).join('\n')+'\n',{mode:0o600});
console.log(JSON.stringify({
  status:'AUDIT_INPUT_PACKET_BUILT',count:files.length,
  sourceCommit:commit,unverifiedExternalApproval:true,
  shastaV2Deployed:false,mainnet:false,sale:false
}));
