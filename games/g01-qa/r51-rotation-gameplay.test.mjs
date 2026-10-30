import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const crown=readFileSync(new URL('../crown-defender/index.html',import.meta.url),'utf8');
const taniya=readFileSync(new URL('../../templates/taniya_studio/index.html',import.meta.url),'utf8');
test('Crown refuses nonfinite and zero-size canvas geometry',()=>{
 assert.match(crown,/r\.width<8\|\|r\.height<8\|\|W<=0\|\|H<=0\)return null/);
 assert.match(crown,/if\(!Number\.isFinite\(scale\)\|\|scale<=0\)return null/);
 assert.match(crown,/if\(!Number\.isFinite\(x\)\|\|!Number\.isFinite\(y\)\)return null/);
});
test('Crown validates pointer before capture and clears stale drag',()=>{
 assert.match(crown,/const p=pointerTarget\(e\);if\(!p\)return;try\{canvas\.setPointerCapture/);
 assert.match(crown,/const p=pointerTarget\(e\);if\(!p\)\{releaseAimCapture\(\);return\}/);
});
test('Taniya cake draft persists only bounded local decoration state',()=>{
 assert.match(taniya,/sessionStorage\.getItem\('taniyaCakeDraftR51'\)/);
 assert.match(taniya,/Number\.isInteger\(draft\?\.candles\)\?Math\.max\(0,Math\.min\(12,draft\.candles\)\):0/);
 assert.match(taniya,/^\s*let icing=.*\/\^#\[0-9a-fA-F\]\{6\}\$\/\.test/m);
 assert.match(taniya,/sessionStorage\.setItem\('taniyaCakeDraftR51',JSON\.stringify\(\{icing,topping,candles\}\)\)/);
});
test('Taniya saves each meaningful edit and reset clears the draft',()=>{
 for(const action of ['topping=b.dataset.top;rememberCake();draw()','candles=Math.min(12,candles+1);rememberCake();draw()','candles=Math.max(0,candles-1);rememberCake();draw()'])
  assert.ok(taniya.includes(action),action);
 assert.match(taniya,/sessionStorage\.removeItem\('taniyaCakeDraftR51'\)/);
});
