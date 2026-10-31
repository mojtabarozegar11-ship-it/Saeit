import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const game=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../../games/ramadan-war/index.html',import.meta.url),'utf8');
function between(a,b){const i=game.indexOf(a),j=game.indexOf(b,i);assert(i>=0&&j>i,a+' missing');return game.slice(i,j)}

test('fatal projectile never becomes a mission victory in the same frame',()=>{
 const source=between('function hurt(amount){','\nfunction special(){')+'\n'+between('function tick(dt){','\nfunction prepareMission(){');
 const world={gameOver:false,victory:false,missionPassed:false,shield:0,hitFlash:0,armor:0,lives:1,hp:1,maxHp:100,x:2.5,y:7.5,hero:0,angle:0,mission:0,time:0,shotTimer:0,reloadTimer:0,ammo:8,magazine:8,comboTimer:0,combo:0,explosionTimer:0,rocketTimer:0,droneTimer:0,skillTimer:0,muzzle:0,recoil:0,impacts:[],enemyTimer:20,enemies:[],hostile:[{hp:5,life:2}],missiles:[],pickups:[],strikeTimer:0};
 const results=[];
 const ctx={world,screen:'game',keys:{},joyF:0,joyS:0,fireHeld:false,Math,
  advanceTimeStop:()=>false,resolveMovementAxes:()=>({forward:0,side:0}),move(){},updateObjective(){},required:()=>1,
  advanceHostileProjectile:()=>true,tile:()=>0,showResult:(title,description,type)=>{results.push(type);ctx.screen=type},
  toast(){},sync(){},save(){},canEnemyAct:()=>false,shouldCleanupEnemy:()=>false,missionObjectiveComplete:()=>true,
  removeEnemyAndRetargetMissiles(){},playTone(){},explode(){},prepareMission(){},recordSurvivalBest(){}};
 vm.runInNewContext(source+'\ntick(.04)',ctx);
 assert.equal(world.gameOver,true);
 assert.equal(world.hp,0);
 assert.deepEqual(results,['over']);
 assert.equal(world.missionPassed,false);
});

test('pause never falsely promises a successful save; retry can recover',()=>{
 const source=between('let saveWarningShown=false,saveStatus=', '\nfunction restore(){');
 let allowed=false,writes=0,lastSnapshot=null;const status={textContent:''},retry={hidden:true};const world={endless:false,pickups:[]};
 const resume={disabled:false};const ctx={screen:'game',world,graphicsUnavailable:false,saveKey:'rwNativeCampaign',storageWrite:(key,value)=>{writes++;if(allowed)lastSnapshot=value;return allowed},storageRead:()=>lastSnapshot,storageRemove:()=>true,
  campaignSaveDisposition:()=>world.endless?'keep':'write',boundedCampaignPickups:()=>[],toast(){},$:(id)=>id==='#pauseSaveStatus'?status:id==='#retrySave'?retry:id==='#resume'?resume:null};
 const api=vm.runInNewContext(source+'\n({save,updatePauseSaveStatus})',ctx);
 assert.equal(api.save(),false);api.updatePauseSaveStatus();assert.equal(retry.hidden,false);assert.match(status.textContent,/ذخیرهٔ خودکار انجام نشد/);
 allowed=true;assert.equal(api.save(),true);api.updatePauseSaveStatus();assert.equal(retry.hidden,true);assert.match(status.textContent,/ذخیره شد/);
 world.endless=true;assert.equal(api.save(),false);api.updatePauseSaveStatus();assert.equal(retry.hidden,true);assert.match(status.textContent,/حالت بقا/);assert.equal(writes,2);
 assert.match(html,/id="pauseSaveStatus"[^>]*aria-live="polite"/);
 assert.match(html,/id="retrySave"[^>]*hidden/);
});
