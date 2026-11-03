import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {closestReachableObjective,objectiveApproachWaypoint,objectiveWaypoint} from '../objective-navigation.mjs';
const source=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const free=(x,y)=>x>=1&&x<=5&&y>=1&&y<=5;
test('recovery selects shortest reachable intel route',()=>{
 assert.deepEqual(closestReachableObjective(1.5,1.5,[[5.5,5.5],[2.5,1.5],[4.5,1.5]],free,7),[2.5,1.5]);
});
test('recovery skips unreachable intel',()=>{
 const pass=(x,y)=>free(x,y)&&x!==3;
 assert.deepEqual(closestReachableObjective(1.5,1.5,[[4.5,1.5],[2.5,2.5]],pass,7),[2.5,2.5]);
 assert.equal(closestReachableObjective(1.5,1.5,[[4.5,1.5]],pass,7),null);
});
test('approach guides to a traversable cell, not through a blocked target',()=>{
 const pass=(x,y)=>free(x,y)&&!(x===3&&y===3);
 assert.equal(objectiveWaypoint(1.5,3.5,3.5,3.5,pass,7),null);
 const route=objectiveApproachWaypoint(1.5,3.5,3.5,3.5,pass,1.35,7);
 assert.ok(route);assert.ok(route.steps>0);
 assert.ok(Math.hypot(route.x-3.5,route.y-3.5)<=1.35);
});
test('approach never invents a route across a sealed wall',()=>{
 const pass=(x,y)=>free(x,y)&&x!==3;
 assert.equal(objectiveApproachWaypoint(1.5,2.5,5.5,2.5,pass,1.35,7),null);
});
test('malformed targets fail closed',()=>{
 assert.equal(closestReachableObjective(1,1,[[NaN,2]],free,7),null);
 assert.equal(closestReachableObjective(1,1,new Array(65).fill([2,2]),free,7),null);
 assert.equal(objectiveApproachWaypoint(1,1,3,3,free,NaN,7),null);
});
test('runtime wires nearest-intel and safe approach fallback',()=>{
 assert.match(source,/closestReachableObjective\(world\.x,world\.y,intel/);
 assert.match(source,/objectiveApproachWaypoint\(world\.x,world\.y,site\[0\]/);
});