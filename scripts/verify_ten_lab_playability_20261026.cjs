'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const src=fs.readFileSync('site_releases/mojplaywin/ten-lab-20261023/assets/arcade.js','utf8');
new vm.Script(src,{filename:'ten-lab-arcade.js'});
function section(start,end){const a=src.indexOf(start),b=src.indexOf(end,a+start.length);assert(a>=0&&b>a,'missing runtime '+start);return src.slice(a,b)}
const input=section('function inputKey(k){',"$('start').addEventListener('click',start);");
for(const [slug,expected] of [['grid-dominion',0],['lexicon-sprint',0],['metro-vault',1]]){
 const result=vm.runInNewContext('let active=true,paused=false,calls=0,nav=0;const slug='+JSON.stringify(slug)+';function action(){calls++}const scene={key(){nav++}};'+input+'inputKey("ArrowUp");({calls,nav})');
 assert.equal(result.calls,expected,slug+' ArrowUp must not trigger an unintended game action');
 assert.equal(result.nav,1,slug+' ArrowUp must reach game-specific keyboard handler');
}
const best=section('let best=0;try{','function text(');
for(const [stored,want] of [['Infinity',0],['-4',0],['42',42]]){
 const actual=vm.runInNewContext("const storageKey='test';"+best+'best',{localStorage:{getItem(){return stored}}});
 assert.equal(actual,want,'corrupt ten-lab best must be sanitized');
}
const metro=section('function metro(){','function cargo(){');
const metroResult=vm.runInNewContext('let clock=0,score=0,level=1;'+metro+'const scene=metro();for(let i=0;i<55;i++)scene.update(.1);({score,level})',{
 rand:(a,b)=>b-.01,down:()=>false,finish:()=>{},note:()=>{},clamp:(x,a,b)=>Math.max(a,Math.min(b,x))
});
assert(metroResult.score>180,'Metro Vault collected coin bonuses must survive later frames');
const dominion=section('function dominion(){','function metro(){');
const strokes=[];
vm.runInNewContext('let score=0,level=1,active=true,paused=false;'+dominion+'dominion().draw()',{
 ctx:{strokeRect(...args){strokes.push(args)}},strokes,clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),bg:()=>{},rect:()=>{},text:()=>{},finish:()=>{},note:()=>{}
});
assert(strokes.length>1,'Grid Dominion must visually indicate affordable legal claims');
const lexicon=section('function lexicon(){','function dominion(){');
const outlines=[];
let seed=12345;
vm.runInNewContext('let score=0,level=1,active=true,paused=false;'+lexicon+'const scene=lexicon();scene.key("ArrowRight");scene.draw()',{
 rand:(a,b)=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return a+(b-a)*(seed/4294967296)},
 ctx:{strokeRect(...args){outlines.push(args)}},outlines,clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),bg:()=>{},rect:()=>{},text:()=>{},finish:()=>{},note:()=>{}
});
assert(outlines.some(args=>args[0]===129),'Lexicon Sprint keyboard cursor must move visibly right');
assert(src.includes("if(ix===buoys.length){finish(true,'All five buoys rounded');return}"),'Windward Regatta must stop simulation immediately on victory');
assert(src.includes("else if(settled>=35)finish(true,'All 35 shipments dispatched')"),'Cargo Switchyard must not award victory on a fatal last shipment');
console.log('TEN_LAB_PLAYABILITY_PASS: five games, keyboard isolation, coin persistence, tactical cues and outcome safety');
