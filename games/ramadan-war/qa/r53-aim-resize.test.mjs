import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {boundedAimMotion} from '../input-guard.mjs';
const source=readFileSync(new URL('../game.js',import.meta.url),'utf8');
test('R53 invalid aim event cancels gesture and releases pointer capture',()=>{
 assert.match(source,/if\(!delta\)\{if\(aimGesture\)aimGesture\.cancelled=true;const old=aimId;aimId=null;safeReleaseCapture\(canvas,old\);return\}/);
});
test('R53 resize clears captured pointers without changing save',()=>{
 assert.match(source,/addEventListener\('resize',\(\)=>\{if\(screen==='game'\)releaseGameInputs\(\)\}\)/);
 assert.match(source,/function releaseGameInputs\(\)\{const oldFire=fireId,oldJoy=joyId,oldAim=aimId;/);
});
test('R53 nonfinite aim input fails closed',()=>{
 assert.equal(boundedAimMotion(Number.NaN,5,1,1),null);
 assert.equal(boundedAimMotion(5,Infinity,1,1),null);
});
