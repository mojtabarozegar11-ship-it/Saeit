'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const games=['beacon-labyrinth','cipher-garden','nebula-salvage','pulse-forge','skyline-keeper'];
for(const name of games){
 const html=fs.readFileSync('site_releases/mojplaywin/games-20261021/'+name+'/index.html','utf8');
 const scripts=[...html.matchAll(/(<script\b[^>]*>)([\s\S]*?)<\/script>/g)];
 for(const m of scripts)if(!m[1].includes('application/ld+json'))new vm.Script(m[2],{filename:name+'.js'});
 const begin=html.indexOf('const saveKey='),api=html.indexOf('const api=',begin);
 const score=html.indexOf('score(n){',api),level=html.indexOf('level(v){',score);
 assert(begin>=0&&api>begin&&score>api&&level>score,name+' runtime contract missing');
 const init=html.slice(begin,api),method=html.slice(score,level);
 function exercise(stored,calls){
  const writes=new Map();
  const context={localStorage:{getItem(){return stored},setItem(k,v){writes.set(k,v)}},hudBest:{textContent:''},hudScore:{textContent:''}};
  const output=vm.runInNewContext(init+'const api={'+method+'};'+calls+'({score,best,scoreText:hudScore.textContent,bestText:hudBest.textContent})',context);
  return {output,writes};
 }
 for(const bad of ['Infinity','NaN','-900','1e300']){
  const {output,writes}=exercise(bad,'api.score(Infinity);api.score(NaN);api.score(-1);api.score(50);');
  assert.equal(output.score,50,name+' must reject corrupt score events');
  assert.equal(output.best,50,name+' must recover from corrupt stored best');
  assert.equal([...writes.values()][0],'50',name+' must persist recovered best');
 }
 const valid=exercise('120','api.score(50);');
 assert.equal(valid.output.best,120,name+' must preserve legitimate record');
 assert.equal(valid.writes.size,0,name+' must not overwrite a higher record');
 const capped=exercise('0','api.score(1e30);');
 assert.equal(capped.output.score,1000000000,name+' must cap impossible scoring overflow');
}
console.log('ARCADE_SCORE_INTEGRITY_PASS: 5 games, malformed saves, invalid scoring, best preservation and cap');
