import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {makeCampaignBackup,readCampaignBackup,MAX_CAMPAIGN_BACKUP_BYTES} from '../campaign-backup.mjs';
const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
test('BOM-prefixed valid JSON backup roundtrips while malformed/double-BOM fails',()=>{
 const raw=JSON.stringify({hero:0,mission:0,lives:100,x:2.5,y:7.5,angle:0,maxHp:100,hp:100,ammo:8,magazine:8,rockets:12,drones:3,score:0,points:0,kills:0,missionKills:0,enemies:[],objective:{done:0,hold:0,bossDefeated:false}});
 const backup=makeCampaignBackup(raw);assert.ok(backup);
 assert.deepEqual(JSON.parse(readCampaignBackup('\uFEFF'+backup)),JSON.parse(raw));
 assert.equal(readCampaignBackup('\uFEFF\uFEFF'+backup),null);
 assert.equal(readCampaignBackup('\uFEFF'.repeat(MAX_CAMPAIGN_BACKUP_BYTES)),null);
});
test('clipboard fallback does not show private backup after screen change or hidden tab',()=>{
 assert.match(game,/const originScreen=screen;/);
 assert.match(game,/if\(screen!==originScreen\|\|document\.hidden\)return;/);
});
test('async file reads reject stale selections and changed screens',()=>{
 assert.match(game,/let backupFileReadToken=0/);
 assert.match(game,/token=\+\+backupFileReadToken,originScreen=screen/);
 assert.match(game,/if\(token!==backupFileReadToken\|\|screen!==originScreen\)return;/);
});
test('oversized files are refused before file.text is called',()=>{
 assert.match(game,/if\(file\.size>MAX_CAMPAIGN_BACKUP_BYTES\)/);
 assert.match(game,/readCampaignBackup\(await file\.text\(\)\)/);
});
