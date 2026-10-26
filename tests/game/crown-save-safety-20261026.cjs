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

// Exercise the real menu transition: abandoning a premium trial must restore earned-flight rewards.
const menuCode=js.slice(js.indexOf('function mainMenu(){'),js.indexOf('function pause(){'));
assert.ok(menuCode.includes('if(trialJet){trialJet=false;'), 'practice reset must exist at menu boundary');
function menuTransition(practice){
 const nodes=new Map();
 const get=id=>{if(!nodes.has(id))nodes.set(id,{value:'1',hidden:false,textContent:'',append(){}});return nodes.get(id)};
 const result=vm.runInNewContext(
  "let trialJet="+practice+",activeJet='spectre',selectedJet='falcon',state='playing',overlayState='none';"+
  "const save={campaign:{unlockedSector:2}};"+menuCode+
  "mainMenu();({trialJet,activeJet,state,overlayState})",
  {$:get,document:{createElement(){return {}}},sectors:Array.from({length:10},(_,i)=>({name:'Sector '+i})),
   ownedJet:id=>id==='falcon',getMission:()=>({name:'Safe mission',text:'Briefing'}),hidePanes(){},showOverlay(){}}
 );
 return result;
}
const abandoned=menuTransition(true);
assert.equal(abandoned.trialJet,false,'abandoned trial must not suppress normal mission rewards');
assert.equal(abandoned.activeJet,'falcon','abandoned premium preview must not remain active');
assert.equal(abandoned.state,'menu');
const normal=menuTransition(false);
assert.equal(normal.trialJet,false,'normal menu must remain normal');

// Flight controls must never activate from menu overlays or consume actions while paused.
const keyStart=js.indexOf("document.addEventListener('keydown',e=>{");
const keyEnd=js.indexOf("document.addEventListener('keyup',",keyStart);
assert.ok(keyStart>=0&&keyEnd>keyStart,'flight keyboard handler must be present');
const keyCode=js.slice(keyStart,keyEnd);
const keyboard=vm.runInNewContext(
 "let state='menu',overlayState='none',keydown;const keys=new Set();"+
 "const canvas={};const document={body:{},addEventListener(name,fn){if(name==='keydown')keydown=fn}};"+
 "class HTMLElement{};const counts={dash:0,emp:0,prism:0,chrono:0,pause:0};"+
 "function dash(){counts.dash++}function useEMP(){counts.emp++}"+
 "function usePrism(){counts.prism++}function useChrono(){counts.chrono++}"+
 "function pause(){counts.pause++}"+
 keyCode+"({keys,counts,dispatch:e=>keydown(e),setState:s=>state=s,setOverlay:s=>overlayState=s,body:document.body})"
);
const flightEvent=(code,repeat=false)=>({code,repeat,target:keyboard.body,preventDefault(){this.prevented=true}});
keyboard.dispatch(flightEvent('KeyE'));
keyboard.dispatch(flightEvent('ShiftLeft'));
assert.equal(keyboard.counts.emp,0,'menu must not discharge EMP');
assert.equal(keyboard.counts.dash,0,'menu must not activate dash');
assert.equal(keyboard.keys.size,0,'menu shortcuts must not queue held flight controls');
const menuArrow=flightEvent('ArrowDown');keyboard.dispatch(menuArrow);
assert.equal(menuArrow.prevented,undefined,'menu navigation must not be blocked by flight controls');
keyboard.setState('playing');
const flightArrow=flightEvent('ArrowDown');keyboard.dispatch(flightArrow);
assert.equal(flightArrow.prevented,true,'playing must still suppress page scrolling');
keyboard.dispatch(flightEvent('KeyE'));keyboard.dispatch(flightEvent('KeyE',true));
assert.equal(keyboard.counts.emp,1,'active EMP must work once per key press');
keyboard.setState('paused');keyboard.setOverlay('pause');
keyboard.dispatch(flightEvent('KeyE'));
assert.equal(keyboard.counts.emp,1,'paused flight must not consume EMP');
keyboard.dispatch(flightEvent('Escape'));
assert.equal(keyboard.counts.pause,1,'Escape must still resume from pause overlay');

console.log('CROWN_SAVE_SAFETY_PASS: scoreboard validation, date safety, achievements and backward-compatible progress');
