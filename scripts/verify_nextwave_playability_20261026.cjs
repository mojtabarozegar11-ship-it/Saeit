'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const src=fs.readFileSync('site_releases/mojplaywin/ten-lab-20261023-next/assets/arcade.js','utf8');
new vm.Script(src,{filename:'nextwave-arcade.js'});
function section(a,b){const i=src.indexOf(a),j=src.indexOf(b,i+a.length);assert(i>=0&&j>i,'missing game section '+a);return src.slice(i,j)}
const hex=section('function hexBloom(){','function prismRelay(){');
const targets=[0,2,4,6,8,10,12,14,16,18,20],remaining=Array.from({length:25},(_,i)=>i);
let calls=0,hexRewards=0;
const hexRnd=()=>{if(calls<22){if(calls%2===0){const idx=remaining.indexOf(targets[calls/2]);remaining.splice(idx,1);calls++;return idx}calls++;return 1}return 0};
vm.runInNewContext('let level=1,playing=true,paused=false;'+hex+'const scene=hexBloom();scene.click({x:240,y:38});scene.click({x:333,y:38})',{
 rnd:hexRnd,reward:n=>{hexRewards+=n},notify:()=>{},finish:()=>{},clamp:(x,a,b)=>Math.max(a,Math.min(b,x))
});
assert(hexRewards>0,'Hex Bloom must guarantee a playable pair on an initially isolated checkerboard');
const prism=section('function prismRelay(){','function kitchenRush(){');
let prismRewards=0;
vm.runInNewContext('let level=1,playing=true,paused=false;'+prism+"const scene=prismRelay();scene.act('action');scene.act('right');scene.act('action');scene.act('action');",{
 reward:n=>{prismRewards+=n},notify:()=>{},finish:()=>{}
});
assert.equal(prismRewards,500,'Prism Relay keyboard solve must score once, not repeatedly during transition');
const kitchen=section('function kitchenRush(){','function typeDefender(){');
const finishes=[];
vm.runInNewContext('let level=1,playing=true,paused=false;'+kitchen+'kitchenRush().update(95)',{
 rnd:()=>0,reward:()=>{},notify:()=>{},finish:(won,msg)=>finishes.push({won,msg})
});
assert.equal(finishes.length,1,'Kitchen Rush simultaneous timer and customer timeout must resolve once');
assert.equal(finishes[0].won,false);
function checkPostFinish(start,end,game,rand){
 const source=section(start,end),input={value:'1234',addEventListener(){},parentElement:{remove(){}},focus(){}};
 vm.runInNewContext('let level=1,playing=false,paused=false;'+source+'const scene='+game+'();scene.act("action")',{
  mountInput:()=>input,rnd,reward:()=>{throw Error('post-finish score changed')},notify:()=>{},finish:()=>{}
 });
 assert.equal(input.value,'1234',game+' must not mutate input after game end');
}
checkPostFinish('function typeDefender(){','function codebreaker(){','typeDefender',()=>0);
let k=0;checkPostFinish('function codebreaker(){','const builders=','codebreaker',()=>k++%4);
const best=section('let best=0;try{','function bg('),hudReward=section('function hud(){','function finish(');
const score=vm.runInNewContext("const slug='hex-bloom';let score=0,level=1;"+best+hudReward+'reward(Infinity);reward(-1);reward(50);({score,best})',{
 localStorage:{getItem(){return 'Infinity'},setItem(){}},$:()=>({textContent:''})
});
assert.equal(score.score,50,'Nextwave must ignore invalid reward events');
assert.equal(score.best,50,'Nextwave must recover from nonfinite stored personal best');
console.log('NEXTWAVE_PLAYABILITY_PASS: Hex, Prism, Kitchen, Type, Codebreaker and score ledger');
