'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('content/zomorod-seed-guardian-20261023/index.html','utf8');
const script=html.split('<script>')[1]?.split('</script>')[0];
assert.ok(script,'Seed Guardian must have a playable script');
new vm.Script(script,'seed-guardian.js');
const start=script.indexOf('let saved={stage:1,best:0,clears:0};');
const end=script.indexOf('let stage=saved.stage',start);
assert.ok(start>=0&&end>start,'Seed Guardian save parser must exist');
const parser=script.slice(start,end);
function load(value,throws=false){
 return vm.runInNewContext("const storeKey='zm.seed.guardian.v1';"+parser+'saved',{
  localStorage:{getItem(){if(throws)throw Error('storage denied');return JSON.stringify(value)}},
  JSON,Number,Math
 });
}
function plain(v){return JSON.parse(JSON.stringify(v))}
assert.deepEqual(plain(load({stage:45,best:1830,clears:44})),{stage:45,best:1830,clears:44},
 'legitimate completed levels and scores must survive');
assert.deepEqual(plain(load({stage:121,best:'999999',clears:'120'})),{stage:120,best:0,clears:0},
 'forged string scores and clear counts must be rejected');
assert.deepEqual(plain(load({stage:1,best:1e30,clears:1000000})),{stage:1,best:0,clears:0},
 'unbounded score and clear counts must be rejected');
assert.deepEqual(plain(load({stage:1,best:-4,clears:-3})),{stage:1,best:0,clears:0},
 'negative score and clear counts must be rejected');
assert.deepEqual(plain(load(null)),{stage:1,best:0,clears:0},
 'null saved data must fall back safely');
assert.deepEqual(plain(load(null,true)),{stage:1,best:0,clears:0},
 'blocked browser storage must not crash the game');
console.log('SEED_GUARDIAN_SAVE_INTEGRITY=PASS: strict bounded records and private mode');
