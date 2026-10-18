const assert=require('node:assert/strict');
require('../../public/tala/assets/tala-calculator.js');
const {calculate,number,norm}=globalThis.TalaCalc;
const ordinary=calculate({weight:2,purity:750,rate:100000000,laborPct:0,profitPct:0,taxPct:10});
assert.equal(ordinary.material,200000000);
assert.equal(ordinary.total,200000000);
assert.equal(ordinary.tax,0);
const luxury=calculate({weight:2,purity:750,rate:100000000,laborPct:10,profitPct:7,taxPct:10,gem:30000000,extra:5000000,laborPerGram:1000000});
assert.equal(luxury.material,200000000);
assert.equal(luxury.labor,27000000);
assert.equal(luxury.profit,15890000);
assert.equal(luxury.tax,4289000);
assert.equal(luxury.total,277179000);
const pure=calculate({weight:1,purity:999.9,rate:75000000});
assert(Math.abs(pure.material-99990000)<1);
assert.equal(norm('۱۲٬۳۴۵٫۶'), '12345.6');
assert.equal(number('۱۰۰٫۵',1000,'test'),100.5);
for(const invalid of [
 {weight:0,purity:750,rate:1000},
 {weight:1,purity:0,rate:1000},
 {weight:1,purity:750,rate:-10},
 {weight:1,purity:750,rate:'10e6'},
 {weight:1,purity:750,rate:100,gem:-1},
 {weight:1,purity:750,rate:100,profitPct:101},
 {weight:1,purity:750,rate:100,taxPct:-1}
]) assert.throws(()=>calculate(invalid));
assert.equal(calculate({weight:'۱٫۵',purity:750,rate:'۱۰۰۰۰۰'}).total,150000);
console.log('TALA_GOLD_JEWELRY_CALC_TEST=passed');
