import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {restorePlayerPosition} from '../save-validation.mjs';
import {playerSpaceClear} from '../input-guard.mjs';
const wall=(x,y)=>x<0||y<0||x>=16||y>=16||x===0||y===0||x===15||y===15||(x===3&&y===2);
const clear=(x,y)=>playerSpaceClear(x,y,wall);
test('R48: radius-clipped legacy checkpoint recovers to a clear spawn',()=>{
 const state={x:2.86,y:2.5,score:710,points:3,mission:2};
 assert.equal(wall(2,2),false,'the centre tile was always passable');
 assert.equal(clear(state.x,state.y),false,'the radius overlaps the adjacent wall');
 assert.equal(restorePlayerPosition(state,wall,clear),true);
 assert.equal(clear(state.x,state.y),true);
 assert.deepEqual([state.x,state.y],[2.5,7.5]);
 assert.equal(state.score,710);assert.equal(state.points,3);
});
test('R48: a genuinely clear checkpoint preserves exact coordinates',()=>{
 const state={x:2.78,y:2.5};
 assert.equal(restorePlayerPosition(state,wall,clear),false);
 assert.deepEqual(state,{x:2.78,y:2.5});
});
test('R48: unsafe fallback refuses to modify progress',()=>{
 const state={x:2.86,y:2.5,score:900};
 const allBlocked=(x,y)=>wall(x,y)||(x===2&&y===7);
 const clearance=(x,y)=>playerSpaceClear(x,y,allBlocked);
 assert.equal(restorePlayerPosition(state,allBlocked,clearance),null);
 assert.deepEqual(state,{x:2.86,y:2.5,score:900});
});
test('R48: malformed checkpoint fails closed',()=>{
 assert.equal(restorePlayerPosition(null,wall,clear),null);
 assert.equal(restorePlayerPosition({x:NaN,y:Infinity},wall,()=>false),null);
});
test('R48: production restore checks radius and aborts if recovery is impossible',()=>{
 const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
 assert.match(game,/restorePlayerPosition\(world,\(x,y\)=>tile\(x,y,world\.mission\)!==0,\(x,y\)=>playerSpaceClear/);
 assert.match(game,/===null\)\{world=previousWorld;hero=previousHero;saveStatus='failed';return false;/);
});
