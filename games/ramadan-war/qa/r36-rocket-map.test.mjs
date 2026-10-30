import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {chooseNearestTarget} from '../target-selection.mjs';
import {keyboardAction} from '../input-guard.mjs';
const e=(x,y,hp=50)=>({x,y,hp});
test('R36 missile auto-target refuses blocked nearest and selects visible next',()=>{
 const blocked=(x,y,tx,ty)=>tx<4;
 assert.deepEqual(chooseNearestTarget([e(2,2),e(7,2)],0,2,13,true,blocked),e(7,2));
});
test('R36 missile never spends on only occluded targets',()=>{
 assert.equal(chooseNearestTarget([e(2,2)],0,2,13,true,()=>true),null);
});
test('R36 drone nearest remains available when LOS is intentionally not required',()=>{
 assert.deepEqual(chooseNearestTarget([e(2,2)],0,2,13,false,()=>true),e(2,2));
});
test('R36 dead, invalid and out-of-range enemies are ignored',()=>{
 assert.equal(chooseNearestTarget([e(1,1,0),e(NaN,2),e(20,20)],0,0,13,true,()=>false),null);
});
test('R36 M toggles radar only in game, not when focused on interactive controls or repeating',()=>{
 assert.equal(keyboardAction('KeyM','game',null,false),'map');
 assert.equal(keyboardAction('KeyM','game',{closest:()=>true},false),null);
 assert.equal(keyboardAction('KeyM','home',null,false),null);
 assert.equal(keyboardAction('KeyM','game',null,true),null);
});
test('R36 map action and target selection are wired to actual gameplay',()=>{
 const js=readFileSync(new URL('../game.js',import.meta.url),'utf8');
 const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
 assert.match(js,/chooseNearestTarget\(world\.enemies/);
 assert.match(js,/targetAim\(13\)\|\|nearest\(13,true\)/);
 assert.match(js,/if\(action==='map'\)/);
 assert.match(html,/aria-keyshortcuts="M"/);
});


test('R37 invalid player coordinates fail closed without consuming a target',()=>{
 assert.equal(chooseNearestTarget([e(2,2)],Infinity,2,13,true,()=>false),null);
 assert.equal(chooseNearestTarget([e(2,2)],0,NaN,13,true,()=>false),null);
});
test('R37 browser QA isolates auto-spawned enemies and handles point-blank rockets',()=>{
 const js=readFileSync(new URL('../game.js',import.meta.url),'utf8');
 assert.match(js,/replaceTestEnemy:\(\)=>/);
 assert.match(js,/world\.enemies=\[e\];world\.missiles=\[\];world\.enemyTimer=30/);
 assert.match(js,/if\(d<\.55\)\{explode\(target\.x,target\.y,145\)/);
});
