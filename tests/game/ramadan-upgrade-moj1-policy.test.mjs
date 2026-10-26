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
