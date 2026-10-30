import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const crown=readFileSync(new URL('../crown-defender/index.html',import.meta.url),'utf8');
const echo=readFileSync(new URL('../echoform/signal-lattice-r44.html',import.meta.url),'utf8');
test('Crown clears held keyboard keys when focus moves to controls',()=>{
 assert.match(crown,/document\.addEventListener\('focusin',e=>\{if\(state==='playing'/);
 assert.match(crown,/keys\.clear\(\);return\}keys\.add\(e\.code\)/);
});
test('Crown focused Escape toggles pause and modified shortcuts cannot trigger abilities',()=>{
 assert.match(crown,/e\.code==='Escape'&&!e\.repeat/);
 assert.match(crown,/e\.preventDefault\(\);pause\(\);return\}const allowed/);
 assert.match(crown,/e\.ctrlKey\|\|e\.altKey\|\|e\.metaKey\|\|e\.isComposing/);
});
test('ECHOFORM protects ongoing sequence from accidental restart',()=>{
 assert.match(echo,/round>1&&!window\.confirm\('Restart the current sequence/);
});
test('ECHOFORM pauses across pagehide and bfcache return',()=>{
 assert.match(echo,/addEventListener\('pagehide'/);
 assert.match(echo,/addEventListener\('pageshow',e=>\{if\(e\.persisted\)pause/);
});
