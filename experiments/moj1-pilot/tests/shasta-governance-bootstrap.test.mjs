// Readiness / failure-boundary checks for Shasta governance bootstrap.
// Offline only: no RPC calls, no deployer private key, no network broadcast.
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';

const root=resolve(dirname(fileURLToPath(import.meta.url)), '..');
const governor=resolve(root,'scripts/deploy-governance-shasta.mjs');
const token=resolve(root,'scripts/deploy-shasta.mjs');

test('Shasta governance bootstrap and token deployer have valid JavaScript syntax',()=>{
  for(const script of [governor,token]){
    const run=spawnSync(process.execPath,['--check',script],{encoding:'utf8',timeout:10000});
    assert.equal(run.status,0,run.stderr);
  }
});

test('governance Shasta deployer fails closed without exact test-only authorization',()=>{
  const result=spawnSync(process.execPath,[governor],{
    cwd:root,encoding:'utf8',timeout:10000,
    env:{...process.env, MOJ1_GOV_DEPLOY_CONFIRM:'',TRON_PRIVATE_KEY:''}
  });
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/SHASTA_ONLY_TEST_GOVERNANCE/);
  assert.doesNotMatch(result.stdout,/TEST_GOVERNANCE_ONCHAIN_VERIFIED/);
});

test('governance Shasta deployer refuses missing signing key before RPC',()=>{
  const result=spawnSync(process.execPath,[governor],{
    cwd:root,encoding:'utf8',timeout:10000,
    env:{...process.env, MOJ1_GOV_DEPLOY_CONFIRM:'SHASTA_ONLY_TEST_GOVERNANCE',TRON_PRIVATE_KEY:''}
  });
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/Dedicated Shasta-only deployer private key/);
});

test('Shasta governor deployment is single-broadcast, journaled and never Mainnet',()=>{
  const src=readFileSync(governor,'utf8');
  const tokenSrc=readFileSync(token,'utf8');
  assert.match(src,/https:\/\/api\.shasta\.trongrid\.io/);
  assert.doesNotMatch(src,/https:\/\/api\.trongrid\.io/);
  assert.match(src,/journal\.markBroadcastUncertain/);
  assert.match(src,/reconcileDeployment/);
  assert.match(src,/SHASTA_TEST_TRX_REQUIRED/);
  assert.match(src,/MOJ1_SHASTA_GOV_OWNERS/);
  assert.equal((src.match(/sendRawTransaction\(/g)||[]).length,1);
  assert.match(tokenSrc,/MOJ1_SHASTA_GOV_OWNERS/);
  assert.match(tokenSrc,/onchainGovernor\.owners\(i\)/);
  assert.match(tokenSrc,/Duplicate Shasta governance owners/);
});
