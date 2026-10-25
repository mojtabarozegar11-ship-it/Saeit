'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const read=p=>fs.readFileSync(p,'utf8');
const between=(s,a,b)=>{
 const i=s.indexOf(a),j=s.indexOf(b,i+a.length);
 assert.ok(i>=0&&j>i,'missing function boundary '+a);
 return s.slice(i,j);
};
const inline=s=>[...s.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const rah=read('templates/studio_raha/index.html');
const tan=read('templates/taniya_studio/index.html');
const prism=read('mpw-editorial/field-guides/20261023/prism-relay/index.html');
for(const [name,html] of [['Raham',rah],['Taniya',tan],['Prism',prism]]){
 const js=inline(html);assert.ok(js.length>0,name+' inline script missing');
 js.forEach(code=>new vm.Script(code,{filename:name+'.js'}));
}
assert.equal((tan.match(/<article class="game"/g)||[]).length,20,'Taniya 20-game catalog must remain intact');
const cake=between(tan,'function cakeCardMarkup(', 'function mountCake(){');
const cakeCases=vm.runInNewContext(cake+"[cakeCardMarkup('#ff79b8','🍓',0),cakeCardMarkup('#4488cc','🌼',4),cakeCardMarkup('unsafe','🍬',99)]",{});
assert.notEqual(cakeCases[0],cakeCases[1],'cake designs must change SVG');
assert.ok(cakeCases[1].includes('#4488cc'),'selected frosting must appear in SVG');
assert.equal((cakeCases[1].match(/y="480"/g)||[]).length,4,'four candles must be drawn');
assert.equal((cakeCases[2].match(/y="480"/g)||[]).length,12,'candle cap must be enforced');
assert.ok(!cakeCases[2].includes('unsafe'),'untrusted color must be rejected');
const clean=between(prism,'function cleanProgress(', 'function load(){');
const cases=vm.runInNewContext('const MAX=150;'+clean+"[cleanProgress({version:1,unlocked:2,best:{'1':3,'2':999,'150':3}}),cleanProgress({version:1,unlocked:9999,best:[]}),cleanProgress(null)]",{});
assert.equal(cases[0].unlocked,2);
assert.equal(cases[0].best['1'],3);
assert.equal(Object.keys(cases[0].best).length,1);
assert.equal(cases[1].unlocked,150);
assert.equal(cases[2].unlocked,1);
const jungle=between(rah,'function jungleRunGame(stage){','function runnerGame(stage){');
function runJungle(choices){
 const listeners=new Map(),stage={isConnected:true,buttons:[],_html:'',get innerHTML(){return this._html},set innerHTML(v){this._html=v;this.buttons=[]},querySelector(){return {append(...items){stage.buttons.push(...items)}}}};
 const sandbox={Math:Object.assign(Object.create(Math),{random:()=>0}),localStorage:{getItem(){return '0'},setItem(){}},document:{
  getElementById(){return {classList:{contains(){return true}}}},
  addEventListener(event,fn){listeners.set(event,fn)},
  removeEventListener(event,fn){if(listeners.get(event)===fn)listeners.delete(event)}
 },button(text,fn){return {text,click:fn}}};
 vm.runInNewContext('let jungleCleanup=()=>{};'+jungle+'jungleRunGame(stage);',Object.assign(sandbox,{stage}));
 for(const move of choices){const b=stage.buttons.find(x=>x.text.toLowerCase().startsWith(move));assert.ok(b,'action '+move+' unavailable');b.click()}
 return {stage,listeners};
}
const win=runJungle(Array(12).fill('jump'));
assert.ok(win.stage.innerHTML.includes('Jungle cleared!'),'12 correct jumps should win');
const lose=runJungle(Array(3).fill('duck'));
assert.ok(lose.stage.innerHTML.includes('jungle wins'),'three wrong moves should end run');
console.log('GAME_QUALITY_REGRESSION_PASS: Raham runner, Taniya cake SVG, Prism progress, three JS parsers');
