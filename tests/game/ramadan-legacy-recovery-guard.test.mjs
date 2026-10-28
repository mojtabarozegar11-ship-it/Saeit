import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseCampaignSave, restoreRecoveryPickups} from '../../games/ramadan-war/save-validation.mjs';

const sites=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
const pickup=i=>({x:sites[i][0],y:sites[i][1],type:'mission-intel',spotIndex:i,life:3600});
const state=(done,ids=[],collected)=>({mission:2,
  objective:{done,hold:0,bossDefeated:false,...(collected?{collectedSites:collected}:{})},
  pickups:ids.map(pickup),score:300*done,points:done});

test('ambiguous legacy save never fabricates an unearned recovery pickup',()=>{
  const s=state(1,[]),before=structuredClone(s);
  assert.equal(restoreRecoveryPickups(s,sites),0);
  assert.deepEqual(s,before);
});
test('complete remaining legacy pickups infer an exact provenance ledger without points',()=>{
  const s=state(1,[1,2]);
  assert.equal(restoreRecoveryPickups(s,sites),0);
  assert.deepEqual(s.objective.collectedSites,[0]);
  assert.equal(s.points,1);
});
test('invalid legacy recovery state is transactional',()=>{
  const s=state(1,[0,1,2]),before=structuredClone(s);
  assert.equal(restoreRecoveryPickups(s,sites),0);
  assert.deepEqual(s,before);
});
test('known ledger restores only missing uncollected pickup once',()=>{
  const s=state(1,[2],[0]);
  assert.equal(restoreRecoveryPickups(s,sites),1);
  assert.deepEqual(s.pickups.map(p=>p.spotIndex),[2,1]);
  assert.equal(s.points,1);
  assert.equal(restoreRecoveryPickups(s,sites),0);
});
test('malformed and oversized browser storage is rejected before JSON parsing',()=>{
  assert.equal(parseCampaignSave('x'.repeat(512*1024+1)),null);
  assert.equal(parseCampaignSave('{'),null);
  assert.equal(parseCampaignSave(''),null);
  assert.deepEqual(parseCampaignSave('{"mission":2}'),{mission:2});
});
test('continue never silently overwrites an invalid save with a fresh campaign',()=>{
  const source=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
  assert.match(source,/const s=parseCampaignSave\(storageRead\(saveKey\)\)/);
  assert.match(source,/if\(!restore\(\)\)\{toast\([^;]+;return\}/);
  assert.doesNotMatch(source,/if\(!restore\(\)\)newWorld\(false\)/);
});
