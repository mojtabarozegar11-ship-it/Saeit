const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('games/crown-defender/index.html','utf8'), code=html.split('<script>')[1].split('</script>')[0];
assert.match(html, /<link rel="canonical" href="https:\/\/mojplaywin\.com\/games\/crown-defender\/">/);
assert.match(html, /<meta property="og:url" content="https:\/\/mojplaywin\.com\/games\/crown-defender\/">/);
assert.match(html, /<meta name="twitter:card" content="summary">/);
assert.match(html,/MOJ1 is the planned premium purchase asset; checkout is disabled pending verified TRON contract/);
assert.doesNotMatch(code,/location\.href=item\.checkout/,'client must not navigate to legacy USD checkout');
// The actual saved economy loader must not coerce strings, booleans or decimals
// into credits, hangar upgrades or campaign progress.
const saveStart=code.indexOf('const STORAGE='),saveEnd=code.indexOf('let save=loadSave();',saveStart);
assert.ok(saveStart>=0&&saveEnd>saveStart,'production save loader must be extractable');
function readCrownSave(payload){
  const ctx={localStorage:{getItem:()=>JSON.stringify(payload)},JSON};
  vm.createContext(ctx);
  vm.runInContext('const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));\\n'.replace('\\n','\n')+
    code.slice(saveStart,saveEnd)+'\nglobalThis.loaded=loadSave();',ctx);
  return JSON.parse(JSON.stringify(ctx.loaded));
}
const clean=readCrownSave({schema:120,best:1800,credits:230,hangar:{armor:2},
  campaign:{unlockedSector:3,cleared:false},stats:{kills:12}});
assert.equal(clean.credits,230);
assert.equal(clean.hangar.armor,2);
assert.equal(clean.campaign.unlockedSector,3);
assert.equal(clean.stats.kills,12);
const forged=readCrownSave({schema:120,best:'9000',credits:'1000000',
  hangar:{armor:true,engine:3.5},campaign:{unlockedSector:'10',cleared:false},
  stats:{kills:[],attempts:1.25}});
assert.equal(forged.best,0,'string best cannot become earned score');
assert.equal(forged.credits,0,'string credits cannot become earned currency');
assert.equal(forged.hangar.armor,0,'boolean cannot become an upgrade');
assert.equal(forged.hangar.engine,0,'fractional upgrades are rejected');
assert.equal(forged.campaign.unlockedSector,1,'string stage cannot unlock sectors');
assert.equal(forged.stats.kills,0);
assert.equal(forged.stats.attempts,0);

const validClear=readCrownSave({schema:120,campaign:{unlockedSector:10,cleared:true}});
assert.equal(validClear.campaign.cleared,true,'real boolean completion remains readable');
for(const [schema,cleared] of [[120,'true'],[120,{}],[120,1],['120',true],[null,true]]){
  assert.equal(readCrownSave({schema,campaign:{unlockedSector:10,cleared}}).campaign.cleared,false,
    'forged campaign clear must not unlock the victory state');
}

// Saved quality/contrast are enum values, not arbitrary strings. A forged
// quality setting must not bypass auto low-detail mode on weaker devices.
const validSettings=readCrownSave({settings:{quality:'low',contrast:'high',autofire:false,sound:true}});
assert.deepEqual(validSettings.settings,{quality:'low',contrast:'high',autofire:false,sound:true});
const forgedSettings=readCrownSave({settings:{quality:'ultra',contrast:'flashing',autofire:'false',sound:1}});
assert.deepEqual(forgedSettings.settings,{quality:'auto',contrast:'normal',autofire:true,sound:false},
  'invalid saved settings must fall back to safe defaults');
const mixedSettings=readCrownSave({settings:{quality:'high',contrast:'unknown',autofire:false,sound:'true'}});
assert.deepEqual(mixedSettings.settings,{quality:'high',contrast:'normal',autofire:false,sound:false},
  'valid settings survive without coercing malformed neighbors');

