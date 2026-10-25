'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync('games/crown-defender/index.html','utf8');
const js=html.split('<script>')[1].split('</script>')[0];
const from=js.indexOf('const DEFAULT='),to=js.indexOf('let save=loadSave();',from);
assert.ok(from>=0&&to>from,'Crown save loader must remain testable');
const loader=js.slice(from,to);
const records=[
 {score:1234,wave:7,mode:'campaign',when:'2026-10-26',win:true},
 {score:-5,wave:2,mode:'campaign'},
 {score:Infinity,wave:2,mode:'campaign'},
 {score:99,wave:-1,mode:'campaign'},
 {score:99,wave:1,mode:'javascript:alert(1)'},
 {score:3,wave:2,mode:'endless',when:'not-a-date'},
 {score:2,wave:2,mode:'bossrush',when:'2026-10-26'}
];
const storage={getItem(){return JSON.stringify({
 best:200,credits:30,
 achievements:['ACE','ACE','BAD ENTRY',42,'BOSS_HUNTER'],
 history:records,
 campaign:{unlockedSector:2},
 stats:{kills:2}
})}};
const run=vm.runInNewContext("const STORAGE='mpw-crown-v10-save';const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));"+loader+"loadSave()",{localStorage:storage,JSON,Number,Math,Set});
assert.equal(run.history.length,3,'invalid scoreboard entries must be discarded');
assert.equal(run.history[0].score,1234);
assert.equal(run.history[1].when,'','invalid dates must be dropped');
assert.equal(run.history[2].when,'2026-10-26');
assert.equal(run.achievements.length,2,'duplicate and malformed achievements must be removed');
assert.equal(run.credits,30,'legitimate local credit history must survive');
assert.equal(run.campaign.unlockedSector,2,'valid campaign progress must survive');
console.log('CROWN_SAVE_SAFETY_PASS: scoreboard validation, date safety, achievements and backward-compatible progress');
