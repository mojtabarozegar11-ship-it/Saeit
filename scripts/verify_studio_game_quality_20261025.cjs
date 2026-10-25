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
const cakeCases=vm.runInNewContext(cake+"[cakeCardMarkup('#ff79b8','🍓',0),cakeCardMarkup('#4488cc','🌼',4),cakeCardMarkup('unsafe','🍬',99),cakeCardMarkup('#4488cc','🍓',2,'Happy Birthday'),cakeCardMarkup('#4488cc','🍓',2,'<script>alert(1)</script>')]",{});
assert.notEqual(cakeCases[0],cakeCases[1],'cake designs must change SVG');
assert.ok(cakeCases[1].includes('#4488cc'),'selected frosting must appear in SVG');
assert.equal((cakeCases[1].match(/y="480"/g)||[]).length,4,'four candles must be drawn');
assert.equal((cakeCases[2].match(/y="480"/g)||[]).length,12,'candle cap must be enforced');
assert.ok(!cakeCases[2].includes('unsafe'),'untrusted color must be rejected');
assert.ok(cakeCases[3].includes('Happy Birthday'),'selected greeting must appear in SVG');
assert.ok(!cakeCases[4].includes('<script>'),'untrusted greeting must be rejected');
const clean=between(prism,'function cleanProgress(', 'function load(){');
const cases=vm.runInNewContext('const MAX=150;'+clean+"[cleanProgress({version:1,unlocked:2,best:{'1':3,'2':999,'150':3}}),cleanProgress({version:1,unlocked:9999,best:[]}),cleanProgress(null)]",{});
assert.equal(cases[0].unlocked,2);
assert.equal(cases[0].best['1'],3);
assert.equal(Object.keys(cases[0].best).length,1);
assert.equal(cases[1].unlocked,150);
assert.equal(cases[2].unlocked,1);
const jungle=between(rah,'function jungleRunGame(stage){','function runnerGame(stage){');
function runJungle(choices,random=()=>0){
 const listeners=new Map(),storage=new Map(),stage={isConnected:true,buttons:[],_html:'',get innerHTML(){return this._html},set innerHTML(v){this._html=v;this.buttons=[]},querySelector(){return {append(...items){stage.buttons.push(...items)}}}};
 const sandbox={Math:Object.assign(Object.create(Math),{random}),localStorage:{getItem(k){return storage.get(k)||'0'},setItem(k,v){storage.set(k,v)}},document:{
  getElementById(){return {classList:{contains(){return true}}}},
  addEventListener(event,fn){listeners.set(event,fn)},
  removeEventListener(event,fn){if(listeners.get(event)===fn)listeners.delete(event)}
 },button(text,fn){return {text,click:fn}}};
 vm.runInNewContext('let jungleCleanup=()=>{};'+jungle+'jungleRunGame(stage);',Object.assign(sandbox,{stage}));
 const seen=[];
 for(const move of choices){
  const hint=stage.innerHTML.includes('Jump over the log!')?'jump':stage.innerHTML.includes('Duck under the vines!')?'duck':'sidestep';
  seen.push(hint);
  const selected=typeof move==='function'?move(hint):move;
  const b=stage.buttons.find(x=>x.text.toLowerCase().startsWith(selected));
  assert.ok(b,'action '+selected+' unavailable');b.click();
 }
 return {stage,listeners,seen,storage};
}

