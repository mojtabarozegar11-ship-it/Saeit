import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const air=readFileSync(new URL('../../air-supremacy/index.html',import.meta.url),'utf8');
const cake=readFileSync(new URL('../../../templates/taniya_studio/index.html',import.meta.url),'utf8');
test('R53 Air rejects a collapsed joystick before capture',()=>{
 assert.match(air,/rect\.width<8\|\|rect\.height<8\)return;try\{stickArea\.setPointerCapture/);
});
test('R53 Air releases capture if drag geometry fails',()=>{
 assert.match(air,/pointermove',e=>\{if\(pointerId===e\.pointerId&&drive\(e\)===false\)/);
 assert.match(air,/const stale=pointerId;pointerId=null;try\{stickArea\.releasePointerCapture\(stale\)\}catch/);
});
test('R53 Taniya retains SVG URL long enough for mobile handoff',()=>{
 assert.match(cake,/setTimeout\(\(\)=>URL\.revokeObjectURL\(pending\),60000\)/);
 assert.match(cake,/document\.body\.appendChild\(a\)/);
});
test('R53 Taniya never claims a confirmed saved download',()=>{
 assert.match(cake,/Cake card download requested\. Check your downloads to confirm/);
 assert.match(cake,/Cake card download is unavailable in this browser/);
});
test('R53 Taniya validates frosting and announces accessible state',()=>{
 assert.match(cake,/if\(!\/\^#\[0-9a-fA-F\]\{6\}\$\/\.test\(e\.target\.value\)\)return/);
 assert.match(cake,/setAttribute\('aria-label','Cake with '/);
});
