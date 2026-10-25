'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
for(const [name,path] of [
 ['English','games/air-supremacy/index.html'],
 ['Persian','games/air-supremacy-fa/index.html']
]){
 const html=fs.readFileSync(path,'utf8');
 const script=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].at(-1)?.[1];
 assert(script,name+' gameplay script missing');new vm.Script(script,{filename:path});
 const from=script.indexOf('function drive(e){'),to=script.indexOf("stickArea.addEventListener('pointermove'",from);
 assert(from>=0&&to>from,name+' touch-control boundary missing');
 const control=script.slice(from,to);
 const result=vm.runInNewContext(`
 let pointerId=null;const stick={x:0,y:0},knob={style:{}},handlers={};
 const stickArea={getBoundingClientRect(){return {left:0,width:200,bottom:200,height:200}},setPointerCapture(){},addEventListener(event,fn){handlers[event]=fn}};
 `+control+`
 handlers.pointerdown({pointerId:1,clientX:77.5,clientY:158,preventDefault(){}});
 const half=stick.x;
 handlers.pointerdown({pointerId:2,clientX:1000,clientY:1000,preventDefault(){}});
 const preserved=stick.x,owner=pointerId;
 drive({clientX:146,clientY:258});
 ({half,preserved,owner,magnitude:Math.hypot(stick.x,stick.y)})
 `);
 assert(result.half>.49&&result.half<.51,name+' joystick must be linear at half deflection');
 assert.equal(result.owner,1,name+' second finger must not hijack first joystick pointer');
 assert.equal(result.preserved,result.half,name+' second finger must not move the joystick');
 assert(Math.abs(result.magnitude-1)<1e-9,name+' diagonal joystick must normalize to unit magnitude');
}
console.log('AIR_SUPREMACY_TOUCH_PASS: EN and FA linear joystick, radial cap, multitouch ownership');
