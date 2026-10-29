"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");
const E = require("./greenhouse_engine.js");

const sample = {
  project:"Reference case",crop:"Tomato",season:"Spring",region:"Example",currency:"USD",
  areaM2:1000,yieldKgM2:12,rejectionPct:10,priceKg:2.5,cyclesYear:2,years:5,
  initialInvestment:50000,fixedAnnual:10000,waterLitersM2:100,waterPriceLiter:0.01,
  energyKwhM2:10,energyPriceKwh:0.2,climateKwhM2:5,climatePriceKwh:0.2,
  laborHoursM2:0.5,laborPriceHour:8,otherVariableM2:7,
  packagingKg:0.1,logisticsKg:0.05,discountPct:12,revenueGrowthPct:0,costGrowthPct:3,
  yieldMin:8,yieldMax:16,priceMin:2,priceMax:3,riskSeed:20261029
};
test("Reference case reconciles all component costs and cash flow", () => {
  const r=E.calculate(sample);
  assert.equal(r.cycle.grossKg,12000);
  assert.equal(r.cycle.saleableKg,10800);
  assert.equal(r.cycle.revenue,27000);
  assert.deepEqual(r.cycle.breakdown,{
    water:1000,energy:2000,climate:1000,labor:4000,other:7000,packaging:1080,logistics:540
  });
  assert.equal(r.cycle.variableCost,16620);
  assert.equal(r.cycle.cycleMargin,5380);
  assert.equal(r.yearOne.revenue,54000);
  assert.equal(r.yearOne.variableCost,33240);
  assert.equal(r.yearOne.netCashFlow,10760);
  assert.equal(r.yearOne.cumulativeCashFlow,-39240);
  assert.equal(r.breakEven.pricePerKg,2.01);
  assert.equal(r.breakEven.grossYieldKgM2,9.457);
  assert.equal(r.financials.years.length,5);
  assert.equal(r.stress.length,9);
});
test("Conservative price threshold does not understate true break-even", () => {
  const r=E.calculate(sample), required=r.cycle.variableCost+r.cycle.allocatedFixedCost;
  assert.ok(r.breakEven.pricePerKg*r.cycle.saleableKg+1e-7>=required);
  assert.ok((r.breakEven.pricePerKg-0.01)*r.cycle.saleableKg<required);
});
test("Conservative yield threshold accounts for per-kg costs", () => {
  const r=E.calculate(sample);
  const p=sample;
  const y=r.breakEven.grossYieldKgM2;
  const resource=15000, fixed=5000, contribution=p.priceKg-p.packagingKg-p.logisticsKg;
  assert.ok(p.areaM2*y*(1-p.rejectionPct/100)*contribution+1e-7>=resource+fixed);
});
test("Unreachable economics are represented as null thresholds", () => {
  const r=E.calculate({...sample,rejectionPct:100});
  assert.equal(r.breakEven.pricePerKg,null);
  assert.equal(r.breakEven.grossYieldKgM2,null);
  assert.equal(r.cycle.saleableKg,0);
});
test("Break-even cannot be attained with negative per-unit contribution", () => {
  const r=E.calculate({...sample,priceKg:0.10,priceMin:0});
  assert.equal(r.breakEven.grossYieldKgM2,null);
});
test("Risk simulation is deterministic, bounded and explicitly uncalibrated", () => {
  const one=E.calculate(sample),two=E.calculate(sample);
  assert.deepEqual(one.risk,two.risk);
  assert.equal(one.risk.simulations,2000);
  assert.match(one.risk.method,/NOT a market probability/);
  assert.ok(one.risk.p05<one.risk.median&&one.risk.median<one.risk.p95);
});
test("No risk simulation with all bounds empty",()=>{
  const p={...sample};["yieldMin","yieldMax","priceMin","priceMax"].forEach(k=>delete p[k]);
  assert.equal(E.calculate(p).risk,null);
});
test("Reject incomplete and inconsistent risk bounds",()=>{
  const p={...sample};delete p.yieldMax;
  assert.throws(()=>E.calculate(p),/all four/);
  assert.throws(()=>E.calculate({...sample,yieldMin:13}),/contain expected/);
});
test("Reject invalid or unrealistic critical inputs",()=>{
  for(const [k,v] of [["areaM2",0],["areaM2",-1],["priceKg",-3],
    ["rejectionPct",120],["years",1.5],["cyclesYear",0],["waterPriceLiter","NaN"],
    ["initialInvestment",Infinity],["currency","<script>"]]){
    assert.throws(()=>E.calculate({...sample,[k]:v}),undefined,k);
  }
});
test("Reject missing fields and object abuse",()=>{
  assert.throws(()=>E.calculate([]),/object/);
  assert.throws(()=>E.calculate({...sample,project:""}),/project/);
  assert.throws(()=>E.calculate({...sample,region:"evil\nheader"}),/region/);
});
test("Economic invariants hold over independent user cases",()=>{
  for(let i=1;i<=128;i++){
    const p={...sample,areaM2:100+i,yieldKgM2:3+i/10,
      priceKg:1+i/100,fixedAnnual:1000+i*2,rejectionPct:(i%20),
      yieldMin:0,yieldMax:100,priceMin:0,priceMax:100};
    const a=E.calculate(p),morePrice=E.calculate({...p,priceKg:p.priceKg+1}),
      moreCost=E.calculate({...p,fixedAnnual:p.fixedAnnual+100}),
      moreReject=E.calculate({...p,rejectionPct:p.rejectionPct+1});
    assert.ok(morePrice.yearOne.netCashFlow>=a.yearOne.netCashFlow);
    assert.ok(Math.abs(moreCost.yearOne.netCashFlow-a.yearOne.netCashFlow+100)<1e-6);
    assert.ok(moreReject.yearOne.netCashFlow<=a.yearOne.netCashFlow+1e-6);
  }
});
test("Cumulative cash flows include year-zero capital and NPV discounts",()=>{
  const p={...sample,years:1,discountPct:0,revenueGrowthPct:0,costGrowthPct:0};
  const r=E.calculate(p);
  assert.equal(r.financials.npv,r.yearOne.netCashFlow-p.initialInvestment);
  assert.equal(r.financials.years[0].cumulativeCashFlow,r.financials.npv);
});
test("Zero capital yields no artificial infinite ROI",()=>{
  const r=E.calculate({...sample,initialInvestment:0});
  assert.equal(r.financials.roiPct,null);assert.equal(r.financials.paybackYears,0);
});
test("Single-file browser distribution contains the identical audited engine",()=>{
  const html=fs.readFileSync(path.join(__dirname,"greenhouse_economics_studio.html"),"utf8");
  const engine=fs.readFileSync(path.join(__dirname,"greenhouse_engine.js"),"utf8");
  const match=html.match(/<script id="model-source">\s*([\s\S]*?)\s*<\/script>/);
  assert.ok(match,"The offline HTML must embed its engine");
  assert.equal(match[1].trim(),engine.trim(),"HTML model must match audited source byte for byte");
  assert.match(html,/lang="en"/);assert.match(html,/connect-src 'none'/);
  assert.doesNotMatch(html,/<script[^>]+src="https?:/);
  const context={module:{exports:{}}};
  vm.runInNewContext(match[1],context,{timeout:1000});
  assert.equal(context.module.exports.calculate(sample).cycle.cycleMargin,5380);
});

test("Offline English UI works for comparison exports, reset, CSV and JSON import",()=>{
  const html=fs.readFileSync(path.join(__dirname,"greenhouse_economics_studio.html"),"utf8");
  const matched=html.match(/<script>\s*([\s\S]*?)\s*<\/script>\s*<\/body>/);
  assert.ok(matched,"customer UI script must exist");
  const nodes=new Map(), downloaded=[];
  function node(tag){
    const listeners={};
    const n={tagName:tag,value:"",files:[],children:[],textContent:"",className:"",
      appendChild(child){this.children.push(child);return child;},
      replaceChildren(...items){this.children=items;},
      addEventListener(kind,handler){listeners[kind]=handler;},
      fire(kind,event){assert.ok(listeners[kind],this._id+" missing "+kind);return listeners[kind](event||{target:this});},
      click(){if(listeners.click)listeners.click({target:this});},
      remove(){}};
    Object.defineProperty(n,"id",{get(){return this._id;},set(v){this._id=v;nodes.set(v,this);}});
    Object.defineProperty(n,"value",{get(){return this._value===undefined?"":this._value;},set(v){this._value=String(v);}});
    return n;
  }
  for(const [,id] of html.matchAll(/\bid="([^"]+)"/g)){if(!nodes.has(id)){const el=node("div");el.id=id;}}
  const document={getElementById(id){return nodes.get(id);},createElement:node,body:node("body")};
  class MemoryBlob{constructor(parts,options){this.body=parts.join("");this.mime=options.type;}}
  class MemoryReader{readAsText(file){this.result=file.content;this.onload();}}
  let prints=0;
  const context={document,GreenhouseEngine:E,Blob:MemoryBlob,FileReader:MemoryReader,
    URL:{createObjectURL(blob){downloaded.push(blob);return "blob:memory";},revokeObjectURL(){}},
    window:{print(){prints++;}},setTimeout(fn){fn();}};
  context.globalThis=context;
  vm.runInNewContext(matched[1],context,{timeout:5000});
  const byId=id=>{const item=nodes.get(id);assert.ok(item,id+" missing");return item;};
  const click=id=>byId(id).fire("click");
  assert.equal(byId("metrics").children.length,9,byId("status").textContent||"sample calculates on open");
  click("export-compare");
  assert.match(byId("status").textContent,/No saved comparisons/);
  click("save");
  assert.equal(byId("comparison").children.length,1);
  byId("f-project").value="Second greenhouse";
  click("save");
  assert.equal(byId("comparison").children.length,2);
  click("export-compare");
  assert.match(downloaded.at(-1).body,/Second greenhouse/);
  assert.match(downloaded.at(-1).body,/Year-one net operating cash/);
  click("clear-compare");
  assert.equal(byId("comparison").children.length,0);
  click("export-compare");
  assert.match(byId("status").textContent,/No saved comparisons/);

  byId("f-project").value="=1+2";
  click("export-csv");
  assert.match(downloaded.at(-1).body,/'=1\+2/,"spreadsheet formula must be escaped");
  assert.match(downloaded.at(-1).body,/Cycle water cost/);
  assert.match(downloaded.at(-1).body,/Model scope/);
  click("export-json");
  assert.match(downloaded.at(-1).body,/"schema": "F28\/3"/);
  click("print");
  assert.equal(prints,1);

  byId("f-areaM2").value="-1";
  click("run");
  assert.equal(byId("metrics").children.length,0,"old financial results must disappear on invalid input");
  assert.equal(byId("cash").children.length,0);
  assert.match(byId("status").textContent,/Results cleared/);
  click("restore");
  assert.equal(byId("metrics").children.length,9);

  const input=byId("import-file");
  input.files=[{size:120,content:JSON.stringify({schema:"F28/3",scenario:{...sample,project:"Imported reference case"}})}];
  input.fire("change",{target:input});
  assert.equal(byId("f-project").value,"Imported reference case");
  assert.match(byId("status").textContent,/imported and validated/);
  assert.equal(byId("metrics").children.length,9);

  input.files=[{size:50,content:'{"scenario":{"areaM2":-1}}'}];
  input.fire("change",{target:input});
  assert.match(byId("status").textContent,/Import failed/);
  assert.equal(byId("f-project").value,"Imported reference case","invalid import cannot replace valid inputs");
});
