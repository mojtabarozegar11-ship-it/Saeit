import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {readCampaignBackup,makeCampaignBackup} from '../campaign-backup.mjs';
const js=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
test('home and pause offer both file and pasted-code recovery',()=>{
 for(const id of ['pasteSave','pastePauseSave','applyBackupCode','backupCodeText','closeBackupCode'])assert.match(html,new RegExp('id="'+id+'"'));
 assert.match(js,/function openBackupCode\(mode,raw=''/);
 assert.match(js,/function applyImportedCampaign\(imported\)/);
 assert.match(js,/applyImportedCampaign\(imported\);/);
});
test('manual code is cleared and never transmitted or persisted automatically',()=>{
 assert.match(js,/function closeBackupCode\(\)\{\s*\$\('#backupCodeText'\)\.value='';/);
 assert.match(js,/if\(copied\)toast\(/);
 assert.match(js,/else openBackupCode\('export',backup\)/);
 assert.doesNotMatch(js,/fetch\([^)]*backupCodeText/);
});
test('valid backup roundtrip and invalid paste refuse import',()=>{
 const raw=JSON.stringify({hero:0,mission:0,lives:100,x:2.5,y:7.5,angle:0,maxHp:100,hp:100,ammo:8,magazine:8,rockets:12,drones:3,score:0,points:0,kills:0,missionKills:0,enemies:[],objective:{done:0,hold:0,bossDefeated:false}});
 const backup=makeCampaignBackup(raw);
 assert.ok(backup,'fixture must validate');
 assert.deepEqual(JSON.parse(readCampaignBackup(backup)),JSON.parse(raw));
 for(const code of ['{bad}',JSON.stringify({format:'ramadan-war-campaign-v1',version:2,campaign:JSON.parse(raw)}),'x'.repeat(524289)])assert.equal(readCampaignBackup(code),null);
});
