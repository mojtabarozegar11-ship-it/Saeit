'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {classifyControl}=require('./g01_s01_checkout_a11y_r27.cjs');
const base={tag:'A',text:'Checkout',href:'/checkout/',ariaLabel:'',title:'',id:'',disabled:false};
test('real checkout link is not marked broken',()=>assert.deepEqual(classifyControl(base).issues,[]));
test('placeholder checkout link is flagged without clicking',()=>assert.deepEqual(classifyControl({...base,href:'#'}).issues,['NON_NAVIGABLE_CHECKOUT_LINK']));
test('unnamed checkout button is flagged',()=>assert.ok(classifyControl({...base,tag:'BUTTON',text:'',id:'checkoutBtn',href:''}).issues.includes('MISSING_ACCESSIBLE_NAME')));
test('conflicting disabled state is flagged',()=>assert.ok(classifyControl({...base,disabled:true,ariaDisabled:'false'}).issues.includes('CONFLICTING_DISABLED_STATE')));
test('noncommerce controls ignored',()=>assert.equal(classifyControl({...base,text:'About',href:'/about/'}),null));
