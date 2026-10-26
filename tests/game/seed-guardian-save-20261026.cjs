'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('content/zomorod-seed-guardian-20261023/index.html','utf8');
const script=html.split('<script>')[1]?.split('</script>')[0];
assert.ok(script,'Seed Guardian must have a playable script');
new vm.Script(script,'seed-guardian.js');
const start=script.indexOf('let saved={stage:1,best:0,clears:0};');
const end=script.indexOf('let stage=saved.stage',start);
assert.ok(start>=0&&end>start,'Seed Guardian save parser must exist');
const parser=script.slice(start,end);
function load(value,throws=false){
 return vm.runInNewContext("const storeKey='zm.seed.guardian.v1';"+parser+'saved',{
  localStorage:{getItem(){if(throws)throw Error('storage denied');return JSON.stringify(value)}},
  JSON,Number,Math
 });
}
function plain(v){return JSON.parse(JSON.stringify(v))}
assert.deepEqual(plain(load({stage:45,best:1830,clears:44})),{stage:45,best:1830,clears:44},
 'legitimate completed levels and scores must survive');
assert.deepEqual(plain(load({stage:121,best:'999999',clears:'120'})),{stage:120,best:0,clears:0},
 'forged string scores and clear counts must be rejected');
assert.deepEqual(plain(load({stage:1,best:1e30,clears:1000000})),{stage:1,best:0,clears:0},
 'unbounded score and clear counts must be rejected');
assert.deepEqual(plain(load({stage:1,best:-4,clears:-3})),{stage:1,best:0,clears:0},
 'negative score and clear counts must be rejected');
assert.deepEqual(plain(load(null)),{stage:1,best:0,clears:0},
 'null saved data must fall back safely');
assert.deepEqual(plain(load(null,true)),{stage:1,best:0,clears:0},
 'blocked browser storage must not crash the game');
console.log('SEED_GUARDIAN_SAVE_INTEGRITY=PASS: strict bounded records and private mode');

\n// Runtime regression: stage 120 must be a genuine ending, not an endless replay of stage 120.
const finishStart=script.indexOf('function finish(success){');
const finishEnd=script.indexOf('function nextStage(){',finishStart);
assert.ok(finishStart>=0&&finishEnd>finishStart,'finish transition must be available');
const finishCode=script.slice(finishStart,finishEnd);
function finishAt(level,win){
 const nodes={
  dialogTitle:{textContent:''},dialogText:{textContent:''},next:{textContent:''},
  overlay:{classList:{add(name){assert.equal(name,'show')}}}
 };
 const state={stage:level,score:1230,best:100,saved:{clears:level-1},playing:true,mode:'playing',
  $:id=>nodes[id],Math,persist(){this.persisted=true},tone(){},paintHud(){}};
 // Explicit closure avoids relying on a VM-global 'this' binding.
 state.persist=()=>{state.persisted=true};
 vm.runInNewContext(finishCode+';finish('+String(win)+');',state);
 return {state,nodes};
}
const finale=finishAt(120,true);
assert.equal(finale.state.stage,120,'final victory must not overflow the 120-stage campaign');
assert.equal(finale.state.mode,'complete','stage 120 victory must enter a distinct completed state');
assert.equal(finale.state.saved.clears,120,'all 120 clears must be recorded');
assert.equal(finale.state.persisted,true,'final victory must persist completion');
assert.match(finale.nodes.dialogTitle.textContent,/۱۲۰/,'final dialog must recognize the completed campaign');
assert.match(finale.nodes.next.textContent,/مرحله ۱/,'final dialog must offer an explicit replay');
const ordinary=finishAt(119,true);
assert.equal(ordinary.state.stage,120,'winning stage 119 must unlock stage 120');
assert.equal(ordinary.state.mode,'levelup','ordinary victory must not trigger the final dialog');
const defeat=finishAt(120,false);
assert.equal(defeat.state.stage,120,'defeat must not skip or complete stage 120');
assert.equal(defeat.state.mode,'lost','defeat must remain a loss');

const replayStart=script.indexOf('function nextStage(){');
const replayEnd=script.indexOf('function tapLane(',replayStart);
assert.ok(replayStart>=0&&replayEnd>replayStart,'replay transition must be available');
const replayNodes={overlay:{classList:{remove(name){assert.equal(name,'show')}}}};
const replay={stage:120,mode:'complete',playing:false,
 $:id=>replayNodes[id],persist(){this.didPersist=true},reset(){this.didReset=true},paintHud(){}};
replay.persist=()=>{replay.didPersist=true};
replay.reset=()=>{replay.didReset=true};
vm.runInNewContext(script.slice(replayStart,replayEnd)+';nextStage();',replay);
assert.equal(replay.stage,1,'completed campaign replay must begin at stage 1');
assert.equal(replay.didPersist,true,'replay start must save the new stage');
assert.equal(replay.didReset,true,'replay must reset gameplay');
assert.equal(replay.mode,'playing','replay must resume normal gameplay');

const tapStart=script.indexOf('function tapLane(');
const tapEnd=script.indexOf('function spritz(',tapStart);
assert.ok(tapStart>=0&&tapEnd>tapStart,'lane control must be available');
for(const ended of ['complete','levelup','lost']){
 const state={mode:ended,selected:1,mutation:0,gates:[3,3,3],seeds:[],H:820,Math,Number};
 vm.runInNewContext(script.slice(tapStart,tapEnd)+';tapLane(0,true);',state);
 assert.equal(state.selected,1,'ended '+ended+' game must ignore lane selection');
 assert.equal(state.mutation,0,'ended '+ended+' game must ignore gate mutation');
}
assert.ok(script.includes('mode===\'complete\')nextStage()'),'keyboard completion must allow replay');
assert.ok(script.includes("e.target.closest('button,a,select,textarea,[contenteditable=\"true\"]')"),
 'keyboard shortcuts must not hijack focused native button activation');
console.log('SEED_GUARDIAN_FINALE=PASS: stage 120 victory, replay, keyboard, and terminal input safety');
