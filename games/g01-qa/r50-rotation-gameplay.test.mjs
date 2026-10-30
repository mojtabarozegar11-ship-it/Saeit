import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const air=readFileSync(new URL('../air-supremacy/index.html',import.meta.url),'utf8');
const roham=readFileSync(new URL('../../templates/studio_raha/index.html',import.meta.url),'utf8');
const start=air.indexOf('function drive(e){');
const end=air.indexOf("stickArea.addEventListener('pointerdown'",start);
test('Air Supremacy joystick function remains extractable',()=>{
 assert.ok(start>=0&&end>start);const source=air.slice(start,end);
 new vm.Script(source+';drive({clientX:0,clientY:0})');
});
test('Air Supremacy invalid touch cannot poison flight vector',()=>{
 const stick={x:1,y:1},knob={style:{transform:'old'}};
 const stickArea={getBoundingClientRect:()=>({left:0,bottom:200,width:200,height:200})};
 const context={stick,knob,stickArea,Math,Number};vm.createContext(context);
 vm.runInContext(air.slice(start,end),context);
 vm.runInContext('drive({clientX:NaN,clientY:30})',context);
 assert.equal(stick.x,0);assert.equal(stick.y,0);assert.equal(knob.style.transform,'translate(0,0)');
 vm.runInContext('drive({clientX:109,clientY:158})',context);
 assert.ok(Math.abs(stick.x-1)<.001);assert.equal(stick.y,0);
});
test('Roham Jungle Run includes manual pause and keyboard P',()=>{
 assert.match(roham,/const pauseBtn=button\('Pause ⏸'/);
 assert.match(roham,/e\.code==='KeyP'/);
 assert.match(roham,/if\(paused\|\|!running\)return/);
 assert.match(roham,/if\(running&&!paused&&!document\.hidden&&!raf\)/);
 assert.match(roham,/if\(running&&!paused&&air<=0\)/);
});
test('Roham pause does not leave an active animation frame',()=>{
 assert.match(roham,/if\(paused\)suspend\(\);else resumeVisible\(\)/);
 assert.match(roham,/function suspend\(\)\{cancelAnimationFrame\(raf\);raf=0;last=0\}/);
});
