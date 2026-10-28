import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import vm from 'node:vm';
import {campaignSaveDisposition} from '../../games/ramadan-war/save-validation.mjs';

const root=dirname(fileURLToPath(import.meta.url));
const game=readFileSync(resolve(root,'../../games/ramadan-war/game.js'),'utf8');

test('survival mode never clears the saved campaign on start, pause, or pagehide',()=>{
 assert.equal(campaignSaveDisposition({mission:6,endless:true,gameOver:false,victory:false}),'keep');
 assert.equal(campaignSaveDisposition({mission:0,endless:true,gameOver:false,victory:false}),'keep');
 assert.equal(campaignSaveDisposition({mission:2,endless:false,gameOver:false,victory:false}),'write');
 assert.equal(campaignSaveDisposition({mission:5,endless:false,gameOver:true,victory:false}),'remove');
 assert.equal(campaignSaveDisposition({mission:5,endless:false,gameOver:false,victory:true}),'remove');
 assert.equal(campaignSaveDisposition(null),'keep');
});

test('accepted gunshots persist earned points and consumed ammo without waiting five seconds',()=>{
 const start=game.indexOf('function fire(){');
 const end=game.indexOf('\nfunction launchRocket()',start);
 assert.ok(start>0 && end>start,'fire implementation must exist');
 const src=game.slice(start,end);
 let saved=0;
 const world={ammo:8,magazine:8,hero:0,shots:0,shotTimer:0,muzzle:0,recoil:0,
  combo:0,comboTimer:0,score:0,points:0,power:0,missionPassed:false,impacts:[],x:2.5,y:7.5};
 const target={x:3.5,y:7.5,hp:100};
 const ctx={screen:'game',world,visibleAttack:()=>target,engine:{pitch:()=>0},
  document:{querySelector:()=>({classList:{remove(){},add(){}}})},
  clearTimeout(){},setTimeout(){return 1},hitTimer:0,
  toast(){},playTone(){},sync(){},reload(){},save(){saved++}};
 vm.runInNewContext(src+'\nfire();',ctx);
 assert.equal(saved,1,'one durable checkpoint per accepted shot');
 assert.equal(world.ammo,7);
 assert.equal(world.shots,1);
 assert.ok(world.score>0 && world.points>0);
 assert.ok(target.hp<100);
 vm.runInNewContext('fire();',ctx);
 assert.equal(saved,1,'cooldown-rejected input must not write or spend ammo');
});


test('actual save() wiring leaves an existing campaign slot untouched in endless mode',()=>{
 const start=game.indexOf('let saveWarningShown=false;function save(){');
 const end=game.indexOf('\nfunction restore()',start);
 assert.ok(start>0 && end>start,'save implementation must exist');
 const source=game.slice(start,end);
 const calls=[];
 const context={world:{mission:6,endless:true,victory:false,gameOver:false,pickups:[]},
  campaignSaveDisposition,saveKey:'rwNativeCampaign',
  boundedCampaignPickups:()=>[],storageWrite:(key,val)=>{calls.push(['write',key,val]);return true},
  storageRemove:key=>{calls.push(['remove',key]);return true},toast(){}};
 vm.runInNewContext(source+'\nsave();',context);
 assert.equal(calls.length,0,'survival must not touch the campaign slot');
 context.world={mission:1,endless:false,victory:false,gameOver:false,pickups:[]};
 vm.runInNewContext('save();',context);
 assert.equal(calls.length,1);
 assert.equal(calls[0][0],'write');
 context.world.gameOver=true;
 vm.runInNewContext('save();',context);
 assert.equal(calls.length,2);
 assert.equal(calls[1][0],'remove');
});
