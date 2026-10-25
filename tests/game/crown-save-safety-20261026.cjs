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
 {score:3,wave:2,mode:'endless',when:'2026-02-31'},
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
const forged=vm.runInNewContext("const STORAGE='mpw-crown-v10-save';const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));"+loader+'loadSave()',{
 localStorage:{getItem(){return JSON.stringify({best:'99999',credits:'1000000',hangar:{cannons:'5'},campaign:{unlockedSector:'10'},stats:{kills:true}})}},JSON,Number,Math,Set
});
assert.equal(forged.best,0,'string scores must not be promoted to valid records');
assert.equal(forged.credits,0,'string credits must not become earned currency');
assert.equal(forged.hangar.cannons,0,'string upgrades must not become purchased upgrades');
assert.equal(forged.campaign.unlockedSector,1,'string campaign progress must not unlock sectors');
assert.equal(forged.stats.kills,0,'boolean statistics must not be counted as kills');
const init=js.slice(js.indexOf('let save=loadSave();'),js.indexOf('// Each silhouette'));
const legacy=vm.runInNewContext("const STORAGE='mpw-crown-v10-save';const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));"+loader+init+'save.best',{localStorage:{getItem(key){return key==='mpw-crown-defender-best-v1'?'Infinity':'{\"best\":250}'},setItem(){}},JSON,Number,Math,Set,Date});
assert.equal(legacy,250,'nonfinite legacy scores must not poison the current save');
assert.equal(vm.runInNewContext(loader+'validRecordDate(\"2026-02-28\")',{Date,Number,Math,JSON,Set}), '2026-02-28');
console.log('CROWN_SAVE_SAFETY_PASS: scoreboard validation, date safety, achievements and backward-compatible progress');
