import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const src=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
function extract(begin,end){const i=src.indexOf(begin),j=src.indexOf(end,i);assert.ok(i>=0&&j>i);return src.slice(i,j)}
const saveSource=extract('let saveWarningShown=false,saveStatus=', '\nfunction updatePauseSaveStatus');
function saveHarness({durable=true}={}){
 const values=new Map(),warnings=[];
 const ctx={screen:'game',world:{mission:1,endless:false,score:99,pickups:[]},saveKey:'rwNativeCampaign',
  campaignSaveDisposition:()=> 'write',boundedCampaignPickups:a=>a,
  storageWrite:(key,value)=>{if(durable)values.set(key,value);return true},
  storageRead:key=>values.get(key)??null,toast:message=>warnings.push(message)};
 vm.runInNewContext(saveSource+'\nglobalThis.performSave=save;globalThis.getSaveStatus=()=>saveStatus;',ctx);
 return {ctx,warnings,save:()=>ctx.performSave()};
}
test('save refuses success if a storage shim silently discards writes',()=>{
 const h=saveHarness({durable:false});assert.equal(h.save(),false);
 assert.equal(h.ctx.getSaveStatus(),'failed');assert.equal(h.warnings.length,1);
});
test('save confirms exact snapshot readback',()=>{
 const h=saveHarness();assert.equal(h.save(),true);
 assert.equal(h.ctx.getSaveStatus(),'saved');assert.equal(h.warnings.length,0);
});
const captureSource=extract('function safeReleaseCapture(',"addEventListener('keydown',e=>{");
test('pause releases three captured pointers and clears held input',()=>{
 const released=[];
 const fire={hasPointerCapture:id=>id===2,releasePointerCapture:id=>released.push(['fire',id])};
 const stick={hasPointerCapture:id=>id===3,releasePointerCapture:id=>released.push(['stick',id])};
 const canvas={hasPointerCapture:id=>id===4,releasePointerCapture:id=>released.push(['canvas',id])};
 const ctx={fireId:2,joyId:3,aimId:4,keys:{Space:true},fireHeld:true,joyF:1,joyS:1,aimGesture:{},knob:{style:{transform:'move'}},stick,canvas,$:()=>fire};
 vm.runInNewContext(captureSource+'\nglobalThis.releaseAll=releaseGameInputs;',ctx);
 ctx.releaseAll();
 assert.deepEqual(released,[['fire',2],['stick',3],['canvas',4]]);
 assert.equal(ctx.fireId,null);assert.equal(ctx.joyId,null);assert.equal(ctx.aimId,null);
 assert.equal(ctx.fireHeld,false);assert.equal(ctx.joyF,0);assert.equal(ctx.joyS,0);
});
