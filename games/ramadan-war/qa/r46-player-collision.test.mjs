import test from 'node:test';
import assert from 'node:assert/strict';
import {playerSpaceClear,movePlayerWithCollision} from '../player-collision.mjs';
import {readFileSync} from 'node:fs';
const walls=(x,y)=>x<0||y<0||x>=6||y>=6||x===0||y===0||x===5||y===5||x===3&&y===2;

test('free keyboard or joystick motion retains exact displacement',()=>{
 const p={x:1.5,y:1.5};assert.equal(movePlayerWithCollision(p,.5,.25,walls),true);
 assert.ok(Math.abs(p.x-2)<1e-9);assert.ok(Math.abs(p.y-1.75)<1e-9);
});
test('radius footprint blocks clipping into a wall even when center is clear',()=>{
 const p={x:2.5,y:2.5};movePlayerWithCollision(p,.45,0,walls);
 assert.ok(p.x<2.79,'player must not enter tile x=3 with 0.21 radius');
});
test('diagonal collision slides along a clear axis without entering blocked corner',()=>{
 const p={x:2.5,y:1.5};movePlayerWithCollision(p,.7,.7,walls);
 assert.equal(playerSpaceClear(p.x,p.y,walls),true);
 assert.ok(p.y>1.5,'movement can slide along open corridor');
});
test('swept motion cannot tunnel across an obstacle in a single update',()=>{
 const p={x:1.5,y:2.5};movePlayerWithCollision(p,2.5,0,walls);
 assert.ok(p.x<2.79,'swept collision stops before x=3');
});
test('nonfinite coordinates and deltas fail closed',()=>{
 const p={x:1.5,y:1.5};assert.equal(movePlayerWithCollision(p,Infinity,1,walls),false);
 assert.equal(movePlayerWithCollision(p,NaN,1,walls),false);
 assert.equal(movePlayerWithCollision(p,11,0,walls),false);
 assert.deepEqual(p,{x:1.5,y:1.5});
});
test('outer map edges are solid to the full player footprint',()=>{
 assert.equal(playerSpaceClear(.1,2,walls),false);
 assert.equal(playerSpaceClear(5.8,2,walls),false);
});
test('game runtime uses shared radius-aware movement for both control schemes',()=>{
 const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
 assert.match(game,/import \{movePlayerWithCollision\} from '\.\/player-collision\.mjs'/);
 assert.match(game,/function move\(dx,dy\)\{movePlayerWithCollision\(world,dx,dy/);
 assert.match(game,/const movement=resolveMovementAxes\(joyF,joyS,keys\)/);
});
