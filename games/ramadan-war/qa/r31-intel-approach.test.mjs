import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {closestReachableObjective,objectiveApproachWaypoint} from '../objective-navigation.mjs';
const src=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const pass=(x,y)=>x>=1&&x<=5&&y>=1&&y<=5&&!(x===3&&y===3);
test('recovery pickup in blocked cell has a walkable pickup-radius approach',()=>{
 const route=objectiveApproachWaypoint(2.5,3.5,3.5,3.5,pass,.78,7);
 assert.ok(route);assert.ok(Math.hypot(route.x-3.5,route.y-3.5)<.78);
 assert.equal(Math.floor(route.x),2);
 assert.deepEqual(closestReachableObjective(2.5,3.5,[[3.5,3.5]],pass,7,.78),[3.5,3.5]);
});
test('sealed barrier never manufactures pickup route',()=>{
 const sealed=(x,y)=>pass(x,y)&&x!==2;
 assert.equal(closestReachableObjective(1.5,3.5,[[3.5,3.5]],sealed,7,.78),null);
});
test('pickup too far from walkable cells remains blocked',()=>{
 const isolated=(x,y)=>x===1&&y===1;
 assert.equal(objectiveApproachWaypoint(1.5,1.5,3.5,3.5,isolated,.78,7),null);
});
test('equal route length chooses closer pickup',()=>{
 const open=(x,y)=>x>=1&&x<=5&&y>=1&&y<=5;
 assert.deepEqual(closestReachableObjective(1.5,1.5,[[2.8,1.5],[2.1,1.5]],open,7,.78),[2.1,1.5]);
});
test('invalid pickup radii fail closed',()=>{
 assert.equal(objectiveApproachWaypoint(1.5,1.5,2,2,pass,-1,7),null);
 assert.equal(closestReachableObjective(1.5,1.5,[[2,2]],pass,7,NaN),null);
});
test('runtime passes actual recovery pickup radius',()=>{
 assert.match(src,/closestReachableObjective\(world\.x,world\.y,intel,[^\n]+,16,\.78\)/);
});
