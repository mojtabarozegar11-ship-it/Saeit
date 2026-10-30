import test from 'node:test';
import assert from 'node:assert/strict';
import {routeGuidance,paintTacticalMap} from '../tactical-map.mjs';
const wall=(x,y)=>x===2&&y>=1&&y<=3;
test('R34 route direction follows reachable first step, not wall-blocked straight bearing',()=>{
 const hint=routeGuidance(1.5,2.5,0,4.5,2.5,wall);
 assert.equal(hint.status,'reachable');assert.ok(hint.steps>3);
 assert.ok(!hint.message.includes('روبه‌رو'),hint.message);
});
test('R34 enclosed objectives are announced blocked, never fabricated',()=>{
 const enclosed=(x,y)=>x===0||y===0||x===15||y===15||((x===5||x===7)&&y>=4&&y<=6)||((y===4||y===6)&&x>=5&&x<=7);
 const hint=routeGuidance(2.5,2.5,0,6.5,5.5,enclosed);
 assert.equal(hint.status,'blocked');assert.match(hint.message,/مسدود/);
});
test('R34 adjacent solid goal reports interaction range',()=>{
 const hint=routeGuidance(1.5,2.5,0,2.5,2.5,wall);
 assert.equal(hint.status,'arrived');assert.equal(hint.steps,0);assert.match(hint.message,/تعامل/);
});
test('R34 invalid inputs fail closed and radar exposes accessible status',()=>{
 assert.equal(routeGuidance(NaN,2,0,3,4,wall).status,'invalid');
 let label='';const ctx={clearRect(){},fillRect(){},beginPath(){},arc(){},fill(){},save(){},restore(){},translate(){},rotate(){},moveTo(){},lineTo(){},closePath(){},stroke(){}};
 const canvas={width:160,getContext:()=>ctx,setAttribute:(k,v)=>{if(k==='aria-label')label=v},getAttribute:()=>label};
 const state={x:1.5,y:2.5,angle:0,enemies:[]};
 assert.equal(paintTacticalMap(canvas,state,wall,[4.5,2.5]),true);
 assert.match(label,/مسیر هدف/);assert.match(label,/خانه/);
 assert.equal(paintTacticalMap(canvas,state,wall,null),true);
 assert.match(label,/هدف فعالی/);
});
