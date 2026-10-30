import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Script} from 'node:vm';

function inlineScript(path) {
  const html=readFileSync(new URL(path,import.meta.url),'utf8');
  const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
  assert.equal(scripts.length,1);
  new Script(scripts[0][1],{filename:path});
  return scripts[0][1];
}
test('Crown rejects menu and paused gameplay input while allowing P resume',()=>{
  const src=inlineScript('../crown-defender/index.html');
  assert.match(src,/if\(state!=='playing'\)\{keys\.clear\(\);if\(state==='paused'&&overlayState==='pause'&&e\.code==='KeyP'/);
});
test('Air rejects gameplay keys during pause, allowing Escape/P only',()=>{
  const src=inlineScript('../air-supremacy/index.html');
  assert.match(src,/paused&&e\.code!=='Escape'&&e\.code!=='KeyP'/);
});
