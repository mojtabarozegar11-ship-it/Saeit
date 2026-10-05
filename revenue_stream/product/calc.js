(function(root){'use strict';
const units={g:['mass',1],kg:['mass',1000],ml:['volume',1],l:['volume',1000],each:['count',1]};
function number(v,min=0,max=1e12){const n=Number(v);if(!Number.isFinite(n)||n<min||n>max)throw Error('invalid_number');return n;}
function calculate(r){
 const portions=number(r.portions,1,100000),fee=number(r.fee,0,99)/100,margin=number(r.margin,0,99)/100;
 if(fee+margin>=1)throw Error('fee_plus_margin');
 if(!Array.isArray(r.ingredients)||!r.ingredients.length||r.ingredients.length>50)throw Error('ingredients_required');
 const lines=r.ingredients.map(i=>{const a=units[i.buyUnit],b=units[i.useUnit];if(!a||!b||a[0]!==b[0])throw Error('unit_mismatch');
  const pack=number(i.buyQty,.000001),price=number(i.price),quantity=number(i.useQty),yieldRate=number(i.yield,.01,100)/100;
  return {name:String(i.name||'').slice(0,100),cost:quantity*b[1]/(pack*a[1]*yieldRate)*price};});
 const ingredients=lines.reduce((s,i)=>s+i.cost,0),packaging=number(r.packaging)*portions,labor=number(r.labor),delivery=number(r.delivery),overhead=number(r.overhead);
 const cost=ingredients+packaging+labor+delivery+overhead;if(cost<=0)throw Error('cost_required');
 const suggested=cost/(1-fee-margin),sale=number(r.sale)||suggested,commission=sale*fee,contribution=sale-commission-cost;
 const result={lines,ingredients,packaging,labor,delivery,overhead,cost,perPortion:cost/portions,suggested,suggestedPortion:suggested/portions,sale,commission,contribution,margin:contribution/sale*100,stressContribution:contribution-ingredients*.1,portions};
 if(Object.values(result).some(v=>typeof v==='number'&&(!Number.isFinite(v)||Math.abs(v)>9e15)))throw Error('result_out_of_range');return result;
}
function validate(r){if(!r||typeof r!=='object')throw Error('invalid_recipe');calculate(r);return {name:String(r.name||'Recipe').slice(0,100),currency:['IRT','IRR','USD','EUR','AED'].includes(r.currency)?r.currency:'IRT',portions:number(r.portions,1,100000),fee:number(r.fee,0,99),margin:number(r.margin,0,99),packaging:number(r.packaging),labor:number(r.labor),delivery:number(r.delivery),overhead:number(r.overhead),sale:number(r.sale),ingredients:r.ingredients.map(i=>({name:String(i.name||'').slice(0,100),buyQty:number(i.buyQty,.000001),buyUnit:i.buyUnit,price:number(i.price),useQty:number(i.useQty),useUnit:i.useUnit,yield:number(i.yield,.01,100)}))};}
function csvCell(v){let s=String(v);if(/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}
const api={calculate,validate,csvCell};if(typeof module!=='undefined')module.exports=api;root.CostKit=api;
})(typeof globalThis!=='undefined'?globalThis:this);
