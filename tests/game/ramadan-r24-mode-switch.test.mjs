import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const src=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../../games/ramadan-war/index.html',import.meta.url),'utf8');
const start=src.indexOf('function updateHomeSaveStatus(){');
const end=src.indexOf('function updateHome(){',start);
assert.ok(start>=0&&end>start);
function harness({active=true,status='failed',foreign=false,stored=null,accepted=false}={}){
 const banner={hidden:true,textContent:''};let confirmations=0;
 const ctx={saveKey:'rwNativeCampaign',saveStatus:status,foreignSaveDetected:foreign,
  hasResumableCampaignInMemory:()=>active,storageRead:()=>stored,$:()=>banner,
  confirm:()=>{confirmations++;return accepted}};
 vm.runInNewContext(src.slice(start,end)+'\nglobalThis.show=updateHomeSaveStatus;globalThis.check=confirmCampaignReplacement',ctx);
 return {ctx,banner,get confirmations(){return confirmations}};
}
test('home exposes an accessible backup warning when storage fails',()=>{
 const h=harness();h.ctx.show();assert.equal(h.banner.hidden,false);
 assert.match(h.banner.textContent,/پشتیبان/);
 assert.match(html,/<p id="homeSaveStatus"[^>]*role="alert"/);
});
test('confirmed durable campaign does not show a false warning',()=>{
 const h=harness({status:'saved'});h.ctx.show();assert.equal(h.banner.hidden,true);
});
test('unsaved Survival switch is blocked on rejected confirmation',()=>{
 const h=harness();assert.equal(h.ctx.check('survival'),false);assert.equal(h.confirmations,1);
 assert.match(src,/\$\('#survival'\)\.onclick=\(\)=>\{if\(!confirmCampaignReplacement\('survival'\)\)return;newWorld\(true\)\}/);
});
test('safe saved Survival switch preserves original campaign without prompting',()=>{
 const h=harness({status:'saved',stored:'durable'});assert.equal(h.ctx.check('survival'),true);assert.equal(h.confirmations,0);
});
test('New Game and Retry refuse silent loss of an unsaved in-memory campaign',()=>{
 const h=harness();assert.equal(h.ctx.check('new'),false);assert.equal(h.ctx.check('retry'),false);assert.equal(h.confirmations,2);
 assert.match(src,/\$\('#retry'\)\.onclick=\(\)=>\{if\(!confirmCampaignReplacement\('retry'\)\)return;newWorld\(false\)\}/);
});
test('foreign tab conflict is always visible and protected',()=>{
 const h=harness({status:'saved',foreign:true,stored:'changed'});h.ctx.show();
 assert.equal(h.banner.hidden,false);assert.equal(h.ctx.check('survival'),false);
});
