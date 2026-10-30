import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const roham=readFileSync(new URL('../../templates/studio_raha/index.html',import.meta.url),'utf8');
const echo=readFileSync(new URL('../echoform/signal-lattice-r43.html',import.meta.url),'utf8');
const scripts=html=>[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(m=>m[1]);

test('R48: Roham and ECHOFORM inline gameplay scripts parse',()=>{
 for(const html of [roham,echo]){const parts=scripts(html);assert.ok(parts.length>0);for(const src of parts)new vm.Script(src)}
});
test('R48: Roham drawing owns a single touch and releases on cancel',()=>{
 const begin=roham.indexOf('function drawGame(stage){'),end=roham.indexOf('\nfunction runnerGame(stage){',begin);
 assert.ok(begin>=0&&end>begin);
 const ctx={lineWidth:0,lineCap:'',strokeStyle:'',beginPath(){},moveTo(){},arc(){this.dots=(this.dots||0)+1},fill(){},lineTo(){this.lines=(this.lines||0)+1},stroke(){},clearRect(){}};
 const canvas={width:600,height:250,getContext:()=>ctx,getBoundingClientRect:()=>({left:0,top:0,width:600,height:250}),setPointerCapture(){}};
 const stage={innerHTML:'',querySelector:s=>s==='canvas'?canvas:{append(){}}};
 const sandbox={button:()=>({})};
 vm.runInNewContext(roham.slice(begin,end)+';globalThis.drawGame=drawGame;',sandbox);
 sandbox.drawGame(stage);
 const evt=id=>({pointerId:id,pointerType:'touch',button:0,clientX:10,clientY:10,preventDefault(){}});
 canvas.onpointerdown(evt(1));canvas.onpointerdown(evt(2));canvas.onpointermove(evt(2));
 assert.equal(ctx.dots,1);assert.equal(ctx.lines||0,0);
 canvas.onpointermove(evt(1));assert.equal(ctx.lines,1);
 canvas.onpointercancel(evt(1));canvas.onpointerdown(evt(2));assert.equal(ctx.dots,2);
});
test('R48: ECHOFORM mistake feedback identifies expected and received tiles',()=>{
 assert.match(echo,/function finish\(expected,received\)/);
 assert.match(echo,/light\(expected,'correct'\)/);
 assert.match(echo,/finish\(sequence\[cursor\],i\)/);
 assert.match(echo,/Expected signal/);
});
