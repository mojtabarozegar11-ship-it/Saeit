import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {join,resolve,dirname} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {openDeploymentJournal} from '../scripts/deployment-journal.mjs';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const script=resolve(root,'scripts/deploy-v2-shasta.mjs');
function attempt(overrides={}){
  return spawnSync(process.execPath,[script],{
    cwd:root,encoding:'utf8',timeout:10000,
    env:{...process.env,MOJ1_V2_DEPLOY_CONFIRM:'',TRON_PRIVATE_KEY:'',
      MOJ1_V2_DEPLOY_JOURNAL_PATH:'',...overrides}
  });
}
test('V2 Shasta escrow deployment refuses Mainnet and missing explicit test-only opt-in',()=>{
  const p=attempt({MOJ1_V2_DEPLOY_CONFIRM:'MAINNET'});
  assert.notEqual(p.status,0);
  assert.match(p.stderr,/SHASTA_V2_ESCROW_ONLY/);
});
test('V2 Shasta deployment refuses all missing test signing material before network',()=>{
  const p=attempt({MOJ1_V2_DEPLOY_CONFIRM:'SHASTA_V2_ESCROW_ONLY'});
  assert.notEqual(p.status,0);
  assert.match(p.stderr,/Dedicated Shasta pilot key required/);
});
test('V2 Shasta deployment refuses missing private persistent journal before network',()=>{
  const p=attempt({MOJ1_V2_DEPLOY_CONFIRM:'SHASTA_V2_ESCROW_ONLY',
    TRON_PRIVATE_KEY:'1'.repeat(64)});
  assert.notEqual(p.status,0);
  assert.match(p.stderr,/Persistent absolute V2 deployment journal required/);
});
test('V2 dedicated journal is idempotent, crash-safe and bound to compiled artifact',async t=>{
  const dir=await mkdtemp(join(tmpdir(),'moj1-v2-shasta-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const path=join(dir,'journal.json');
  const context={network:'Shasta',governance:'41'+'f'.repeat(40),
    artifacts:{MojCoinGuarded:'sha256-v2-compiled-artifact'}};
  const record={txID:'a'.repeat(64),rawDataSha256:'b'.repeat(64),
    expectedAddress:'41'+'c'.repeat(40)};
  const j=await openDeploymentJournal(path,context);
  await j.markBroadcastUncertain('MojCoinGuarded',record);
  await assert.rejects(j.markBroadcastUncertain('MojCoinGuarded',record),/Cannot repeat/);
  assert.equal(j.pending('MojCoinGuarded').txID,record.txID);
  assert.doesNotMatch(await readFile(path,'utf8'),/privateKey|TRON_PRIVATE_KEY|signedTransaction/);
  await j.close();
  const reopened=await openDeploymentJournal(path,context);
  assert.throws(()=>reopened.verifiedAddress('MojCoinGuarded'),/DO NOT REDEPLOY/);
  await reopened.markVerified('MojCoinGuarded',record.expectedAddress,record.txID);
  await reopened.close();
  await assert.rejects(openDeploymentJournal(path,{...context,
    artifacts:{MojCoinGuarded:'changed-bytecode'}}),/identity mismatch/);
});
test('journal still rejects unsupported Mainnet and unlisted Shasta token manifests',async()=>{
  await assert.rejects(openDeploymentJournal('/tmp/unused-v2-test.json',{
    network:'Mainnet',governance:'x',artifacts:{MojCoinGuarded:'x'}}),/Invalid Shasta/);
  await assert.rejects(openDeploymentJournal('/tmp/unused-v2-test.json',{
    network:'Shasta',governance:'x',artifacts:{MojCoinGuarded:'x',MojCoin:'x'}}),/Invalid Shasta/);
});
