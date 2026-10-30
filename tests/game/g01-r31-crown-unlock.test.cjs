const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../../games/crown-defender/index.html'),'utf8');
const start=html.indexOf('function equipJet(){'),end=html.indexOf('function trialFlight(){',start);
assert.ok(start>0&&end>start,'real Crown equipJet source exists');
const source=html.slice(start,end);
function scenario(profileOK,fleetOK){
 const events=[],ctx={
  fleetById:id=>({id,name:'Test Jet',cost:50}),previewJet:'newjet',fleetPending:false,ownedJet:()=>false,
  save:{credits:100},bank:100,fleetSave:{jets:[],selected:'falcon'},
  persist:()=>{events.push('profile');return profileOK},
  persistFleet:()=>{events.push('fleet');return fleetOK},
  fleetMessage:s=>events.push(s),fleetCards:()=>{},fmt:n=>String(n),
  $:()=>({textContent:''}),selectedJet:'falcon',activeJet:'falcon',trialJet:false
 };
 vm.createContext(ctx);vm.runInContext(source+';this.execute=equipJet;',ctx);
 return {ok:ctx.execute(),ctx,events};
}
test('earned-credit jet unlock is cancelled when profile storage fails',()=>{
 const {ok,ctx,events}=scenario(false,true);
 assert.equal(ok,false);assert.equal(ctx.save.credits,100);assert.equal(ctx.bank,100);
 assert.equal(ctx.fleetSave.jets.length,0);assert.equal(ctx.selectedJet,'falcon');
 assert.ok(events.some(x=>String(x).includes('cancelled')));
});
test('earned-credit jet unlock is compensated when fleet storage fails',()=>{
 const {ok,ctx}=scenario(true,false);
 assert.equal(ok,false);assert.equal(ctx.save.credits,100);assert.equal(ctx.fleetSave.jets.length,0);
});
test('successful earned-credit unlock charges once and equips',()=>{
 const {ok,ctx}=scenario(true,true);
 assert.equal(ok,true);assert.equal(ctx.save.credits,50);
 assert.deepEqual(Array.from(ctx.fleetSave.jets),['newjet']);assert.equal(ctx.selectedJet,'newjet');
});
