import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {routeGuidance} from '../tactical-map.mjs';
const empty=()=>false;
test('R35 same walkable tile is not automatically arrival when target is far within tile',()=>{
 const hint=routeGuidance(1.01,1.01,0,1.99,1.99,empty);
 assert.equal(hint.status,'nearby');assert.equal(hint.steps,0);assert.match(hint.message,/نزدیک‌تر/);
});
test('R35 true proximity within same walkable tile still marks arrival',()=>{
 assert.equal(routeGuidance(1.5,1.5,0,1.9,1.9,empty).status,'arrived');
});
test('R35 solid objective same tile approach cannot falsely claim interaction range',()=>{
 const solid=(x,y)=>x===2&&y===2;
 const hint=routeGuidance(2.01,2.01,0,2.99,2.99,solid);
 assert.equal(hint.status,'blocked');
});
test('R35 adjacent solid goal with player far in same approach tile requires closing distance',()=>{
 const solid=(x,y)=>x===2&&y===2;
 const hint=routeGuidance(1.01,1.01,0,2.5,2.5,solid);
 assert.equal(hint.status,'reachable');
});
test('R35 extraction HUD has explicit quota gate instead of reporting interaction as ready',()=>{
 const src=readFileSync(new URL('../game.js',import.meta.url),'utf8');
 assert.match(src,/p\.kind==='extract'&&world\.missionKills<p\.quota&&canInteractAt\(/);
 assert.match(src,/ابتدا دشمنان باقی‌مانده را پاکسازی کن/);
});
