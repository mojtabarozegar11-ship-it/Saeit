import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const game=readFileSync(new URL('../ramadan-war/game.js',import.meta.url),'utf8');
const roham=readFileSync(new URL('../../templates/studio_raha/index.html',import.meta.url),'utf8');
const echo=readFileSync(new URL('../echoform/signal-lattice-r43.html',import.meta.url),'utf8');
test('R58 Ramadan: background blocks new campaign, in-memory resume and next mission',()=>{
 assert.match(game,/if\(document\.hidden\)\{toast\('برای شروع نبرد/);
 assert.match(game,/function resumeInMemoryCampaign\(\)\{if\(!hasResumableCampaignInMemory\(\)\|\|!canEnterGameplay\(graphicsUnavailable,document\.hidden\)\)return false/);
 assert.match(game,/function nextMission\(\)\{if\(!world\|\|!canEnterGameplay\(graphicsUnavailable,document\.hidden\)\)return/);
});
test('R58 ECHOFORM: freeze cancels active playback before BFCache',()=>{
 assert.match(echo,/document\.addEventListener\('freeze',\(\)=>pause\(/);
 assert.match(echo,/window\.addEventListener\('pageshow',e=>\{if\(e.persisted\)pause\(/);
 const scripts=[...echo.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
 assert.ok(scripts.length);scripts.forEach(x=>new Function(x[1]));
});
test('R58 Roham: runner suspends on freeze/pagehide/history and cleans listeners',()=>{
 for(const event of ['pagehide','pageshow'])assert.ok(roham.includes("window.addEventListener('"+event+"'"));
 assert.match(roham,/document\.addEventListener\('freeze',backgroundPause\)/);
 assert.match(roham,/document\.removeEventListener\('freeze',backgroundPause\)/);
 assert.match(roham,/function restoreFromHistory\(e\)\{if\(e.persisted\)backgroundPause\(\)\}/);
 const scripts=[...roham.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
 assert.ok(scripts.length);scripts.forEach(x=>new Function(x[1]));
});
