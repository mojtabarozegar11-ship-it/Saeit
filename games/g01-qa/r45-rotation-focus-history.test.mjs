import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const crown=readFileSync(new URL('../crown-defender/index.html',import.meta.url),'utf8');
const echo=readFileSync(new URL('../echoform/signal-lattice-r45.html',import.meta.url),'utf8');

test('Crown releases held keyboard, touch and aim controls on pagehide and bfcache',()=>{
 assert.match(crown,/addEventListener\('pagehide',\(\)=>\{keys\.clear\(\);releaseTouchControls\(\);releaseAimCapture\(\);if\(state==='playing'\)pause\(\)\}\)/);
 assert.match(crown,/addEventListener\('pageshow',e=>\{if\(e\.persisted\)\{keys\.clear\(\);releaseTouchControls\(\);releaseAimCapture\(\);if\(state==='playing'\)pause\(\)\}\}\)/);
});
test('ECHOFORM warns before restarting any active round including round one',()=>{
 assert.match(echo,/phase==='paused'\)\&\&round>0\&\&!window\.confirm\('Restart the current sequence\?/);
 assert.doesNotMatch(echo,/round>1\&\&!window\.confirm/);
 assert.match(echo,/Signal Lattice R45/);
});
