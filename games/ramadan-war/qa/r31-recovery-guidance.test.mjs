import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {closestReachableObjective,objectiveApproachWaypoint} from '../objective-navigation.mjs';
const source=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const pass=(x,y)=>x>=1&&x<=5&&y>=1&&y<=5&&x!==3;
test('recovery objective does not invent an unreachable fallback',()=>{
 assert.equal(closestReachableObjective(1.5,2.5,[[5.5,2.5]],pass,7),null);
 assert.deepEqual(closestReachableObjective(1.5,2.5,[[5.5,2.5],[2.5,4.5]],pass,7),[2.5,4.5]);
 assert.doesNotMatch(source,/closestReachableObjective\(world\.x,world\.y,intel[^\n]*\|\|intel\[0\]/);
});
test('recovery HUD distinguishes blocked path from missing package',()=>{
 assert.match(source,/world\.pickups\.some\(item=>item\.type==='mission-intel'\)/);
 assert.match(source,/مسیر بسته است؛ از مسیر دیگری نزدیک شوید/);
});
test('approach routing is deterministic and never crosses an impassable barrier',()=>{
 const route=objectiveApproachWaypoint(1.5,2.5,5.5,2.5,pass,1.35,7);
 assert.equal(route,null);
 const all=(x,y)=>x>=1&&x<=5&&y>=1&&y<=5&&!(x===3&&y===3);
 const candidate=objectiveApproachWaypoint(1.5,3.5,3.5,3.5,all,1.35,7);
 assert.ok(candidate&&candidate.steps>=0);
 assert.ok(Math.hypot(candidate.x-3.5,candidate.y-3.5)<=1.35);
});
