import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const air=readFileSync(new URL('../air-supremacy/index.html',import.meta.url),'utf8');
const echo=readFileSync(new URL('../echoform/signal-lattice-r43.html',import.meta.url),'utf8');
test('Air Supremacy Escape pauses/resumes even if a HUD button has focus',()=>{
 assert.match(air,/if\(e\.code==='Escape'&&!e\.repeat\)\{e\.preventDefault\(\);togglePause\(\);return\}if\(focus\)return/);
});
test('Echoform Escape works on action buttons but does not hijack select controls',()=>{
 assert.match(echo,/if\(e\.key==='Escape'&&!.+\.matches\('select,input,textarea'\)\)\{/);
 assert.match(echo,/Signal Lattice R43/);
});
