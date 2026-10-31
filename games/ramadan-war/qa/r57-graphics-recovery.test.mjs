import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {canEnterGameplay,canReloadGraphics} from '../graphics-recovery.mjs';
const game=readFileSync(new URL('../game.js',import.meta.url),'utf8');
const home=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const crown=readFileSync(new URL('../../crown-defender/index.html',import.meta.url),'utf8');
const air=readFileSync(new URL('../../air-supremacy/index.html',import.meta.url),'utf8');

test('R57 GPU lost or hidden never resumes gameplay',()=>{
 assert.equal(canEnterGameplay(false,false),true);
 for(const flags of [[true,false],[false,true],[true,true]])assert.equal(canEnterGameplay(...flags),false);
 assert.match(game,/addEventListener\('webglcontextlost',event=>\{event\.preventDefault\(\);graphicsUnavailable=true;releaseGameInputs\(\)/);
 assert.match(game,/function showScreen\(name\)\{if\(name==='game'&&!canEnterGameplay\(graphicsUnavailable,document\.hidden\)\)/);
});
test('R57 manual graphics reload requires verified durable save',()=>{
 assert.equal(canReloadGraphics(true,'saved'),true);
 for(const status of ['failed','not-saved','survival',undefined])assert.equal(canReloadGraphics(true,status),false);
 assert.equal(canReloadGraphics(false,'saved'),false);
 assert.match(home,/id="reloadGraphics"[^>]*hidden disabled/);
 assert.match(game,/\$\('#reloadGraphics'\)\.onclick=\(\)=>\{if\(!canReloadGraphics\(graphicsUnavailable,saveStatus\)\)/);
});
test('R57 Crown Defender freeze drops held input and pauses',()=>{
 assert.match(crown,/document\.addEventListener\('freeze',\(\)=>\{keys\.clear\(\);releaseTouchControls\(\);releaseAimCapture\(\);if\(state==='playing'\)pause\(\)\}\)/);
});
test('R57 Air Supremacy BFCache and freeze cannot retain firing',()=>{
 assert.match(air,/function suspendAirForLifecycle\(\)\{key\.clear\(\);firing=false;boostHeld=false;if\(run&&!paused\)togglePause\(true\)\}/);
 for(const marker of ["'pagehide',suspendAirForLifecycle","'freeze',suspendAirForLifecycle","'pageshow',e=>{if(e.persisted)suspendAirForLifecycle()"])assert.ok(air.includes(marker));
});
