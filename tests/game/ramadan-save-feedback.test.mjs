import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {boundedCampaignPickups} from '../../games/ramadan-war/save-validation.mjs';

const source=readFileSync(new URL('../../games/ramadan-war/game.js',import.meta.url),'utf8');
const saveLine=source.split('\n').find(line=>line.startsWith('let saveWarningShown=false;function save(){'));
assert.ok(saveLine,'save must expose one-time storage-failure notice');

function setup(canSave=false) {
  const notifications=[],writes=[],removes=[];
  const context={world:{mission:0,victory:false,gameOver:false},saveKey:'rwNativeCampaign',
    boundedCampaignPickups,
    storageWrite:(key,value)=>{writes.push({key,value});return canSave},
    storageRemove:key=>{removes.push(key);return true},
    toast:message=>notifications.push(message)};
  vm.runInNewContext(saveLine,context);
  return {context,notifications,writes,removes};
}

test('failed browser storage shows an actionable warning only once despite repeated autosaves',()=>{
  const h=setup(false);
  h.context.save();h.context.save();h.context.save();
  assert.equal(h.writes.length,3);
  assert.equal(h.notifications.length,1);
  assert.match(h.notifications[0],/ذخیره/);
  assert.match(h.notifications[0],/خروج/);
});

test('successful campaign save never falsely reports a persistence failure',()=>{
  const h=setup(true);
  h.context.save();
  assert.equal(h.writes.length,1);
  assert.equal(h.notifications.length,0);
});

test('completed campaign deletes its obsolete save without warning about storage writes',()=>{
  const h=setup(false);
  h.context.world.victory=true;
  h.context.save();
  assert.equal(h.writes.length,0);
  assert.deepEqual(h.removes,['rwNativeCampaign']);
  assert.equal(h.notifications.length,0);
});

test('no active campaign performs no persistence operation or warning',()=>{
  const h=setup(false);
  h.context.world=null;
  h.context.save();
  assert.equal(h.writes.length,0);
  assert.equal(h.notifications.length,0);
});
