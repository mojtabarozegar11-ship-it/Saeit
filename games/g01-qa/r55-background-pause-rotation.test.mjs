import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const roham=readFileSync(new URL('../../templates/studio_raha/index.html',import.meta.url),'utf8');
const echo=readFileSync(new URL('../echoform/signal-lattice-r43.html',import.meta.url),'utf8');
function parseInline(html) {
  const blocks=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
  assert.ok(blocks.length,'Expected inline gameplay source');
  for(const block of blocks) new Function(block[1]);
}
test('R55 Roham: background transition pauses run and requires manual resume',()=>{
  assert.match(roham,/function backgroundPause\(\)\{if\(!running\|\|paused\)return;paused=true;/);
  assert.match(roham,/function visibility\(\)\{if\(document.hidden\)backgroundPause\(\);else resumeVisible\(\)\}/);
  assert.match(roham,/window.addEventListener\('blur',backgroundPause\)/);
  assert.match(roham,/window.removeEventListener\('blur',backgroundPause\)/);
  parseInline(roham);
});
test('R55 ECHOFORM: pagehide and BFCache restore cancel stale playback',()=>{
  assert.match(echo,/window.addEventListener\('pagehide',\(\)=>pause\(/);
  assert.match(echo,/window.addEventListener\('pageshow',e=>\{if\(e.persisted\)pause\(/);
  assert.match(echo,/function pause\(reason\)\{if\(phase!=='input'&&phase!=='show'\)return;session\+\+/);
  parseInline(echo);
});
