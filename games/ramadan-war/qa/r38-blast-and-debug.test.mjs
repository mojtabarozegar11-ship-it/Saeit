import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {blastDamageFactor} from '../missile-targets.mjs';
test('cover impact does not damage enemies through solid walls',()=>{
 const blocked=()=>true;
 assert.equal(blastDamageFactor(1,1,2,1,blocked,true),0);
 assert.ok(blastDamageFactor(1,1,2,1,blocked,false)>0);
});
test('nearby visible enemy gets distance-scaled damage; invalid input fails closed',()=>{
 assert.equal(blastDamageFactor(1,1,1,1,()=>false,true),1);
 assert.ok(blastDamageFactor(1,1,2,1,()=>false,true)>0);
 assert.equal(blastDamageFactor(1,1,4,1,()=>false,true),0);
 assert.equal(blastDamageFactor(Infinity,1,1,1,()=>false,true),0);
 assert.equal(blastDamageFactor(1,1,1,1,null,true),0);
});
test('rocket collision passes cover flag and debug reports simulation enemy count',()=>{
 const s=readFileSync(new URL('../game.js',import.meta.url),'utf8');
 assert.match(s,/explode\(m\.x,m\.y,145,true\)/);
 assert.match(s,/\.\.\.engine\.stats\(\),enemies:world\.enemies\.length/);
 assert.match(s,/blastDamageFactor\(x,y,e\.x,e\.y,blocked,coverOnly\)/);
});
