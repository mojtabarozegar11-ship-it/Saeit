'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('games/crown-defender/index.html','utf8');
const start=source.indexOf('function equipJet(){'),end=source.indexOf('\nfunction trialFlight()',start);
assert.ok(start>=0&&end>start,'Crown equip function missing');
const fn=source.slice(start,end);
function run(persistResults,fleetResults){
 const messages=[],storedCredits=[];
 const ctx={previewJet:'raptor',fleetPending:false,fleetById:()=>({id:'raptor',name:'R-07 Raptor',cost:450}),ownedJet:()=>false,save:{credits:1000},bank:1000,fleetSave:{jets:['falcon'],selected:'falcon'},selectedJet:'falcon',activeJet:'falcon',trialJet:false,
 persist:()=>{storedCredits.push(ctx.save.credits);return persistResults.shift()??true;},
 persistFleet:()=>fleetResults.shift()??true,fleetMessage:s=>messages.push(s),fleetCards:()=>{},$:()=>({textContent:''}),fmt:n=>String(n)};
 vm.createContext(ctx);vm.runInContext(fn+'\nthis.run=equipJet;',ctx);
 return {ok:ctx.run(),credits:ctx.save.credits,jets:Array.from(ctx.fleetSave.jets),selected:ctx.fleetSave.selected,messages,storedCredits};
}
test('failed credit persistence does not unlock or spend earned credits',()=>{
 const r=run([false],[]);assert.equal(r.ok,false);assert.equal(r.credits,1000);assert.deepEqual(r.jets,['falcon']);assert.match(r.messages.at(-1),/Unlock canceled/);
});
test('failed fleet write refunds earned credits and cancels unlock',()=>{
 const r=run([true,true],[false]);assert.equal(r.ok,false);assert.equal(r.credits,1000);assert.deepEqual(r.jets,['falcon']);assert.deepEqual(r.storedCredits,[550,1000]);assert.match(r.messages.at(-1),/credits restored/);
});
test('successful earned-credit unlock still equips owned jet',()=>{
 const r=run([true],[true,true]);assert.equal(r.ok,true);assert.equal(r.credits,550);assert.deepEqual(r.jets,['falcon','raptor']);assert.equal(r.selected,'raptor');
});
