'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(path.join(__dirname,'../../games/air-supremacy/index.html'),'utf8');
assert.match(html,/MAX_MISSION=12/);
assert.match(html,/missionKills>=missionGoal/);
assert.doesNotMatch(html,/missionT>58/);
assert.doesNotMatch(html,/fetch\(/);
const match=html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(match);
const raw=match[1];
new vm.Script(raw,{filename:'air-supremacy.js'});
const saved=new Map();
function makeGame(){
 const nodes=new Map();
 function node(id=''){
   const listeners={};
   return {
     id,textContent:'',innerHTML:'',value:'',disabled:false,hidden:false,
     style:{},children:[],attributes:{},listeners,
     classList:{
       values:new Set(),
       add(...x){x.forEach(k=>this.values.add(k))},
       remove(...x){x.forEach(k=>this.values.delete(k))},
       toggle(k,v){if(v===undefined?v:!!v)this.values.add(k);else this.values.delete(k);return this.values.has(k)},
       contains(k){return this.values.has(k)}
     },
     setAttribute(k,v){this.attributes[k]=v},
     append(...parts){this.children.push(...parts)},
     replaceChildren(...parts){this.children=parts;this.value=''},
     querySelectorAll(){return []},
     addEventListener(k,fn){listeners[k]=fn},
     removeEventListener(k){delete listeners[k]},
     getBoundingClientRect(){return {left:0,right:100,bottom:100,width:100,height:100}},
     setPointerCapture(){},getContext(){return null}
   };
 }
 const dom={
   hidden:false,
   createElement(t){return node(t)},
   createTextNode(t){return {textContent:String(t)}},
   getElementById(id){if(!nodes.has(id))nodes.set(id,node(id));return nodes.get(id)},
   addEventListener(){},
 };
 const storage={getItem:k=>saved.has(k)?saved.get(k):null,setItem(k,v){saved.set(k,String(v))}};
 const canvas=dom.getElementById('field');
 canvas.getContext=k=>k==='2d'?{}:null;
 const sandbox={
   document:dom,localStorage:storage,navigator:{maxTouchPoints:0},
   innerWidth:1280,innerHeight:720,devicePixelRatio:1,
   performance:{now:()=>0},setTimeout(fn){fn()},requestAnimationFrame(){},addEventListener(){},
   console,Math,Uint8Array,Float32Array,Date,JSON,Number,String,Array,Map,Set,
 };
 sandbox.window=sandbox;
 const extra=[
 'window.__AIR_TEST__={',
 'snapshot:()=>({...window.__AIR_SUPREMACY_QA__.snapshot(),',
 'unlocked:profile.unlocked,credits:profile.credits,earned:creditsEarned,',
 'missionKills,missionGoal,missionBossNeeded,bossSpawned,bossCleared,',
 'missionNotified,pendingMissionAdvance,upgrades:{...profile.upgrades}}),',
 'step:simulate,spawn:spawnEnemy,kill,fire:shoot,missile:launchMissile,',
 'hit,resolveMission,finish,pause:togglePause,',
 'current:()=>({player,enemies,missiles,profile}),refreshHangar};',
 ].join('\n');
 const insertPoint='spawnScenery();last=performance.now();requestAnimationFrame(loop);';
 assert.ok(raw.includes(insertPoint));
 vm.runInNewContext(raw.replace(insertPoint,extra+'\n'+insertPoint),sandbox,{timeout:4000,filename:'air-supremacy.test.js'});
 const api=sandbox.__AIR_TEST__;
 assert.ok(api);
 return {api,el:id=>dom.getElementById(id)};
}
{
 const {api,el}=makeGame();
 assert.equal(api.snapshot().unlocked,1);
 assert.equal(api.snapshot().credits,0);
 assert.equal(typeof el('launch').onclick,'function');
 el('launch').onclick();
 assert.equal(api.snapshot().playerHp,100);
 assert.equal(api.snapshot().shield,100);
 assert.equal(api.snapshot().mission,1);
 let foes=api.current().enemies;
 api.spawn();
 const e=foes[0];e.z=-90;e.x=0;e.y=3;
 for(let i=0;i<20&&foes.includes(e);i++){api.fire();api.step(.13)}
 assert.ok(!foes.includes(e),'Player cannon must defeat target with actual cooldown');
 assert.ok(api.snapshot().kills>=1);
 api.pause(true);
 assert.equal(api.snapshot().paused,true);
 assert.equal(el('pauseOverlay').classList.contains('on'),true);
 api.pause(false);
 assert.equal(api.snapshot().paused,false);
 for(let level=1;level<=12;level++){
   assert.equal(api.snapshot().mission,level);
   const remaining=api.snapshot().missionGoal-api.snapshot().missionKills;
   for(let j=0;j<remaining;j++){api.spawn();api.kill(api.current().enemies.at(-1))}
   if(level%3===0){
     if(!api.snapshot().bossSpawned)api.spawn(true);
     const boss=api.current().enemies.find(x=>x.boss);
     assert.ok(boss,'Mission '+level+' must have a capital ship');
     api.kill(boss);
   }
   assert.equal(api.snapshot().pendingMissionAdvance,true,'Objective requirement '+level);
   api.step(.016);
   if(level<12)assert.equal(api.snapshot().mission,level+1);
   else assert.equal(api.snapshot().running,false);
 }
 assert.equal(api.snapshot().unlocked,12);
 assert.ok(api.snapshot().credits>=1200);
 assert.equal(el('endLabel').textContent,'CAMPAIGN CLEARED');
 const profile=JSON.parse(saved.get('mpw-air-supremacy-campaign-v2'));
 assert.equal(profile.unlocked,12);assert.equal(profile.wins,1);
 const before=api.snapshot().credits;
 el('cannonUpgrade').listeners.click();
 assert.equal(api.snapshot().upgrades.cannon,1);
 assert.equal(api.snapshot().credits,before-250);
}
{
 const {api,el}=makeGame();
 assert.equal(api.snapshot().unlocked,12);
 assert.equal(api.snapshot().upgrades.cannon,1);
 assert.equal(Number(el('missionSelect').value),12);
 el('launch').onclick();
 assert.equal(api.snapshot().mission,12);
 api.finish(false);
 const credits=api.snapshot().credits;
 api.finish(false);
 assert.equal(api.snapshot().credits,credits,'No repeat payout from finish');
}
// A guided missile must hit on the swept segment, not just at its previous position.
{
 const {api,el}=makeGame();
 el('launch').onclick();
 api.spawn();
 const e=api.current().enemies.at(-1);
 Object.assign(e,{x:0,y:3,z:-31,speed:0,shot:100,hp:5});
 api.missile();
 assert.equal(api.current().missiles.length,1,'missile launched after target lock');
 e.z=-25; // 21 units ahead of missile; a 0.1s step travels 19 units.
 api.step(.1);
 assert.equal(api.current().enemies.includes(e),false,'swept missile must hit in same frame');
}
// An already-expired missile must not deal damage or survive another frame.
{
 const {api,el}=makeGame();
 el('launch').onclick();
 api.spawn();
 const e=api.current().enemies.at(-1);
 Object.assign(e,{x:0,y:3,z:-31,speed:0,shot:100,hp:5});
 api.missile();
 const m=api.current().missiles.at(-1);
 m.life=0;e.z=-14;
 api.step(.016);
 assert.equal(e.hp,5,'expired missile must not deal damage');
 assert.equal(api.current().missiles.length,0,'expired missile must be removed');
}
// A lethal aircraft collision must not award a post-sortie guided-missile kill.
{
 const {api,el}=makeGame();
 el('launch').onclick();
 api.spawn();
 const lethal=api.current().enemies.at(-1);
 Object.assign(lethal,{x:0,y:3,z:-5,speed:0,shot:100});
 api.spawn();
 const target=api.current().enemies.at(-1);
 Object.assign(target,{x:0,y:3,z:-31,speed:0,shot:100,hp:5});
 api.missile();
 target.z=-14;
 Object.assign(api.current().player,{hp:1,shield:0,inv:0});
 api.step(.016);
 assert.equal(api.snapshot().running,false,'lethal collision must end sortie');
 assert.equal(target.hp,5,'missile must not damage target after sortie ends');
}
console.log('AIR_SUPREMACY_GAMEPLAY_PASS: 100 hull, actual cannon combat, 12 objective clears, 4 bosses, pause, credits, persistent upgrades, replay payout guard');
