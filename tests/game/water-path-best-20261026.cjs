'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('content/zomorod-hourly-20261023/water-path-game/index.html','utf8');
const script=html.split('<script>')[1]?.split('</script>')[0];
assert.ok(script,'Water Path playable script must exist');
new vm.Script(script,'water-path.js');
const start=script.indexOf('function bestForStage(');
const end=script.indexOf('function rnd(',start);
assert.ok(start>=0&&end>start,'validated per-stage record helper must exist');
const fn=script.slice(start,end);
const records=vm.runInNewContext(
 'const bests={0:12,1:1,2:100001,3:"5",4:Infinity,5:-4,6:0,7:100000};'+fn+
 '[0,1,2,3,4,5,6,7,8].map(bestForStage)',
 {Number}
);
assert.deepEqual(Array.from(records),[12,1,null,null,null,null,null,100000,null],
 'valid records survive; strings, forged extremes and nonfinite values are rejected');
assert.ok(html.includes('id="best"'),'players must see their per-stage best record');
assert.ok(script.includes('bestDisplay.textContent="بهترین حرکت: "+(bestForStage(stage)??"—")'),
 'rendered HUD must update the best record after each move and victory');
assert.ok(script.includes('if(best===null||turns<best)bests[stage]=turns'),
 'victory must only replace a record with a genuinely better move count');
console.log('WATER_PATH_PERSONAL_BEST=PASS: visible, bounded, per-stage records');


// Runtime victory regression: completed pipes must not be rotatable after rewards are saved.
const renderStart=script.indexOf('function render(){');
const renderEnd=script.indexOf('board.addEventListener("keydown"',renderStart);
assert.ok(renderStart>=0&&renderEnd>renderStart,'render function must be available');
const renderCode=script.slice(renderStart,renderEnd);
function renderSolved(level){
 const board={buttons:[],replaceChildren(){this.buttons=[]},appendChild(b){this.buttons.push(b)},querySelector(){return null}};
 const next={disabled:true,focusCount:0,focus(){this.focusCount++}};
 const restart={focusCount:0,focus(){this.focusCount++}};
 const previous={disabled:false};
 const doc={createElement(){return {dataset:{},disabled:false,setAttribute(){},addEventListener(event,fn){if(event==='click')this.click=fn},focus(){}}},getElementById(id){assert.equal(id,'restart');return restart}};
 const state={
  stage:level,solved:false,completed:0,turns:7,bests:{},tiles:Array.from({length:25},()=>({mask:5})),
  reached:new Set([10,14]),board,next,previous,document:doc,
  movesDisplay:{textContent:''},bestDisplay:{textContent:''},progress:{textContent:''},status:{textContent:''},
  connected(){return true},bestForStage(){return null},tileSVG(){return '<svg></svg>'},
  save(){this.saved=true},beep(){},rotate(mask){return mask===5?10:5},Math,Number,Set
 };
 state.save=()=>{state.saved=true};
 vm.runInNewContext(renderCode+';render();',state);
 return {state,board,next,restart,previous};
}
const won=renderSolved(0);
assert.equal(won.state.solved,true,'successful pipe connection must lock the puzzle');
assert.equal(won.state.completed,1,'first victory must count as completed');
assert.equal(won.state.saved,true,'victory must persist progress');
assert.equal(won.board.buttons.length,25,'all board tiles must remain visible');
assert.ok(won.board.buttons.every(b=>b.disabled),'all solved pipe controls must be disabled');
assert.equal(won.next.disabled,false,'next stage must become available after victory');
assert.equal(won.next.focusCount,1,'keyboard focus must move to next stage');
const before=won.state.turns;
won.board.buttons[0].click();
assert.equal(won.state.turns,before,'a stale click callback must not rotate solved pipes');
const final=renderSolved(9);
assert.equal(final.next.disabled,true,'final stage must not offer a nonexistent stage eleven');
assert.equal(final.restart.focusCount,1,'final victory must focus replay rather than disabled next');
assert.ok(final.board.buttons.every(b=>b.disabled),'final solved puzzle must remain stable');
console.log('WATER_PATH_SOLVED_BOARD=PASS: immutable victory, focus handoff, and final-stage replay');

// Keyboard-accessibility regression: stage transitions and restart must focus a playable pipe.
const navStart=script.indexOf('next.addEventListener("click"');
const navEnd=script.indexOf('function toggle()',navStart);
assert.ok(navStart>=0&&navEnd>navStart,'stage navigation handlers must exist');
const navButtons={next:{},previous:{},restart:{}};
for(const button of Object.values(navButtons))button.addEventListener=function(type,fn){if(type==='click')this.click=fn};
const navState={stage:0,solved:true,next:navButtons.next,previous:navButtons.previous,
 document:{getElementById(id){assert.equal(id,'restart');return navButtons.restart}},
 setupCalls:0,focusCalls:0,setup(){this.setupCalls++},focusFirstPipe(){this.focusCalls++}};
vm.runInNewContext(script.slice(navStart,navEnd),navState);
navButtons.next.click();
assert.equal(navState.stage,1,'next stage advances exactly once');
assert.equal(navState.focusCalls,1,'next stage focuses a playable pipe');
navButtons.previous.click();
assert.equal(navState.stage,0,'previous stage returns to first stage');
assert.equal(navState.focusCalls,2,'previous stage restores playable keyboard focus');
navButtons.restart.click();
assert.equal(navState.setupCalls,3,'all three navigation actions reinitialize puzzle');
assert.equal(navState.focusCalls,3,'restart restores playable keyboard focus');
navState.solved=false;
navButtons.next.click();
assert.equal(navState.stage,0,'unsolved puzzle cannot skip a stage');
assert.equal(navState.focusCalls,3,'blocked next-stage action cannot steal focus');
assert.ok(script.includes('if(e.ctrlKey||e.metaKey||e.altKey||e.isComposing||e.target.isContentEditable'),
 'global shortcuts must not override browser shortcuts, IME or editable elements');
console.log('WATER_PATH_KEYBOARD_NAV=PASS: focus handoff, locked stage progression and shortcut safety');
