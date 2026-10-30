import test from 'node:test';
import assert from 'node:assert/strict';
import {boundedAimMotion} from '../input-guard.mjs';
import {readFileSync} from 'node:fs';
const src=readFileSync(new URL('../game.js', import.meta.url),'utf8');
test('normal touch aiming keeps exact movement',()=>assert.deepEqual(boundedAimMotion(150,170,130,120),{dx:20,dy:50}));
test('orientation jumps are bounded per axis',()=>assert.deepEqual(boundedAimMotion(9000,-9000,10,10),{dx:120,dy:-120}));
test('custom cap cannot exceed hard safety maximum',()=>assert.deepEqual(boundedAimMotion(10000,0,0,0,1e8),{dx:240,dy:0}));
test('invalid pointer positions fail closed',()=>{for(const x of [NaN,Infinity,-Infinity])assert.equal(boundedAimMotion(x,10,0,0),null);});
test('invalid prior pointer position fails closed',()=>assert.equal(boundedAimMotion(10,20,NaN,0),null));
test('invalid step limit fails closed',()=>{assert.equal(boundedAimMotion(10,20,0,0,0),null);assert.equal(boundedAimMotion(10,20,0,0,Infinity),null)});
test('live game uses bounded aim before applying angle and camera pitch',()=>{
 assert.match(src,/const delta=boundedAimMotion\(e\.clientX,e\.clientY,aimLast,aimY\)/);
 assert.match(src,/if\(!delta\)\{if\(aimGesture\)aimGesture\.cancelled=true;const old=aimId;aimId=null;safeReleaseCapture\(canvas,old\);return\}/);
 assert.match(src,/world\.angle-=delta\.dx/);assert.match(src,/engine\.look\(0,delta\.dy/);
});
test('orientation transient does not resize WebGL to zero pixels',()=>assert.match(src,/W=Math\.max\(1,gameRoot\.clientWidth\|\|0\);H=Math\.max\(1,gameRoot\.clientHeight\|\|0\)/));
