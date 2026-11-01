import test from 'node:test';
import assert from 'node:assert/strict';
import {makeCampaignBackup,readCampaignBackup,MAX_CAMPAIGN_BACKUP_BYTES} from './campaign-backup.mjs';

const state={hero:0,mission:0,lives:100,x:2.5,y:7.5,angle:0,maxHp:100,hp:100,ammo:8,magazine:8,rockets:12,drones:3,score:0,points:0,kills:0,missionKills:0,enemies:[],hostile:[],missiles:[],pickups:[],objective:{done:0,hold:0,bossDefeated:false},endless:false,victory:false,gameOver:false};
const original=JSON.stringify(state);

test('valid campaign exports and round-trips without losing progress',()=>{
 const backup=makeCampaignBackup(original);
 assert.ok(backup);
 assert.deepEqual(JSON.parse(readCampaignBackup(backup)),state);
});
test('malformed and oversized exports are refused',()=>{
 assert.equal(makeCampaignBackup('{oops'),null);
 assert.equal(makeCampaignBackup('x'.repeat(MAX_CAMPAIGN_BACKUP_BYTES+1)),null);
});
test('imports reject forged, missing, wrong-version and invalid campaign data',()=>{
 const good=JSON.parse(makeCampaignBackup(original));
 for(const bad of [null,{}, {...good,format:'other'}, {...good,version:2},{...good,campaign:{...state,hero:999}}]){
  assert.equal(readCampaignBackup(JSON.stringify(bad)),null);
 }
});
test('oversized import is refused before parse',()=>{
 assert.equal(readCampaignBackup(' '.repeat(MAX_CAMPAIGN_BACKUP_BYTES+1)),null);
});
test('survival and victory states are never portable as campaign progress',()=>{
 for(const key of ['endless','victory','gameOver']){
  assert.equal(makeCampaignBackup(JSON.stringify({...state,[key]:true})),null);
 }
});
