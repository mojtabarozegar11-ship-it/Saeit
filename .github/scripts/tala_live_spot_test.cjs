const assert=require('node:assert/strict');
require('../../public/tala/assets/tala-live-spot.js');
const {interpret,OZ_GRAMS}=globalThis.TalaLiveSpot;
const now=Date.parse('2026-10-18T12:00:00Z');
const quote=(symbol,price,updatedAt)=>({symbol,currency:'USD',price,updatedAt});
let a=interpret(quote('XAU',4200,'2026-10-18T11:58:00Z'),'XAU',now);
assert.equal(a.stale,false);
assert.equal(a.usdPerGram,4200/OZ_GRAMS);
let b=interpret(quote('XAG',50,'2026-10-18T07:00:00Z'),'XAG',now);
assert.equal(b.stale,true);
for(const raw of [null,{},quote('XAG',4300,'2026-10-18T11:58:00Z'),quote('XAU',0,'2026-10-18T11:58:00Z'),quote('XAU',NaN,'2026-10-18T11:58:00Z'),quote('XAU',4200,'2026-10-18T12:10:00Z'),{...quote('XAU',4200,'2026-10-18T11:58:00Z'),currency:'IRR'}]){
  assert.throws(()=>interpret(raw,'XAU',now));
}
console.log('TALA_LIVE_SPOT_VALIDATION=passed');
