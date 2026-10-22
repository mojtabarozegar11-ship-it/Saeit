import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {renderMoj1StagingPage} from '../staging/site/render-preview.mjs';
import {makeSyntheticGuestOrder,previewSyntheticCheckout} from '../staging/mojplaywin-readonly-bridge.mjs';

const manifest = JSON.parse(readFileSync(new URL('../shasta-deployment.json',import.meta.url),'utf8'));
const hash = 'b'.repeat(64);
const contracts = ['MojPilotGovernance','MojCoin','MojGenesisDistributor','MojAssets'];
const proof = {
  mode:'MOJ1_SHASTA_PUBLIC_READ_ONLY',status:'PASS',
  token:manifest.token_contract,escrow:manifest.genesis_escrow,
  governance:manifest.governance_contract,nft:manifest.nft_contract,
  totalWholeTokens:manifest.total_supply_whole,escrowFullyFunded:true,
  distributed:false,mainnet:false,privateKeyUsed:false,paymentsModified:false,
  bytecodeEvidence:contracts.map((contract)=>({
    contract,runtimeSha256:hash,
    creationSha256:contract==='MojGenesisDistributor'?null:hash,
    method:contract==='MojGenesisDistributor'?
      'ATTESTED_PARENT_PLUS_RUNTIME_MATCH_WITH_CHECKED_IMMUTABLES':
      'CREATION_AND_EXACT_RUNTIME_MATCH'
  }))
};
const safe = previewSyntheticCheckout({
  manifest,chainProof:proof,order:makeSyntheticGuestOrder()
});

test('accessible, responsive testnet-only informational page',()=>{
  const page=renderMoj1StagingPage({manifest,receipt:safe});
  assert.match(page, /<!doctype html>/);
  assert.match(page, /<html lang="en">/);
  assert.match(page, /name="viewport"/);
  assert.match(page, /name="robots" content="noindex,nofollow,noarchive"/);
  assert.match(page, /Content-Security-Policy/);
  assert.match(page, /data-testnet-only="true"/);
  assert.match(page, /data-synthetic-only="true"/);
  assert.ok(page.includes(manifest.token_contract));
  assert.ok(page.includes('100,000,000,000 MOJ1'));
  assert.ok(page.includes('No real value'));
  assert.ok(page.includes('Not started'));
});

test('no purchase UI, scripts, forms, live wallets or network resources',()=>{
  const page=renderMoj1StagingPage({manifest,receipt:safe});
  assert.doesNotMatch(page, /<script\b|<form\b|<input\b|<button\b|<iframe\b/i);
  assert.doesNotMatch(page, /<img\b|<link\b|<video\b|<audio\b/i);
  assert.doesNotMatch(page, /https?:\/\//i);
  assert.doesNotMatch(page, /transactionHash|privateKey|checkout\/confirm|download-url/i);
  assert.match(page,/Public sale<\/div><div class="v amber">Disabled/);
});

test('unsafe release and forged evidence block preview generation',()=>{
  for(const [key,value] of [
    ['paymentEnabled',true],['deliveryEnabled',true],
    ['mainnetEnabled',true],['orderWriteEnabled',true],
    ['keysUsed',true],['realMojPlayWinGatewayChanged',true],
    ['tokenContract',manifest.nft_contract],['orderKind','REAL'],
    ['orderState','paid'],['distributed',true],
    ['sourceOfChainProof','SELF_REPORT']
  ]){
    assert.throws(()=>renderMoj1StagingPage({manifest,receipt:{...safe,[key]:value}}),
      /MOJ1_PREVIEW_/, key);
  }
  assert.throws(()=>renderMoj1StagingPage({
    manifest:{...manifest,real_payment_enabled:true},receipt:safe
  }),/MOJ1_STAGING_MANIFEST/);
});