// Legacy score migration is a separate untrusted storage channel.
const legacyLine=code.split('\n').find(line=>line.startsWith('let save=loadSave();try{'));
assert.ok(legacyLine,'legacy migration source is available for executable regression');
function migratedLegacyBest(value){
  const ctx={loadSave:()=>({best:0}),localStorage:{getItem:()=>value},JSON};
  vm.createContext(ctx);vm.runInContext(legacyLine,ctx);
  return vm.runInContext('save.best',ctx);
}
for(const value of ['Infinity','1e309','NaN','-12']){
  assert.equal(migratedLegacyBest(value),0,'invalid legacy best: '+value);
}
assert.equal(migratedLegacyBest('2500'),2500,'finite legacy score remains compatible');
assert.equal(migratedLegacyBest('1e15'),1e10,'legacy score is bounded by current save schema');
let frame, fetchMode='offline', drawCalls=0;
const pixels=new Proxy({createLinearGradient:()=>({addColorStop(){}}),createRadialGradient:()=>({addColorStop(){}})}, {get(o,k){return o[k]||function(...args){drawCalls++;for(const v of args)if(typeof v==='number')assert.ok(Number.isFinite(v),'finite canvas argument')}}});
class Element{constructor(tag='DIV'){this.tagName=tag;this.children=[];this.hidden=false;this.value='';this.style={};this.classList={add(){},remove(){},toggle(){}};this.handlers={};if(tag==='IMG'&&!process.env.CROWN_NO_ASSETS){this.complete=true;this.naturalWidth=384;this.naturalHeight=512;}}getContext(){return pixels}append(...x){this.children.push(...x)}appendChild(x){this.children.push(x)}replaceChildren(...x){this.children=x}setAttribute(){}addEventListener(n,f){this.handlers[n]=f}focus(){}getBoundingClientRect(){return {left:0,top:0,width:540,height:960}}}
const elements={};for(const m of html.matchAll(/<([a-z]+)[^>]*\bid="([^"]+)"[^>]*>/g))elements[m[2]]=new Element(m[1].toUpperCase());
elements.mode.value='campaign';elements.difficulty.value='easy';elements.startSector.value='1';
const storage=new Map([['mpw-crown-v10-save',JSON.stringify({schema:120,best:'Infinity',credits:'Infinity',hangar:{armor:'Infinity'},campaign:{unlockedSector:'Infinity',cleared:false},stats:{kills:'Infinity'},achievements:['FIRST_CONTACT','FIRST_CONTACT','ACE','FORGED_ADMIN','x'.repeat(10000)],history:[{score:42,mode:'campaign',wave:2,when:'2026-10-27',win:false},{score:-5,mode:'campaign',wave:1},{score:1,mode:'<script>',wave:1},{score:10,mode:'bossrush',wave:'invalid'},{score:100,mode:'endless',wave:3,when:'x'.repeat(10000)}]} )],['mpw-crown-fleet-v120',JSON.stringify({jets:['falcon','spectre'],selected:'spectre',livery:'arctic',trail:'ion'})]]);
const document={getElementById(id){assert.ok(elements[id],'real element '+id);return elements[id]},createElement:tag=>new Element(tag.toUpperCase()),body:new Element(),handlers:{},addEventListener(n,f){this.handlers[n]=f},hidden:false};
const sandbox={document,HTMLElement:Element,console,Math,Date,Set,JSON,Number,Object,String,Array,Promise,AbortController,setTimeout,clearTimeout,URL,
 localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},navigator:{hardwareConcurrency:4,getGamepads:()=>[]},matchMedia:()=>({matches:false}),requestAnimationFrame:f=>frame=f,location:{href:''},fetch:async()=>{if(fetchMode==='offline')throw Error('offline');if(fetchMode==='checkout')return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({game:'crown-defender',version:1,authenticated:true,owned:[],items:[{sku:'cd-spectre',currency:'USD',price:'4.00',available:true,checkout:'/store/crown/999/checkout/'}]})};return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({game:'crown-defender',version:1,authenticated:true,owned:['cd-spectre'],items:[{sku:'cd-spectre',currency:'USD',price:'4.00',available:true,checkout:'/store/product/999/checkout/'}]})}}};sandbox.window=sandbox;sandbox.addEventListener=()=>{};vm.createContext(sandbox);vm.runInContext(code,sandbox);const game=sandbox.__mpwCrownDefenderTest;

