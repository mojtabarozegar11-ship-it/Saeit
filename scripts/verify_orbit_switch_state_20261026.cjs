'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync('mpw-editorial/nextwave/20261023/orbit-switch/index.html','utf8');
const src=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].at(-1)?.[1];
assert(src,'Orbit Switch inline game script missing');new vm.Script(src);
const part=(a,b)=>{const i=src.indexOf(a),j=src.indexOf(b,i+a.length);assert(i>=0&&j>i,a+' not found');return src.slice(i,j)};
const safeRead=part('function safeRead(', 'state.unlocked=');
for(const [stored,want] of [['Infinity',1],['NaN',1],['1.5',1],['150',150],['1000000000000',1000000000]]){
 const actual=vm.runInNewContext(safeRead+"safeRead('key',1)",{localStorage:{getItem(){return stored}}});
 assert.equal(actual,want,'unsafe saved record '+stored+' must not corrupt campaign');
}
const start=part('function start(){','function fail(){');
const context={
 state:{phase:'intermission',unlocked:5,lives:4,score:900,paused:false,playing:false},
 objects:[],particles:[],maxLevel:200,last:0,performance:{now:()=>1234},
 canvas:{focus(){}},el:()=>({hidden:true}),updateHud(){}
};
vm.runInNewContext(start+'start()',context);
assert.equal(context.state.phase,'play','Next stage must leave intermission state');
assert.equal(context.state.playing,true,'Next stage must resume active simulation');
const fail=part('function fail(){','function levelUp(){');
const saved=[];
const lost={state:{phase:'play',playing:true,best:20,score:90,level:5},safeStore:(k,v)=>saved.push([k,v]),updateHud(){},announce(){}};
vm.runInNewContext(fail+'fail()',lost);
assert.equal(lost.state.best,90,'Death must synchronize visible best with final score');
assert.equal(saved[0][1],90,'Death must persist synchronized best');
console.log('ORBIT_SWITCH_INTEGRITY_PASS: corrupt saves, stage transition, death score');
