import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
test('R36 Air Supremacy touch fire and boost are pointer-owned and pause-released', () => {
 const html = read('../../air-supremacy/index.html');
 assert.match(html, /let boostPointer=null,gunPointer=null/);
 assert.match(html, /e\.pointerId===boostPointer/);
 assert.match(html, /e\.pointerId===gunPointer/);
 assert.match(html, /if\(!run\|\|paused\|\|e\.button!==0\)return/);
 assert.match(html, /boostPointer=null;gunPointer=null;if\(pointerId!==null\)/);
 const inline = html.match(/<script>([\s\S]*?)<\/script>/i);
 assert.ok(inline, 'Air Supremacy executable inline script exists');
 assert.doesNotThrow(() => new vm.Script(inline[1]));
});
test('R36 ECHOFORM persists validated speed and replays with R shortcut', () => {
 const html = read('../../echoform/signal-lattice-r36.html');
 assert.match(html, /Object\.hasOwn\(SPEED,savedSpeed\)/);
 assert.match(html, /localStorage\.setItem\(SPEED_KEY/);
 assert.match(html, /e\.code==='KeyR'/);
 assert.match(html, /phase==='paused'\|\|phase==='input'/);
 const inline = html.match(/<script>([\s\S]*?)<\/script>/i);
 assert.ok(inline);
 assert.doesNotThrow(() => new vm.Script(inline[1]));
});
