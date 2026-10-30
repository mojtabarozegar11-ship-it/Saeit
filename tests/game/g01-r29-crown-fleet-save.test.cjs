'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('games/crown-defender/index.html','utf8');
const start=source.indexOf('function persistFleet(){'),end=source.indexOf('\nfunction ownedJet(',start);
assert.ok(start>=0&&end>start,'Fleet persistence function missing');
const fn=source.slice(start,end);
function invoke(storage){const messages=[];const ctx={fleetSave:{jets:['falcon','raptor'],selected:'raptor'},localStorage:storage,fleetMessage:m=>messages.push(m)};vm.createContext(ctx);vm.runInContext(fn+'\nthis.run=persistFleet;',ctx);return {ok:ctx.run(),messages}}
test('Crown fleet persistence verifies actual readback',()=>{const store=new Map();const result=invoke({setItem:(k,v)=>store.set(k,v),getItem:k=>store.get(k)});assert.equal(result.ok,true);assert.equal(result.messages.length,0);assert.equal(JSON.parse(store.get('mpw-crown-fleet-v120')).selected,'raptor')});
test('Crown fleet persistence rejects silent storage drops',()=>{const result=invoke({setItem:()=>{},getItem:()=>null});assert.equal(result.ok,false);assert.match(result.messages[0],/could not be saved/)});
test('Crown fleet persistence rejects quota exceptions',()=>{const result=invoke({setItem:()=>{throw Error('QuotaExceeded')},getItem:()=>null});assert.equal(result.ok,false);assert.match(result.messages[0],/could not be saved/)});
test('Crown equip HUD does not claim durable equip on failed fleet save',()=>{assert.match(source,/const fleetSaved=persistFleet\(\)/);assert.match(source,/equipped for this session only; browser fleet storage failed/)});
