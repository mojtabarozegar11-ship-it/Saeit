import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {boundedJoystickPointer} from '../input-guard.mjs';

const ramadan=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const air=readFileSync(new URL('../../air-supremacy/index.html',import.meta.url),'utf8');
const cake=readFileSync(new URL('../../../templates/taniya_studio/index.html',import.meta.url),'utf8');

test('R52: collapsed touch surface cannot acquire a joystick pointer',()=>{
  assert.equal(boundedJoystickPointer(20,20,{left:0,top:0,width:0,height:80}),null);
  assert.match(ramadan,/if\(!boundedJoystickPointer\(e\.clientX,e\.clientY,stick\.getBoundingClientRect\(\)\)\)return;e\.preventDefault\(\);joyId=e\.pointerId/);
});
test('R52: invalid active drag releases pointer capture and allows a fresh finger',()=>{
  assert.match(ramadan,/stick\.onpointermove=e=>\{if\(e\.pointerId===joyId&&stickMove\(e\)!==true\)\{const old=joyId;joyId=null;safeReleaseCapture\(stick,old\)\}\}/);
});
test('R52: failed pointer capture neutralizes stale mobile movement',()=>{
  assert.match(ramadan,/catch\(_\)\{joyId=null;joyF=joyS=0;knob\.style\.transform='';return\}stickMove\(e\)/);
});
test('R52: Air Supremacy joystick rejects malformed rect origin and overflow',()=>{
  assert.match(air,/!Number\.isFinite\(r\.left\)\|\|!Number\.isFinite\(r\.bottom\)/);
  assert.match(air,/!Number\.isFinite\(dx\)\|\|!Number\.isFinite\(dy\)\|\|!Number\.isFinite\(d\)/);
});
test('R52: Cake Maker undo persists after rendering and preserves legacy undo',()=>{
  assert.match(cake,/candles=Math\.max\(0,candles-1\);draw\(\);rememberCake\(\)/);
  assert.match(cake,/sessionStorage\.setItem\('taniyaCakeDraftR51'/);
});
