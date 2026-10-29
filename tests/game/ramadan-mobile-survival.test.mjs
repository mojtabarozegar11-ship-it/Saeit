import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const game=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../../games/ramadan-war/index.html',import.meta.url),'utf8');
const css=readFileSync(new URL('../../games/ramadan-war/game.css',import.meta.url),'utf8');
function sourceBetween(a,b){const start=game.indexOf(a),end=game.indexOf(b,start);assert(start>=0&&end>start);return game.slice(start,end)}
test('survival wave counter starts at one and persists independently of campaign slot',()=>{
 const src=sourceBetween('const survivalWave=',"let soundEnabled=");
 const state={rwSurvivalBest:'8',rwNativeCampaign:'untouched'};
 const context={storageRead:key=>state[key]??null,storageWrite:(key,value)=>{state[key]=value;return true},world:{endless:true,mission:6}};
 const api=vm.runInNewContext(src+'\n({survivalWave,readSurvivalBest,recordSurvivalBest})',context);
 assert.equal(api.survivalWave(6),1);assert.equal(api.survivalWave(9),4);
 assert.equal(api.readSurvivalBest(),8);
 api.recordSurvivalBest();assert.equal(state.rwSurvivalBest,'8');
 context.world.mission=14;api.recordSurvivalBest();assert.equal(state.rwSurvivalBest,'9');
 assert.equal(state.rwNativeCampaign,'untouched');
 for(const invalid of ['Infinity','-1','999999','0','1e9','1.1']){state.rwSurvivalBest=invalid;assert.equal(api.readSurvivalBest(),0,invalid)}
});
test('manual reload persists immediately and rejects duplicate reload',()=>{
 const src=sourceBetween('function reload(manual=false){','\nfunction fire(){');
 let saves=0,syncs=0;
 const ctx={screen:'game',world:{ammo:3,magazine:8,reloadTimer:0},playTone(){},sync(){syncs++},save(){saves++}};
 vm.runInNewContext(src+'\nreload(true)',ctx);
 assert.equal(ctx.world.reloading,true);assert.equal(ctx.world.reloadTimer,1.05);
 assert.equal(saves,1);assert.equal(syncs,1);
 assert.equal(vm.runInNewContext('reload(true)',ctx),false);
 assert.equal(saves,1);
});
test('pause export, mobile reload and reduced motion controls are present',()=>{
 for(const id of ['reload','exportPauseSave','survivalRecord'])assert(html.includes('id="'+id+'"'));
 assert(game.includes("$('#exportPauseSave').onclick=exportCampaignBackup"));
 assert(game.includes("$('#reload').onclick=()=>reload(true)"));
 assert(css.includes('@media (prefers-reduced-motion: reduce)'));
 assert(css.includes('#game.firing #weaponArt { animation: none !important; }'));
});
test('boss status reports armor percentage rather than a static search prompt',()=>{
 const src=sourceBetween('function objectiveInfo(){','\nfunction interactObjective(){');
 const context={world:{endless:false,mission:5,missionKills:3,objective:{bossDefeated:false},enemies:[{boss:true,hp:205,max:410}]},fa:n=>String(Math.floor(n)),plan:()=>({kind:'boss',quota:8,sites:[]})};
 const result=vm.runInNewContext(src+'\nobjectiveInfo()',context);
 assert(result[1].includes('50٪'),result[1]);
});