// Menu keys are native page input, never latent gameplay movement/fire.
let menuPrevented=false;
document.handlers.keydown({code:'KeyW',target:document.body,repeat:false,preventDefault(){menuPrevented=true}});
document.handlers.keydown({code:'Space',target:document.body,repeat:false,preventDefault(){menuPrevented=true}});
assert.equal(game.getInput().keys,0,'menu key presses must not latch gameplay input');
assert.equal(menuPrevented,false,'menu Space must retain native browser behavior');
elements.leaders.handlers.click();assert.match(elements.overlayText.textContent,/Achievements: 2\/15/,'only two valid unique achievements count');const records=elements.leaderList.children[0].children;assert.equal(records.length,2,'malformed score, mode and wave records must be discarded');assert.match(records[0].textContent,/42.*campaign.*wave 2/);assert.match(records[1].textContent,/100.*endless.*wave 3/);
assert.equal(game.getState().version,121);assert.equal(game.getState().activeJet,'falcon','local forged premium ignored');game.start();assert.equal(game.getState().bank,0,'nonfinite credits must not become maximum credits');assert.equal(game.getState().best,0,'nonfinite best must not become maximum score');assert.equal(game.getState().sector,1,'nonfinite unlocked sector must not skip campaign');assert.equal(game.getState().upgrades.armor,0,'nonfinite saved armor must not boost player');assert.equal(game.getState().hp,100);
// Actual registered pointer handlers: secondary touches must not steal or
// release an active drag or fire control. Pointer-capture failure is harmless.
const pointerEvent=id=>({pointerId:id,clientX:270,clientY:480,preventDefault(){}});
elements.game.setPointerCapture=id=>{elements.game.captureId=id};
elements.game.handlers.pointerdown(pointerEvent(1));
assert.equal(game.getInput().touchActive,true);
elements.game.handlers.pointerdown(pointerEvent(2));
assert.equal(elements.game.captureId,1,'second finger cannot steal ship drag');
elements.game.handlers.pointerup(pointerEvent(2));
assert.equal(game.getInput().touchActive,true,'unrelated finger cannot release ship drag');
elements.game.handlers.pointerup(pointerEvent(1));
assert.equal(game.getInput().touchActive,false);
elements.fire.setPointerCapture=id=>{elements.fire.captureId=id};
elements.fire.handlers.pointerdown(pointerEvent(11));
assert.equal(game.getInput().held.fire,true);
elements.fire.handlers.pointerdown(pointerEvent(12));
assert.equal(elements.fire.captureId,11,'second fire touch cannot steal capture');
elements.fire.handlers.pointerup(pointerEvent(12));
assert.equal(game.getInput().held.fire,true,'unrelated release cannot stop firing');
elements.fire.handlers.pointercancel(pointerEvent(11));
assert.equal(game.getInput().held.fire,false);
elements.left.setPointerCapture=()=>{throw new Error('capture blocked')};
elements.left.handlers.pointerdown(pointerEvent(14));
assert.equal(game.getInput().held.left,false,'capture failure must not latch movement');
elements.left.setPointerCapture=()=>{};
elements.left.handlers.pointerdown(pointerEvent(15));
assert.equal(game.getInput().held.left,true);
assert.equal(game.getState().maxHp,100);for(let i=1;i<=180;i++)frame(i*16);assert.ok(drawCalls>1000);assert.ok(game.getState().shots>0);assert.ok(game.getState().enemies+game.getState().kills>0);// Browser shortcuts and IME must not latch movement, fire or special actions.
for(const patch of [{ctrlKey:true},{altKey:true},{metaKey:true},{isComposing:true},{keyCode:229}]){
  let prevented=false;
  document.handlers.keydown({code:'KeyE',target:document.body,repeat:false,
    preventDefault(){prevented=true},...patch});
  assert.equal(prevented,false,'modified/composing shortcut must remain native');
  assert.equal(game.getInput().keys,0,'modified/composing shortcut cannot latch game key');
}
// Regression: an already-held key must not survive a browser shortcut or IME.
// Before this fix, Ctrl+W left the ship moving if the browser swallowed keyup.
document.handlers.keydown({code:'KeyW',target:document.body,repeat:false,preventDefault(){}});
assert.equal(game.getInput().keys,1);
document.handlers.keydown({code:'ControlLeft',target:document.body,ctrlKey:true,repeat:false,preventDefault(){}});
assert.equal(game.getInput().keys,0,'Ctrl shortcut releases previously held movement');
document.handlers.keydown({code:'Space',target:document.body,repeat:false,preventDefault(){}});
assert.equal(game.getInput().keys,1);
document.handlers.compositionstart();
assert.equal(game.getInput().keys,0,'IME start releases previously held firing');
document.handlers.keydown({code:'ArrowLeft',target:document.body,repeat:false,preventDefault(){}});assert.equal(game.getInput().keys,1);
document.hidden=true;document.handlers.visibilitychange();assert.equal(game.getState().state,'paused');assert.equal(game.getInput().touchActive,false,'background tab releases ship pointer');assert.equal(game.getInput().held.left,false,'background tab releases directional owner');assert.equal(game.getInput().keys,0,'hidden tab releases keyboard input');assert.equal(Object.values(game.getInput().held).some(Boolean),false);document.hidden=false;game.pause();assert.equal(game.getState().state,'playing');
game.pause();assert.equal(game.getState().state,'paused');game.start();frame(2980);assert.ok(Math.abs(game.getState().simulationTime-.1)<1e-6,'100 ms hitch advances simulation consistently');game.spawnBoss();const beforeBossContact=game.getState().enemies;game.testBossContact();assert.equal(game.getState().enemies,beforeBossContact,'boss must survive contact');game.advanceWave();game.advanceWave();assert.equal(game.getState().state,'playing','waves must not force shop interruption');game.start();for(let i=0;i<8;i++)game.spawnEnemy();assert.doesNotThrow(()=>game.useEMP(),'EMP finishing a wave must tolerate cleared enemy arrays');assert.equal(game.getState().wave,2);
(async()=>{game.openFleet();await game.refreshFleet();assert.equal(elements.fleetStatus.textContent.includes('unavailable'),true);assert.equal(game.getFleet().filter(j=>j.owned).length,1);game.earn(1000);
// Card click selects preview; local free purchase debits once.
elements.fleetGrid.children[1].onclick();assert.equal(game.equipJet(),true);const credits=game.getState().bank;assert.equal(game.equipJet(),true);assert.equal(game.getState().bank,credits);assert.equal(game.getState().activeJet,'raptor');
elements.fleetGrid.children[3].onclick();assert.equal(game.equipJet(),false);game.trialFlight();assert.equal(game.getState().activeJet,'spectre');assert.equal(game.getState().trialJet,true);assert.equal(game.getState().hp,100);assert.equal(game.getFleet().find(j=>j.id==='spectre').owned,false);game.gameOver();game.start();assert.equal(game.getState().activeJet,'raptor');
fetchMode='verified';game.openFleet();await game.refreshFleet();assert.equal(game.getFleet().find(j=>j.id==='spectre').owned,true);elements.fleetGrid.children[3].onclick();assert.equal(game.equipJet(),true);assert.equal(game.getState().activeJet,'spectre');fetchMode='checkout';await game.refreshFleet();elements.fleetGrid.children[3].onclick();assert.equal(elements.jetEquip.disabled,true,'unowned premium MOJ1 jet cannot initiate checkout');const beforeRedirect=sandbox.location.href;assert.equal(game.equipJet(),false);assert.equal(sandbox.location.href,beforeRedirect,'legacy USD checkout must never open');assert.match(elements.fleetStatus.textContent,/MOJ1 checkout/);fetchMode='offline';await game.refreshFleet();assert.equal(game.getState().selectedJet,'falcon');assert.equal(game.getFleet().find(j=>j.id==='spectre').owned,false);game.start();for(let i=181;i<=220;i++)frame(i*16);console.log('PASS Air Supremacy: 100 lives, bitmap/fallback rendering, boss contact, uninterrupted waves, pause, free unlock/debit, premium forgery rejection, trial isolation, server restore, offline revocation');})().catch(e=>{console.error(e);process.exitCode=1});
