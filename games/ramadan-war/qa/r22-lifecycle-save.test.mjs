import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const a=source.indexOf('let saveWarningShown=false,saveStatus=');
const z=source.indexOf('\nfunction updatePauseSaveStatus',a);
assert.ok(a>=0&&z>a);
function harness(blocked=false,endless=false){
 const values=new Map(), ctx={screen:'game',world:{mission:2,endless,pickups:[],score:22},
 saveKey:'rwNativeCampaign',document:{visibilityState:'visible'},
 campaignSaveDisposition:w=>w.endless?'keep':'write',boundedCampaignPickups:v=>v,
 storageRead:k=>values.get(k)??null,
 storageWrite:(k,v)=>{if(blocked)return false;values.set(k,v);return true},
 storageRemove:k=>{values.delete(k);return true},toast:()=>{}};
 vm.runInNewContext(source.slice(a,z)+'\nglobalThis.runSave=save;',ctx);
 return {ctx,values};
}
function event(){return {prevented:false,preventDefault(){this.prevented=true},returnValue:undefined}}
test('tab exit flushes unsaved gameplay',()=>{
 const h=harness();h.ctx.runSave();h.ctx.world.score=301;
 const e=event();h.ctx.warnUnsavedCampaignBeforeExit(e);
 assert.equal(JSON.parse(h.values.get('rwNativeCampaign')).score,301);
 assert.equal(e.prevented,false);
});
test('blocked storage warns on exit',()=>{
 const h=harness(true),e=event();h.ctx.warnUnsavedCampaignBeforeExit(e);
 assert.equal(e.prevented,true);
});
test('other-tab conflict never overwrites newer save',()=>{
 const h=harness();h.ctx.runSave();h.values.set('rwNativeCampaign','newer-other-tab');
 const e=event();h.ctx.warnUnsavedCampaignBeforeExit(e);
 assert.equal(h.values.get('rwNativeCampaign'),'newer-other-tab');assert.equal(e.prevented,true);
});
test('mobile hidden state flushes; visible state does not',()=>{
 const h=harness();h.ctx.saveCampaignOnHidden();assert.equal(h.values.size,0);
 h.ctx.document.visibilityState='hidden';h.ctx.saveCampaignOnHidden();
 assert.equal(JSON.parse(h.values.get('rwNativeCampaign')).score,22);
 h.ctx.world.score=44;h.ctx.document.visibilityState='visible';h.ctx.saveCampaignOnHidden();
 assert.equal(JSON.parse(h.values.get('rwNativeCampaign')).score,22);
});
test('survival mode cannot replace campaign',()=>{
 const h=harness(false,true);h.values.set('rwNativeCampaign','existing');
 h.ctx.document.visibilityState='hidden';h.ctx.saveCampaignOnHidden();
 h.ctx.warnUnsavedCampaignBeforeExit(event());
 assert.equal(h.values.get('rwNativeCampaign'),'existing');
});
test('lifecycle handlers registered',()=>{
 assert.match(source,/addEventListener\('visibilitychange',saveCampaignOnHidden\)/);
 assert.match(source,/addEventListener\('beforeunload',warnUnsavedCampaignBeforeExit\)/);
});