const win=runJungle(Array(12).fill(hint=>hint));
for(const hazard of ['jump','duck','sidestep'])assert.equal(win.seen.filter(x=>x===hazard).length,4,'every jungle course must balance '+hazard);
assert.ok(win.stage.innerHTML.includes('Jungle cleared!'),'12 correct jumps should win');
assert.ok(Number(win.storage.get('studio-raha-jungle-best-v1'))>0,'jungle personal best must persist');
assert.ok(win.stage.innerHTML.includes('Best '+win.storage.get('studio-raha-jungle-best-v1')),'jungle UI must display saved record');
const lose=runJungle(Array(3).fill(hint=>hint==='jump'?'duck':'jump'));
assert.ok(lose.stage.innerHTML.includes('jungle wins'),'three wrong moves should end run');
const sidestep=runJungle(Array(12).fill(hint=>hint),()=>.99);
assert.ok(sidestep.stage.innerHTML.includes('Jungle cleared!'),'twelve sidesteps must clear mud course');
assert.ok(sidestep.stage.innerHTML.includes('Streak 12'),'perfect course should build a streak');
// Exercise the actual Cake Maker UI callbacks, not only its SVG serializer.
const cakeUI=between(tan,'function mountCake(){','function mountPet(){');
let cakeNodes={},downloaded='';
const cakeSandbox={
 stage(html){cakeNodes={'#cakepreview':{innerHTML:''},'#icing':{},'#cakeGreeting':{},
  '[data-action="candle"]':{},'[data-action="cake-remove"]':{},
  '[data-action="cake-reset"]':{},'[data-action="cake-download"]':{}};},
 gamebody:{querySelector(sel){return cakeNodes[sel]},querySelectorAll(sel){return sel==='[data-top]'?[{dataset:{top:'🌼'},onclick:null}]:[]}},
 $(sel){return cakeNodes[sel]},
 btn(label,action){return '<button data-action="'+action+'">'+label+'</button>'},
 say(){},downloadSvg(name,svg){downloaded=svg}
};
vm.runInNewContext(cake+cakeUI+'mountCake();',cakeSandbox);
cakeNodes['[data-action="candle"]'].onclick();
cakeNodes['[data-action="candle"]'].onclick();
assert.equal((cakeNodes['#cakepreview'].innerHTML.match(/y="480"/g)||[]).length,2,'candle additions must update preview');
cakeNodes['[data-action="cake-remove"]'].onclick();
assert.equal((cakeNodes['#cakepreview'].innerHTML.match(/y="480"/g)||[]).length,1,'remove candle must update preview');
cakeNodes['[data-action="cake-reset"]'].onclick();
assert.equal((cakeNodes['#cakepreview'].innerHTML.match(/y="480"/g)||[]).length,0,'start over must reset all candles');
cakeNodes['[data-action="cake-download"]'].onclick();
assert.ok(downloaded.includes('#ff79b8'),'reset must restore default icing in exported design');
// Verify Cake Maker persistence survives a complete UI remount without trusting stored markup.
const savedCake=new Map();cakeSandbox.localStorage={getItem:k=>savedCake.get(k)||null,setItem:(k,v)=>savedCake.set(k,v)};
vm.runInNewContext(cake+cakeUI+'mountCake();',cakeSandbox);
cakeNodes['#icing'].oninput({target:{value:'#4488cc'}});
cakeNodes['#cakeGreeting'].onchange({target:{value:'Congratulations'}});
cakeNodes['[data-action="candle"]'].onclick();
assert.ok(savedCake.has('taniya-cake-design-v1'),'cake design must persist after editing');
vm.runInNewContext(cake+cakeUI+'mountCake();',cakeSandbox);
assert.ok(cakeNodes['#cakepreview'].innerHTML.includes('#4488cc'),'frosting must restore on remount');
assert.ok(cakeNodes['#cakepreview'].innerHTML.includes('Congratulations'),'greeting must restore on remount');
assert.equal((cakeNodes['#cakepreview'].innerHTML.match(/y="480"/g)||[]).length,1,'candles must restore on remount');
savedCake.set('taniya-cake-design-v1',JSON.stringify({icing:'url(javascript:alert(1))',topping:'<svg>',candles:999,greeting:'<script>'}));
vm.runInNewContext(cake+cakeUI+'mountCake();',cakeSandbox);
assert.ok(!cakeNodes['#cakepreview'].innerHTML.includes('javascript'),'tampered cake color must be rejected');
assert.ok(!cakeNodes['#cakepreview'].innerHTML.includes('<script>'),'tampered greeting must be rejected');
console.log('GAME_QUALITY_REGRESSION_PASS: Raham runner, Taniya cake SVG, Prism progress, three JS parsers');
