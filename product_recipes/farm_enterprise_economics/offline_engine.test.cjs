'use strict';
const assert = require('node:assert/strict');
const Engine = require('./offline_engine.js');

const orchard = {
  name:'Illustrative Orchard',
  units_sold:'1000',
  unit_price:'10',
  variable_cost_per_unit:'4',
  allocated_fixed_cost:'3000',
  selling_fee_percent:'5'
};
function evaluate(...enterprises) {
  return Engine.evaluate({currency:'USD', enterprises});
}
const one = evaluate(orchard);
assert.equal(one.results[0].break_even_units, 546);
assert.equal(one.results[0].margin_of_safety_units, '454');
assert.equal(one.results[0].margin_of_safety_percent, '45.40');
assert.equal(one.results[0].contribution_margin_percent, '55.00');
assert.equal(one.results[0].operating_profit_margin_percent, '25.00');
assert.equal(one.portfolio.contribution_margin_percent, '55.00');
assert.equal(one.portfolio.operating_profit_margin_percent, '25.00');

const another = {
  name:'Small market crop', units_sold:'50', unit_price:'100',
  variable_cost_per_unit:'20', allocated_fixed_cost:'1000'
};
const both = evaluate(orchard, another);
assert.equal(both.portfolio.sales_revenue,'15000.00');
assert.equal(both.portfolio.operating_profit,'5500.00');
assert.equal(both.portfolio.contribution_margin_total,'9500.00');
assert.equal(both.portfolio.contribution_margin_percent,'63.33');
assert.equal(both.portfolio.operating_profit_margin_percent,'36.67');

const idle = evaluate({name:'Idle farm',units_sold:'0',unit_price:'100',
  variable_cost_per_unit:'10',allocated_fixed_cost:'800'});
assert.equal(idle.portfolio.operating_profit,'-800.00');
assert.equal(idle.results[0].contribution_margin_percent,null);
assert.equal(idle.results[0].operating_profit_margin_percent,null);
assert.equal(idle.portfolio.contribution_margin_percent,null);
assert.equal(idle.portfolio.operating_profit_margin_percent,null);

for (const name of ['Wheat\u202e=100','Rice\u2066hidden\u2069',
  'Corn\u2028=cmd','Oat\u200fFake','Soy\u061cNote','Barley\u2029Line']) {
  assert.throws(() => evaluate({...orchard,name}), /control/i);
}
const farsi = evaluate({...orchard,name:'گندم\u200cدیم'});
assert.equal(farsi.results[0].name,'گندم\u200cدیم');

console.log('FARM_ECONOMICS_PYTHON_BROWSER_PARITY_AND_REPEATING_DECIMAL=PASS');
