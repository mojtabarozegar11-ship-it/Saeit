import test from 'node:test';
import assert from 'node:assert/strict';
import {validateCampaignSave, restoreRecoveryPickups} from '../../games/ramadan-war/save-validation.mjs';

const SITES=[[4.5,2.5],[12.5,4.5],[8.5,12.5]];
const pickup=(spotIndex)=>({x:SITES[spotIndex][0],y:SITES[spotIndex][1],type:'mission-intel',spotIndex,life:3600});
const fresh=()=>({hero:0,mission:2,lives:100,x:2.5,y:7.5,angle:0,maxHp:100,hp:100,
  ammo:8,magazine:8,rockets:12,drones:3,score:0,points:0,kills:0,missionKills:0,
  enemies:[],pickups:[pickup(0),pickup(1),pickup(2)],
  objective:{done:0,hold:0,bossDefeated:false,collectedSites:[]}});

test('canonical recovery items survive strict provenance validation',()=>{
  assert.equal(validateCampaignSave(fresh()),true);
  const s=fresh();s.objective={done:1,hold:0,bossDefeated:false,collectedSites:[0]};s.pickups=[pickup(1),pickup(2)];
  assert.equal(validateCampaignSave(s),true);
});
test('a moved recovery item cannot be teleported to player via local save',()=>{
  const s=fresh();s.pickups[0]={...pickup(0),x:s.x,y:s.y};
  assert.equal(validateCampaignSave(s),false);
});
test('mission intel with no objective is rejected instead of creating duplicate objectives',()=>{
  const s=fresh();delete s.objective;
  assert.equal(validateCampaignSave(s),false);
});
test('a boss cannot be duplicated, forged in an earlier mission or mislabeled',()=>{
  const enemy={x:8.5,y:7.5,type:3,hp:410,boss:true};
  const s={...fresh(),mission:5,pickups:[],objective:{done:0,hold:0,bossDefeated:false},enemies:[enemy]};
  assert.equal(validateCampaignSave(s),true);
  assert.equal(validateCampaignSave({...s,enemies:[enemy,enemy]}),false);
  assert.equal(validateCampaignSave({...s,mission:4}),false);
  assert.equal(validateCampaignSave({...s,enemies:[{...enemy,type:0}]}),false);
  assert.equal(validateCampaignSave({...s,objective:{...s.objective,bossDefeated:true}}),false);
});
test('recovery restore rejects moved items without changing rewards or pickup state',()=>{
  const s=fresh();s.pickups=[{...pickup(0),x:2.5}];
  const before=structuredClone(s);
  assert.equal(restoreRecoveryPickups(s,SITES),0);
  assert.deepEqual(s,before);
});

test('invalid recovery-site coordinates never create synthetic rewards',()=>{
  const s=fresh();s.pickups=[pickup(0)];const before=structuredClone(s);
  assert.equal(restoreRecoveryPickups(s,[[4.5,2.5],[NaN,4.5],[8.5,12.5]]),0);
  assert.deepEqual(s,before);
});
