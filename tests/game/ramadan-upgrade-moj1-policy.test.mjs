import test from 'node:test';
import assert from 'node:assert/strict';
import {applyEarnedUpgrade,canApplyEarnedUpgrade,UPGRADE_LIMITS} from '../../games/ramadan-war/upgrade-policy.mjs';
import {MOJ1_COMMERCE,MOJ1_CATALOG,checkMoj1Purchase} from '../../games/ramadan-war/moj1-commerce-policy.mjs';
const world=(overrides={})=>({points:5,power:0,armor:0,rockets:12,drones:3,maxHp:112,hp:72,...overrides});
test('power upgrade spends one earned point and grants exactly one level',()=>{
 const s=world();assert.equal(applyEarnedUpgrade(s,0).ok,true);assert.equal(s.points,4);assert.equal(s.power,1);
});
test('armor upgrade heals but never exceeds save-valid maximum health',()=>{
 const s=world({maxHp:192,hp:180});assert.equal(applyEarnedUpgrade(s,1).ok,true);
 assert.equal(s.maxHp,200);assert.equal(s.hp,200);assert.equal(s.armor,1);assert.equal(s.points,4);
});
test('at full armor health cap, no earned points are consumed',()=>{
 const s=world({maxHp:200,hp:190,armor:4});const before={...s};
 assert.equal(applyEarnedUpgrade(s,1).reason,'cap');assert.deepEqual(s,before);
});
test('rocket cap does not charge player for an ineffective purchase',()=>{
 const s=world({rockets:24});const before={...s};
 assert.equal(applyEarnedUpgrade(s,2).reason,'cap');assert.deepEqual(s,before);
});
test('drone cap does not charge player for an ineffective purchase',()=>{
 const s=world({drones:7});const before={...s};
 assert.equal(applyEarnedUpgrade(s,3).reason,'cap');assert.deepEqual(s,before);
});
test('power cap prevents runaway damage and wasted points',()=>{
 const s=world({power:UPGRADE_LIMITS.power});const before={...s};
 assert.equal(applyEarnedUpgrade(s,0).reason,'cap');assert.deepEqual(s,before);
});
test('valid rocket and drone upgrades cap quantities and debit one point',()=>{
 const s=world({rockets:22,drones:6});
 assert.equal(applyEarnedUpgrade(s,2).ok,true);assert.equal(s.rockets,24);assert.equal(s.points,4);
 assert.equal(applyEarnedUpgrade(s,3).ok,true);assert.equal(s.drones,7);assert.equal(s.points,3);
});
test('zero points, unknown upgrade kind, and malformed saves never mutate gameplay',()=>{
 for(const [s,k] of [[world({points:0}),0],[world(),-1],[world(),4],[world({points:Infinity}),0],[world({hp:NaN}),1]]){
  const before={...s};assert.equal(applyEarnedUpgrade(s,k).ok,false);assert.deepEqual(s,before);
 }
});
test('the button gate uses the same cap rules as the mutation',()=>{
 const s=world({rockets:24});assert.equal(canApplyEarnedUpgrade(s,2).ok,false);
 assert.equal(canApplyEarnedUpgrade(s,3).ok,true);
});
test('MOJ1 token identity is not guessed and checkout is fail-closed',()=>{
 assert.equal(MOJ1_COMMERCE.asset,'MOJ1');assert.equal(MOJ1_COMMERCE.network,'TRON');
 assert.equal(MOJ1_COMMERCE.contractAddress,null);assert.equal(MOJ1_COMMERCE.decimals,null);
 assert.equal(MOJ1_COMMERCE.checkoutEnabled,false);assert.equal(MOJ1_COMMERCE.ownerApproved,false);
});
test('all catalog entries have no payable price or enabled checkout',()=>{
 assert.ok(MOJ1_CATALOG.length>0);
 for(const item of MOJ1_CATALOG){assert.equal(item.priceAtomic,null);assert.equal(item.enabled,false)}
});
test('web, Android and iOS cannot create a live MOJ1 purchase',()=>{
 const sku=MOJ1_CATALOG[0].sku;
 for(const platform of ['web','android','ios'])assert.equal(checkMoj1Purchase({platform,sku}).allowed,false);
 assert.equal(checkMoj1Purchase({platform:'web',sku:'fake'}).code,'UNKNOWN_SKU');
 assert.equal(checkMoj1Purchase({platform:'desktop',sku}).code,'UNSUPPORTED_PLATFORM');
});

test('save validator accepts capped legitimate upgrade but rejects poisoned power/armor', async()=>{
 const {validateCampaignSave}=await import('../../games/ramadan-war/save-validation.mjs');
 const s={hero:4,mission:1,lives:99,x:2.5,y:7.5,angle:0,hp:200,maxHp:200,ammo:8,magazine:8,
 rockets:24,drones:7,score:100,points:0,kills:1,missionKills:0,enemies:[],power:12,armor:5};
 assert.equal(validateCampaignSave(s),true);
 for(const patch of [{power:Infinity},{power:'12'},{armor:-1},{armor:NaN},{armor:1000}]){
  assert.equal(validateCampaignSave({...s,...patch}),false,JSON.stringify(patch));
 }
});
test('web runtime uses the earned-upgrade policy and ships its dependencies for rollback', async()=>{
 const {readFileSync}=await import('node:fs');
 const game=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
 const html=readFileSync(new URL('../../games/ramadan-war/index.html',import.meta.url),'utf8');
 const deploy=readFileSync(new URL('../../games/ramadan-war/deploy.py',import.meta.url),'utf8');
 assert.match(game,/import \{canApplyEarnedUpgrade,applyEarnedUpgrade\} from '\.\/upgrade-policy\.mjs'/);
 assert.match(game,/applyEarnedUpgrade\(world,k\)/);
 assert.match(game,/world\.power=Math\.min\(12,world\.power\?\?0\)/);
 assert.match(html,/id="moj1Status"/);
 assert.match(deploy,/'upgrade-policy\.mjs','moj1-commerce-policy\.mjs'/);
 assert.match(deploy,/checkoutEnabled:false/);
});
