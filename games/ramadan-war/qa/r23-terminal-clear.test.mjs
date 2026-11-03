import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const src=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const start=src.indexOf('let saveWarningShown=false,saveStatus=');
const end=src.indexOf('\nfunction updatePauseSaveStatus',start);
assert.ok(start>=0&&end>start);
const snippet=src.slice(start,end);
function harness({removeAllowed=true}={}){
 const values=new Map([['rwNativeCampaign','old-valid-save']]),toasts=[];
 const ctx={screen:'victory',world:{victory:true,endless:false,gameOver:false,mission:5,pickups:[]},saveKey:'rwNativeCampaign',
  campaignSaveDisposition:w=>w.victory||w.gameOver?'remove':'write',boundedCampaignPickups:v=>v,
  storageRead:k=>values.get(k)??null,storageRemove:k=>{if(!removeAllowed)return false;values.delete(k);return true},
  storageWrite:(k,v)=>{values.set(k,v);return true},toast:m=>toasts.push(m)};
 vm.runInNewContext(snippet+'\nglobalThis.doSave=save;globalThis.status=()=>saveStatus;globalThis.baseline=()=>lastSavedSnapshot;globalThis.setBaseline=v=>{lastSavedSnapshot=v};',ctx);
 return {ctx,values,toasts};
}
test('terminal removal checks durable readback before reporting success',()=>{
 const a=harness({removeAllowed:false});assert.equal(a.ctx.doSave(),false);assert.equal(a.ctx.status(),'failed');assert.equal(a.values.get('rwNativeCampaign'),'old-valid-save');
});
test('terminal removal resets baseline so a new campaign can save',()=>{
 const a=harness();assert.equal(a.ctx.doSave(),true);assert.equal(a.ctx.baseline(),null);assert.equal(a.values.has('rwNativeCampaign'),false);
 a.ctx.world={victory:false,gameOver:false,endless:false,mission:0,pickups:[],score:0};a.ctx.screen='game';assert.equal(a.ctx.doSave(),true);assert.equal(JSON.parse(a.values.get('rwNativeCampaign')).score,0);
});
test('terminal clear refuses to delete an externally replaced campaign',()=>{
 const a=harness();a.ctx.setBaseline('old-valid-save');a.values.set('rwNativeCampaign','newer-from-another-tab');
 assert.equal(a.ctx.doSave(),false);assert.equal(a.values.get('rwNativeCampaign'),'newer-from-another-tab');
});
test('terminal result offers retry rather than preemptive deletion',()=>{
 assert.match(html,/id="resultRetryClear"/);
 assert.match(src,/\$\('#resultRetryClear'\)\.onclick=/);
 assert.doesNotMatch(src,/world\.victory=true;storageRemove\(saveKey\);showResult/);
});
