import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const game=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
const start=game.indexOf('function restore(){');
const end=game.indexOf('\nfunction showScreen(',start);
assert.ok(start>=0&&end>start,'production restore() found');
const restoreSource=game.slice(start,end);

function harness(previous,raw,options={}){
 const ctx={world:previous,screen:'home',saveKey:'rwNativeCampaign',hero:0,last:0,
  hasResumableCampaignInMemory:()=>!!(ctx.world&&!ctx.world.endless&&!ctx.world.victory&&!ctx.world.gameOver),
  storageRead:()=>raw,parseCampaignSave:()=>options.parsed??raw,
  validateCampaignSave:()=>options.valid??false,
  boundedCampaignPickups:a=>a||[],prepareObjective:()=>{},
  restoreRecoveryPickups:()=>0,reconcileBossEncounter:()=>{},
  restorePlayerPosition:()=>{},restoreEnemyPositions:()=>options.enemyResult??0,
  restoreEnemyRuntime:()=>{},tile:()=>0,
  OPERATIONS:Array.from({length:6},()=>({sites:[]})),
  engine:{build:()=>{if(options.throwBuild)throw Error('context lost')}},
  resumeCampaignScreen:()=> 'continue',showScreen:()=>{},
  performance:{now:()=>1},scheduleFrame:()=>{},toast:()=>{},showResult:()=>{}
 };
 vm.runInNewContext(restoreSource+'\nglobalThis.restoreCampaign=restore;',ctx);
 return {ctx,restore:()=>ctx.restoreCampaign()};
}

test('invalid disk save preserves valid unsaved in-memory campaign',()=>{
 const previous={mission:3,score:980,hero:2};const {ctx,restore}=harness(previous,'corrupt');
 assert.equal(restore(),false);assert.equal(ctx.world,previous);assert.equal(ctx.world.score,980);
});
test('no existing in-memory campaign stays null after invalid save',()=>{
 const {ctx,restore}=harness(null,'corrupt');assert.equal(restore(),false);assert.equal(ctx.world,null);
});
test('impossible enemy geometry rolls back to the in-memory checkpoint',()=>{
 const previous={mission:2,score:770};
 const disk={mission:1,hero:1,x:2.5,y:7.5,missionKills:0,pickups:[],enemies:[],hostile:[],missiles:[]};
 const {ctx,restore}=harness(previous,disk,{valid:true,enemyResult:-1});
 assert.equal(restore(),false);assert.equal(ctx.world,previous);
});
test('graphics restoration error preserves the previous playable campaign',()=>{
 const previous={mission:2,score:550};
 const disk={mission:1,hero:1,x:2.5,y:7.5,missionKills:0,pickups:[],enemies:[],hostile:[],missiles:[]};
 const {ctx,restore}=harness(previous,disk,{valid:true,throwBuild:true});
 assert.equal(restore(),false);assert.equal(ctx.world,previous);
});
test('valid disk save replaces the old in-memory checkpoint',()=>{
 const previous={mission:2,score:550};
 const disk={mission:1,hero:1,x:2.5,y:7.5,missionKills:0,pickups:[],enemies:[],hostile:[],missiles:[]};
 const {ctx,restore}=harness(previous,disk,{valid:true});
 assert.equal(restore(),true);assert.equal(ctx.world.mission,1);assert.equal(ctx.world.hero,1);
});
test('start button offers memory recovery if disk restore fails',()=>{
 assert.match(game,/if\(!restore\(\)\)\{if\(hasResumableCampaignInMemory\(\)&&resumeInMemoryCampaign\(\)\)/);
});
