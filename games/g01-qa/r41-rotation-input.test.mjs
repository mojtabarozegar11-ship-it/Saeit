import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const air=readFileSync(new URL('../air-supremacy/index.html',import.meta.url),'utf8');
const crown=readFileSync(new URL('../crown-defender/index.html',import.meta.url),'utf8');
test('Air Supremacy releases all held touch inputs on finish, not only pause',()=>{
 const begin=air.indexOf('function finish(won){'),end=air.indexOf('function shoot(){',begin);
 assert.ok(begin>0&&end>begin);
 const code=air.slice(begin,end);
 const messages=[];const profile={credits:0,bestScore:0,wins:0};
 const elements=new Map();
 const $=id=>{if(!elements.has(id))elements.set(id,{classList:{add(){},remove(){}},setAttribute(){},textContent:'',innerHTML:''});return elements.get(id)};
 const ctx={run:true,paused:false,firing:true,key:new Set(['Space']),togglePause:v=>messages.push(v),score:50,kills:2,mission:1,MAX_MISSION:12,creditsEarned:5,profile,refreshHangar(){},$};
 vm.runInNewContext(code+'\nglobalThis.finishSortie=finish;',ctx);
 ctx.finishSortie(false);
 assert.deepEqual(messages,[true]);assert.equal(ctx.run,false);assert.equal(ctx.firing,false);
});
test('Crown Defender releases captured aim pointer on pause/blur/hidden',()=>{
 const begin=crown.indexOf('function releaseAimCapture(){'),end=crown.indexOf('function pause(){',begin);
 assert.ok(begin>0&&end>begin);
 const released=[];
 const ctx={pointer:23,touchTarget:{x:1},dragAnchor:{x:2},canvas:{hasPointerCapture:id=>id===23,releasePointerCapture:id=>released.push(id)}};
 vm.runInNewContext(crown.slice(begin,end)+'\nglobalThis.releaseAim=releaseAimCapture;',ctx);
 ctx.releaseAim();assert.deepEqual(released,[23]);assert.equal(ctx.pointer,null);
 assert.match(crown,/function pause\(\)\{if\(state==='playing'\)\{releaseTouchControls\(\);keys\.clear\(\);releaseAimCapture\(\)/);
 assert.match(crown,/visibilitychange',\(\)=>\{if\(document.hidden\)\{keys.clear\(\);releaseTouchControls\(\);releaseAimCapture\(\)/);
});
