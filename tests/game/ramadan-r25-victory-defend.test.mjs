import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const src=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
function fragment(begin,end){const i=src.indexOf(begin),j=src.indexOf(end,i);assert.ok(i>=0&&j>i);return src.slice(i,j)}
const progress=fragment('function objectiveInfo(){','function interactObjective(){');
function defendAt(x,y){const ctx={world:{endless:false,mission:1,objective:{hold:5,done:0},missionKills:2,x,y},fa:n=>String(n),plan:()=>({kind:'defend',title:'Defend',seconds:22,sites:[[8.5,7.5]],quota:5})};vm.runInNewContext(progress+';globalThis.info=objectiveInfo;',ctx);return ctx.info()[1]}
test('defense timer shows inside-zone status',()=>assert.match(defendAt(8.5,7.5),/در منطقه دفاع/));
test('defense timer explains frozen progress outside zone',()=>assert.match(defendAt(2.5,7.5),/زمان متوقف است/));
test('in-session victory unlocks survival without storage writes',()=>{
 assert.match(src,/if\(type==='victory'\)\{sessionWinUnlocked=true;storageWrite\('rwWin','1'\);\}/);
 assert.match(src,/\$\('#survival'\)\.classList\.toggle\('hidden',!sessionWinUnlocked&&storageRead\('rwWin'\)!=='1'\)/);
 const ctx={sessionWinUnlocked:true,storageRead:()=>null};
 assert.equal(vm.runInNewContext("!sessionWinUnlocked&&storageRead('rwWin')!=='1'",ctx),false);
});
