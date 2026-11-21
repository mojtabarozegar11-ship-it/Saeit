import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const air=readFileSync(new URL('../../games/air-supremacy/index.html',import.meta.url),'utf8');
const crown=readFileSync(new URL('../../games/crown-defender/index.html',import.meta.url),'utf8');

test('Air Supremacy keeps test mutators on loopback only',()=>{
 const begin=air.indexOf('const airQa={snapshot:');
 const end=air.indexOf('refreshHangar();',begin);
 assert.ok(begin>0&&end>begin,'extract production QA export');
 const source=air.slice(begin,end);
 for(const host of ['localhost','127.0.0.1','mojplaywin.com','example.org']){
  const ctx={window:{},location:{hostname:host},begin(){},render(){},sceneTime:0};
  vm.runInNewContext(source,ctx);
  const api=ctx.window.__AIR_SUPREMACY_QA__;
  assert.ok(api&&Object.isFrozen(api));
  assert.equal(typeof api.snapshot,'function');
  assert.equal(typeof api.start,host==='localhost'||host==='127.0.0.1'?'function':'undefined');
  assert.equal(typeof api.renderOnce,host==='localhost'||host==='127.0.0.1'?'function':'undefined');
 }
});
test('Crown Defender exposes only copied read-only telemetry on public hosts',()=>{
 assert.match(crown,/const crownQa=\{getState:/);
 assert.match(crown,/const publicCrownQa=\{getState:crownQa\.getState,getEffects:crownQa\.getEffects,getFleet:crownQa\.getFleet\}/);
 assert.match(crown,/Object\.freeze\(typeof location!=='undefined'&&\['localhost','127\.0\.0\.1'\]\.includes\(location\.hostname\)\?crownQa:publicCrownQa\)/);
 assert.doesNotMatch(crown,/window\.__mpwCrownDefenderTest=\{getState:/);
});
