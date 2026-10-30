import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isInteractiveTarget,keyboardAction,shouldReleaseHeldKeysOnFocus} from '../input-guard.mjs';
const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const target=(selector)=>({closest:(query)=>query.includes(selector)?{}:null});
for(const role of ['link','slider','checkbox','switch','radio','combobox','menuitem','tab']){
 test(`R54 keyboard shortcut cannot hijack ARIA ${role}`,()=>{
  const t=target(`[role="${role}"]`);
  assert.equal(isInteractiveTarget(t),true);
  assert.equal(keyboardAction('Space','game',t),null);
  assert.equal(shouldReleaseHeldKeysOnFocus('game',t),true);
 });
}
test('R54 restored bfcache game clears touch and keyboard then pauses',()=>{
 assert.match(game,/addEventListener\('pageshow',e=>\{if\(e\.persisted\)\{releaseGameInputs\(\);if\(screen==='game'\)\{\$\('#pause'\)\.click\(\)\}\}\}\)/);
 assert.match(game,/function releaseGameInputs\(\)\{const oldFire=fireId,oldJoy=joyId,oldAim=aimId;/);
});
test('R54 ordinary game arena still accepts keyboard fire',()=>{
 assert.equal(keyboardAction('Space','game',null), 'fire');
 assert.equal(keyboardAction('KeyR','game',null),'reload');
});
