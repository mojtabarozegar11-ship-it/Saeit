import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const crown=readFileSync(new URL('../crown-defender/index.html',import.meta.url),'utf8');
const air=readFileSync(new URL('../air-supremacy/index.html',import.meta.url),'utf8');
test('R54 Crown ARIA focus prevents keyboard gameplay shortcuts',()=>{
 assert.match(crown,/\[role="slider"\]/);
 assert.match(crown,/\[role="menuitem"\]/);
 assert.match(crown,/if\(e\.target\?\.closest\?\.\('button,input,select,textarea/);
});
test('R54 Air browser modifiers release held movement keys',()=>{
 assert.match(air,/if\(e\.ctrlKey\|\|e\.altKey\|\|e\.metaKey\|\|e\.isComposing\|\|e\.keyCode===229\)\{key\.clear\(\);return\}/);
});
test('R54 Air ARIA focus releases movement keys',()=>{
 assert.match(air,/document\.addEventListener\('focusin',e=>\{if\(run&&e\.target\?\.closest\?\./);
});
