import test from 'node:test';
import assert from 'node:assert/strict';
import {relativeDirection,paintTacticalMap} from '../tactical-map.mjs';
test('compass reports front, back, left, right and invalid inputs',()=>{
 assert.equal(relativeDirection(2,2,0,5,2),'روبه‌رو');
 assert.equal(relativeDirection(2,2,0,0,2),'پشت سر');
 assert.equal(relativeDirection(2,2,0,2,4),'سمت راست');
 assert.equal(relativeDirection(2,2,0,2,0),'سمت چپ');
 assert.equal(relativeDirection(2,2,0,2,2),'همین‌جا');
 assert.equal(relativeDirection(NaN,2,0,3,4),'نامشخص');
});
test('radar draws walls, objective, enemy, player and does not mutate state',()=>{
 const calls=[],ctx={clearRect:(...x)=>calls.push(['clear',...x]),fillRect:(...x)=>calls.push(['rect',...x]),beginPath(){},arc:(...x)=>calls.push(['arc',...x]),fill(){},save(){},restore(){},translate(){},rotate(){},moveTo(){},lineTo(){},closePath(){}};
 const state={x:2.5,y:3.5,angle:1,enemies:[{x:4,y:5,hp:2},{x:8,y:8,hp:0},{x:Infinity,y:1,hp:4}]};
 const before=JSON.stringify(state);
 assert.equal(paintTacticalMap({width:160,getContext:()=>ctx},state,(x,y)=>x===0||y===0,[6.5,6.5]),true);
 assert.equal(JSON.stringify(state),before);
 assert.equal(calls.filter(x=>x[0]==='arc').length,2);
 assert.equal(calls.filter(x=>x[0]==='rect').length,32);
});
test('radar handles unavailable canvas and rejects out-of-bounds target',()=>{
 assert.equal(paintTacticalMap(null,{},()=>false,null),false);
 let arcs=0;const ctx={clearRect(){},fillRect(){},beginPath(){},arc(){arcs++},fill(){},save(){},restore(){},translate(){},rotate(){},moveTo(){},lineTo(){},closePath(){}};
 assert.equal(paintTacticalMap({width:160,getContext:()=>ctx},{x:2,y:2,angle:0,enemies:[]},()=>false,[100,0]),true);
 assert.equal(arcs,0);
});
