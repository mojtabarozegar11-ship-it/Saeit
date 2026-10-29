import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
const start=source.indexOf('let saveWarningShown=false,saveStatus=');
const end=source.indexOf('\nfunction updatePauseSaveStatus',start);
assert.ok(start>=0&&end>start);
const snippet=source.slice(start,end);
function harness(){
 const values=new Map([['rwNativeCampaign','initial']]),messages=[];
 const ctx={screen:'game',world:{mission:2,endless:false,pickups:[],score:22},saveKey:'rwNativeCampaign',
 campaignSaveDisposition:()=> 'write',boundedCampaignPickups:v=>v,
 storageRead:key=>values.get(key)??null,storageWrite:(key,value)=>{values.set(key,value);return true},
 storageRemove:key=>{values.delete(key);return true},toast:msg=>messages.push(msg)};
 vm.runInNewContext(snippet+'\nglobalThis.runSave=save;globalThis.readStatus=()=>saveStatus;',ctx);
 return {ctx,values,messages};
}
test('lost storage event cannot overwrite a newer tab snapshot',()=>{
 const h=harness();assert.equal(h.ctx.runSave(),true);
 h.values.set('rwNativeCampaign','newer-other-tab');
 assert.equal(h.ctx.runSave(),false);
 assert.equal(h.values.get('rwNativeCampaign'),'newer-other-tab');
 assert.equal(h.ctx.readStatus(),'failed');
 assert.equal(h.messages.length,1);
});
test('localStorage.clear invalidates a previously saved campaign',()=>{
 const h=harness();assert.equal(h.ctx.runSave(),true);
 h.values.delete('rwNativeCampaign');
 assert.equal(h.ctx.observeExternalCampaignSave({key:null,newValue:null}),true);
 assert.equal(h.ctx.runSave(),false);
 assert.equal(h.values.has('rwNativeCampaign'),false);
});
test('unchanged snapshot still permits saves',()=>{
 const h=harness();assert.equal(h.ctx.runSave(),true);
 assert.equal(h.ctx.runSave(),true);
 assert.equal(h.ctx.readStatus(),'saved');
});
test('clear before first snapshot does not falsely block campaign',()=>{
 const h=harness();assert.equal(h.ctx.observeExternalCampaignSave({key:null,newValue:null}),false);
 assert.equal(h.ctx.runSave(),true);
});
