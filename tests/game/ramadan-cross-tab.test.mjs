import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const src=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
const start=src.indexOf("let saveWarningShown=false,saveStatus=");
const end=src.indexOf("\nfunction updatePauseSaveStatus",start);
assert.ok(start>=0&&end>start,'save/storage guard must exist');
const snippet=src.slice(start,end);
function harness(){
 const values=new Map([['rwNativeCampaign','old']]),messages=[];
 const ctx={screen:'game',world:{mission:2,endless:false,pickups:[],score:22},saveKey:'rwNativeCampaign',
  campaignSaveDisposition:()=> 'write',boundedCampaignPickups:v=>v,
  storageRead:key=>values.get(key)??null,storageWrite:(key,value)=>{values.set(key,value);return true},
  storageRemove:key=>values.delete(key),toast:msg=>messages.push(msg)};
 vm.runInNewContext(snippet+'\nglobalThis.runSave=save;globalThis.readStatus=()=>saveStatus;',ctx);
 return {ctx,values,messages};
}
test('foreign-tab update cannot be overwritten by local autosave',()=>{
 const h=harness();h.values.set('rwNativeCampaign','newer');
 assert.equal(h.ctx.observeExternalCampaignSave({key:'rwNativeCampaign',newValue:'newer'}),true);
 assert.equal(h.ctx.runSave(),false);
 assert.equal(h.values.get('rwNativeCampaign'),'newer');
 assert.equal(h.ctx.readStatus(),'failed');assert.equal(h.messages.length,1);
});
test('unrelated or same-value storage event does not block autosave',()=>{
 const h=harness();
 assert.equal(h.ctx.observeExternalCampaignSave({key:'other',newValue:'value'}),false);
 assert.equal(h.ctx.runSave(),true);
 const ownSave=h.values.get('rwNativeCampaign');
 assert.equal(h.ctx.observeExternalCampaignSave({key:'rwNativeCampaign',newValue:ownSave}),false);
});
test('active unsaved campaign warns before tab close',()=>{
 const h=harness();h.ctx.observeExternalCampaignSave({key:'rwNativeCampaign',newValue:'newer'});
 let prevented=false;const event={preventDefault(){prevented=true},returnValue:null};
 h.ctx.warnUnsavedCampaignBeforeExit(event);
 assert.equal(prevented,true);assert.equal(event.returnValue,'');
});
test('durably saved and survival campaigns do not warn',()=>{
 const h=harness();let prevented=false;const event={preventDefault(){prevented=true},returnValue:null};
 h.ctx.warnUnsavedCampaignBeforeExit(event);assert.equal(prevented,false);
 h.ctx.world.endless=true;h.ctx.observeExternalCampaignSave({key:'rwNativeCampaign',newValue:'newer'});
 h.ctx.warnUnsavedCampaignBeforeExit(event);assert.equal(prevented,false);
});
