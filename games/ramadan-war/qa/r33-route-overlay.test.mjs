import test from 'node:test';
import assert from 'node:assert/strict';
import {findTacticalRoute,paintTacticalMap} from '../tactical-map.mjs';
const walls=new Set(['2,1','2,2','2,3']);
const blocked=(x,y)=>walls.has(String(x)+','+String(y));
test('R33 shortest route detours around walls without crossing any',()=>{
 const route=findTacticalRoute(1.5,2.5,4.5,2.5,blocked);
 assert.ok(route);assert.ok(route.steps>3);assert.deepEqual(route.path[0],{x:1.5,y:2.5});
 assert.deepEqual(route.path.at(-1),{x:4.5,y:2.5});
 for(const p of route.path)assert.equal(blocked(Math.floor(p.x),Math.floor(p.y)),false);
 for(let i=1;i<route.path.length;i++)assert.equal(Math.abs(route.path[i].x-route.path[i-1].x)+Math.abs(route.path[i].y-route.path[i-1].y),1);
});
test('R33 blocked target uses a reachable adjacent interaction tile',()=>{
 const route=findTacticalRoute(1.5,2.5,2.5,2.5,blocked);
 assert.equal(route?.approach,true);assert.ok(Math.hypot(route.path.at(-1).x-2.5,route.path.at(-1).y-2.5)<=1.35);
});
test('R33 fully enclosed target has no invented route',()=>{
 const wall=(x,y)=>x===0||y===0||x===15||y===15||(x===5&&y===4)||(x===4&&y===5)||(x===6&&y===5)||(x===5&&y===6);
 assert.equal(findTacticalRoute(2.5,2.5,5.5,5.5,wall),null);
});
test('R33 invalid, nonfinite and off-grid inputs fail closed',()=>{
 for(const input of [[NaN,2,3,4],[1,Infinity,3,4],[-1,2,3,4],[1,2,16,4]])assert.equal(findTacticalRoute(...input,()=>false),null);
 assert.equal(findTacticalRoute(1,1,2,2,()=>false,1000),null);
});
test('R33 radar paints a bounded real path, does not mutate state, and skips off-grid player',()=>{
 const calls=[];const ctx={clearRect(){},fillRect(){},beginPath(){},arc(){},fill(){},save(){},restore(){},translate(){calls.push('player')},rotate(){},moveTo(){},lineTo(){calls.push('segment')},closePath(){},stroke(){calls.push('stroke')}};
 const canvas={width:160,getContext:()=>ctx},state={x:1.5,y:2.5,angle:0,enemies:[]},before=JSON.stringify(state);
 assert.equal(paintTacticalMap(canvas,state,blocked,[4.5,2.5]),true);
 assert.ok(calls.includes('stroke'));assert.ok(calls.filter(x=>x==='segment').length>3);assert.equal(JSON.stringify(state),before);
 calls.length=0;assert.equal(paintTacticalMap(canvas,{x:16,y:2,angle:0,enemies:[]},blocked,[4.5,2.5]),true);
 assert.equal(calls.includes('player'),false);assert.equal(calls.includes('stroke'),false);
});
