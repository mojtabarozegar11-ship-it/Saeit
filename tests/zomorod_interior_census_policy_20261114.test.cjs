'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {PAGES,assertExactPaths,classify,summarize}=
 require('../scripts/zomorod_interior_census_policy_20261114.cjs');
const ok=(path)=>({path,http:200,documentPath:path,censusComplete:true,
 attempts:[{ok:true,number:1}],blackBands:[]});
test('target list covers 23 unique real inner routes',()=>{
 assert.equal(assertExactPaths(PAGES),23);
 assert.equal(new Set(PAGES).size,23);
 assert.ok(PAGES.includes('/ghanadi/cafe-shiraz/'));
 assert.ok(!PAGES.includes('/'));
});
test('reject homepage, duplicates, malformed and empty target lists',()=>{
 for(const list of [[],['/'],['/about/','/about/'],['/../'],['about/']])
  assert.throws(()=>assertExactPaths(list));
});
test('all successful pages are 23/23, with no fabricated deployment',()=>{
 const s=summarize(PAGES.map(ok));
 assert.equal(s.inspected,23);
 assert.equal(s.http200,23);
 assert.equal(s.allRoutesInspected,true);
 assert.equal(s.liveWrites,0);
 assert.equal(s.gate,'NO_GO_UNLESS_ALL_INSPECTED');
});
test('one timeout is not counted as a verified page',()=>{
 const rows=PAGES.map(ok);rows[2]={path:PAGES[2],error:'TimeoutError',attempts:[{ok:false,number:1},{ok:false,number:2}]};
 const s=summarize(rows);
 assert.equal(s.inspected,22);
 assert.equal(s.fetchErrors,1);
 assert.equal(s.allRoutesInspected,false);
 assert.equal(s.failedRoutes[0].status,'UNKNOWN_FETCH_FAILED');
});
test('HTTP 500 is distinguished from timeout',()=>{
 const rows=PAGES.map(ok);rows[1]={path:PAGES[1],http:500,attempts:[{ok:false,number:1}]};
 const s=summarize(rows);
 assert.equal(s.non200,1);
 assert.equal(s.fetchErrors,0);
 assert.equal(s.http200,22);
});
test('HTTP 200 without a completed DOM inspection is not verified',()=>{
 const rows=PAGES.map(ok);rows[0].censusComplete=false;
 const s=summarize(rows);assert.equal(s.domIncomplete,1);
 assert.equal(s.allRoutesInspected,false);
});
test('unexpected redirect does not silently pass',()=>{
 const rows=PAGES.map(ok);rows[0].documentPath='/';
 const s=summarize(rows);assert.equal(s.redirected,1);
 assert.equal(s.allRoutesInspected,false);
});
test('transient failure is reported even if retry succeeds',()=>{
 const rows=PAGES.map(ok);
 rows[0].attempts=[{ok:false,number:1},{ok:true,number:2}];
 const s=summarize(rows);
 assert.equal(s.inspected,23);
 assert.deepEqual(s.transientFailures,[PAGES[0]]);
});
test('partial or reordered scan cannot claim full coverage',()=>{
 assert.throws(()=>summarize(PAGES.slice(1).map(ok)));
 const reversed=PAGES.slice().reverse().map(ok);
 assert.throws(()=>summarize(reversed));
});
test('black-band finding remains visible even on otherwise valid page',()=>{
 const rows=PAGES.map(ok);rows[0].blackBands=[{bg:'rgb(13,14,12)'}];
 const s=summarize(rows);
 assert.deepEqual(s.pathsWithBlackBands,[PAGES[0]]);
 assert.equal(s.allRoutesInspected,true);
});
test('classified failures are precise and never turned into HTTP 200',()=>{
 assert.equal(classify({path:'/about/',http:200,censusComplete:true}),'INSPECTED');
 assert.equal(classify({path:'/about/',error:'Timed out'}),'UNKNOWN_FETCH_FAILED');
 assert.equal(classify({path:'/about/',http:404}),'HTTP_NOT_200');
});
