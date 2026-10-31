import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
test('pagehide suspends gameplay without blur',()=>{
 assert.match(game,/addEventListener\('pagehide',suspendOnPageLifecycle\)/);
 assert.match(game,/function suspendOnPageLifecycle\(\)\{\s*releaseGameInputs\(\);\s*if\(screen==='game'\)\$\('#pause'\)\.click\(\)/);
});
test('freeze suspends and clears temporary private backup',()=>{
 assert.match(game,/document\.addEventListener\('freeze',\(\)=>\{suspendOnPageLifecycle\(\);clearBackupCode\(\);save\(\)\}\)/);
});
test('BFCache return still pauses instead of auto-resuming',()=>{
 assert.match(game,/addEventListener\('pageshow',e=>\{if\(e\.persisted\)\{releaseGameInputs\(\);if\(screen==='game'\)\{\$\('#pause'\)\.click\(\)\}\}\}\)/);
});
