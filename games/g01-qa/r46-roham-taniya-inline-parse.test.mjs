import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Script} from 'node:vm';

function inlineScript(path) {
 const html=readFileSync(new URL(path,import.meta.url),'utf8');
 const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
 assert.equal(scripts.length,1,'exactly one inline script expected');
 new Script(scripts[0][1],{filename:path}); // Compile only; no DOM or payment actions.
 return scripts[0][1];
}

test('Roham Super Jungle Run JavaScript parses and visibility lifecycle is callable',()=>{
 const source=inlineScript('../../templates/studio_raha/index.html');
 assert.match(source,/function runnerGame\(stage\)/);
 assert.match(source,/function resumeVisible\(\)/);
 assert.match(source,/function visibility\(\)/);
 assert.doesNotMatch(source,/\\n function resumeVisible/);
});

test('Taniya Cake Maker exports selected frosting, candle and visual topping',()=>{
 const source=inlineScript('../../templates/taniya_studio/index.html');
 assert.match(source,/function mountCake\(\)/);
 assert.match(source,/const topperShapes=\{/);
 for(const name of ['🍓','🌼','🍬']) assert.ok(source.includes("'"+name+"':"),name);
 assert.ok(source.includes("'+topperShapes[topping]+candleShapes+'"));
 assert.ok(source.includes("downloadSvg('taniya-custom-cake',body)"));
});
