import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const roham=readFileSync(new URL('../../templates/studio_raha/index.html',import.meta.url),'utf8');
const taniya=readFileSync(new URL('../../templates/taniya_studio/index.html',import.meta.url),'utf8');
test('Roham runner rejects secondary touch and inactive overlay',()=>{
 assert.match(roham,/function touch\(e\)\{if\(!running\|\|!\$\('#gameOverlay'\)\.classList\.contains\('open'\)\|\|e\.isPrimary===false/);
});
test('Taniya cake preview shows actual icing color and updates on color input',()=>{
 assert.match(taniya,/cakepreview',gamebody\)\.style\.borderBottom='12px solid '\+icing/);
 assert.match(taniya,/gamebody\.querySelectorAll\('\[data-top\]'\)\.forEach\(b=>b\.setAttribute\('aria-pressed'/);
});
