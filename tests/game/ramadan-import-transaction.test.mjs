import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
const start=source.indexOf("$('#importSaveFile').onchange=async e=>{");
const end=source.indexOf("};$('#survival').onclick",start);
assert.ok(start>=0&&end>start,'production import handler exists');
const handler=source.slice(start+"$('#importSaveFile').onchange=".length,end+1);
async function run({old='OLD_SAVE',activate=true,writeOk=true,removeOk=true,foreign=false,baseline=undefined}={}){
 const state=new Map(old===null?[]:[['rwNativeCampaign',old]]),messages=[];
 const ctx={saveKey:'rwNativeCampaign',saveStatus:'not-saved',hero:2,foreignSaveDetected:foreign,lastSavedSnapshot:baseline,
  MAX_CAMPAIGN_BACKUP_BYTES:512*1024,
  readCampaignBackup:()=> 'NEW_SAVE',
  storageRead:k=>state.has(k)?state.get(k):null,
  storageWrite:(k,v)=>{if(!writeOk)return false;state.set(k,v);return true},
  storageRemove:k=>{if(!removeOk)return false;state.delete(k);return true},
  hasResumableCampaignInMemory:()=>false,
  confirm:()=>true,restore:()=>activate,
  toast:m=>messages.push(m),updateHome:()=>{},
  $:()=>({textContent:''})
 };
 vm.runInNewContext('globalThis.importHandler='+handler+';',ctx);
 const input={files:[{size:100,text:async()=>'{"backup":true}'}],value:'selected'};
 await ctx.importHandler({currentTarget:input});
 return {ctx,state,messages,input};
}
test('failed runtime activation restores the previous disk save',async()=>{
 const r=await run({activate:false});
 assert.equal(r.state.get('rwNativeCampaign'),'OLD_SAVE');
 assert.match(r.messages.at(-1),/قبلی محفوظ/);
});
test('failed activation removes newly written save when none existed',async()=>{
 const r=await run({old:null,activate:false});
 assert.equal(r.state.has('rwNativeCampaign'),false);
});
test('successful activation commits imported campaign',async()=>{
 const r=await run({activate:true});
 assert.equal(r.state.get('rwNativeCampaign'),'NEW_SAVE');
 assert.equal(r.ctx.saveStatus,'saved');
});
test('failed browser write leaves previous save intact',async()=>{
 const r=await run({writeOk:false});
 assert.equal(r.state.get('rwNativeCampaign'),'OLD_SAVE');
});

test('import refuses stale-tab overwrite and preserves newer campaign',async()=>{
 const r=await run({old:'NEWER_OTHER_TAB',baseline:'OLD_BASELINE'});
 assert.equal(r.state.get('rwNativeCampaign'),'NEWER_OTHER_TAB');
 assert.match(r.messages.at(-1),/برگهٔ دیگری/);
});
