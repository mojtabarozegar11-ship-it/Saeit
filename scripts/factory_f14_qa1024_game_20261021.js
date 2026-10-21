#!/usr/bin/env node
/* 1,024 reproducible stateful scenarios, deterministic replay and fail-closed invariants.
   Original F14 game engine only; no DOM or network dependencies. */
'use strict';
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const path=require('node:path');
const [, ,enginePath,nRaw]=process.argv;
assert(enginePath&&nRaw,'engine path and required case count');
const required=Number(nRaw);
assert(Number.isInteger(required)&&required>=1024&&required<=20000);
const E=require(path.resolve(enginePath));
assert(E.ROWS===5&&E.COLS===8);
assert(Object.keys(E.PLANTS).sort().join(',')==='mist,thorn,well');
const kinds=['thorn','mist','well'];

function prng(value){
  let state=value>>>0;
  return ()=>{state=(Math.imul(1664525,state)+1013904223)>>>0;return state;};
}
function invariant(g,info){
  assert(g.health>=0&&g.health<=12&&Number.isInteger(g.health),info+':health');
  assert(Number.isFinite(g.water)&&g.water>=-1e-9&&g.water<=100.00000001,info+':water');
  assert(Number.isSafeInteger(g.score)&&g.score>=0,info+':score');
  assert(Number.isFinite(g.elapsed)&&g.elapsed>=0,info+':time');
  assert(g.wave>=1&&Number.isSafeInteger(g.wave),info+':wave');
  assert(g.waveRemaining>=0&&Number.isSafeInteger(g.waveRemaining),info+':spawns');
  assert(g.events.length<=10,info+':events');
  assert(g.cooldown>=0&&Number.isFinite(g.cooldown),info+':cooldown');
  assert(g.plants.length<=E.ROWS*E.COLS,info+':plant-capacity');
  const placed=new Set();
  for(const p of g.plants){
    assert(p.row>=0&&p.row<E.ROWS&&Number.isInteger(p.row));
    assert(p.col>=0&&p.col<E.COLS&&Number.isInteger(p.col));
    assert(E.PLANTS[p.kind],info+':plant-type');
    const cell=p.row+','+p.col;
    assert(!placed.has(cell),info+':duplicate-cell');placed.add(cell);
  }
  for(const e of g.enemies){
    assert(Number.isFinite(e.x)&&e.x>=68&&e.x<=900,info+':enemy-position');
    assert(e.hp>0&&Number.isFinite(e.hp),info+':enemy-hp');
    assert(e.row>=0&&e.row<5&&Number.isInteger(e.row),info+':enemy-lane');
    assert(e.slow>=0&&Number.isFinite(e.slow),info+':slow');
  }
  if(g.over)assert(g.health===0,info+':gameover-zero-health');
}
function run(seed){
  const rnd=prng((seed*2654435761)^0xa1bd2026);
  const g=E.newGame();
  assert.equal(E.plant(g,0,0,'thorn').ok,false);
  assert.equal(E.start(g),true);
  assert.equal(E.start(g),false);
  assert.equal(E.choose(g,'__proto__'),false);
  assert.equal(E.choose(g,'unknown'),false);
  let prevScore=0;
  const steps=170+(seed%4)*55;
  for(let t=0;t<steps;t++){
    if(g.over)break;
    const info=seed+':'+t;
    if(t%11===0){
      const row=rnd()%7-1,col=rnd()%10-1;
      const kind=kinds[rnd()%3];
      const before=g.water;
      const n=g.plants.length;
      const result=E.plant(g,row,col,kind);
      if(result.ok){
        assert(row>=0&&row<5&&col>=0&&col<8);
        assert(before>=E.PLANTS[kind].cost);
        assert(Math.abs(g.water-(before-E.PLANTS[kind].cost))<1e-7);
        assert.equal(g.plants.length,n+1);
      }else assert.equal(g.plants.length,n);
    }
    if(t%23===0){
      const before=g.water,cd=g.cooldown;
      const originalEnemies=g.enemies.length;
      const rain=E.rainburst(g);
      if(rain.ok){
        assert(before>=25&&cd===0&&originalEnemies>0);
        assert(Math.abs(g.water-(before-25))<1e-7);
        assert.equal(g.cooldown,12);
      }else assert.equal(g.water,before);
    }
    if(t%83===0){
      const snapshot=JSON.stringify(g);
      g.paused=true;
      E.advance(g,0.1);
      g.paused=false;
      // Compare all other fields: frozen state must never mutate.
      const previous=JSON.parse(snapshot);
      previous.paused=false;
      assert.deepEqual(g,previous,info+':paused-state-changed');
    }
    if(t%39===0){
      const n=g.plants.length;
      assert.equal(E.plant(g,-1,0,'thorn').ok,false);
      assert.equal(E.plant(g,0,8,'well').ok,false);
      assert.equal(E.plant(g,0,0,'javascript:evil').ok,false);
      assert.equal(g.plants.length,n);
    }
    const previousTime=g.elapsed;
    E.advance(g,.1);
    invariant(g,info);
    assert(g.elapsed>=previousTime,info+':time-backwards');
    assert(g.score>=prevScore,info+':score-backwards');
    prevScore=g.score;
  }
  const frozen=JSON.stringify(g);
  if(g.over){E.advance(g,100);assert.equal(JSON.stringify(g),frozen,'ended game mutated');}
  invariant(g,seed+':final');
  return JSON.stringify(g);
}
let paired=0;
const all=crypto.createHash('sha256');
for(let seed=1;seed<=required;seed++){
  const a=run(seed),b=run(seed);
  assert.equal(crypto.createHash('sha256').update(a).digest('hex'),
    crypto.createHash('sha256').update(b).digest('hex'),
    'Nondeterministic replay '+seed);
  all.update(a);paired++;
}
const edge=E.newGame();E.start(edge);
edge.health=1;
edge.enemies=[{id:1,row:0,x:68.05,hp:20,maxHp:20,
               speed:20,points:1,hurt:1,slow:0,phase:0}];
E.advance(edge,.1);
assert(edge.over&&edge.health===0);
const dead=JSON.stringify(edge);E.advance(edge,50);assert.equal(JSON.stringify(edge),dead);
const output={cases:required,failures:0,deterministic_replay_verified:paired,
  fixture_loss_guard:'PASS',replay_digest_sha256:all.digest('hex')};
process.stdout.write(JSON.stringify(output)+'\n');
