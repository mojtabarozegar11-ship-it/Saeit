'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {classifyNavigation} = require('../scripts/s01_checkout_route_verdict_20261029.cjs');
test('healthy public product route is anonymous GET only', () => {
  assert.deepEqual(classifyNavigation('/store/product/72/', 200, '/store/product/72/', null),
    {authRequired:false, unexpectedRedirect:false, observedSafe:true});
});
test('buyer checkout login redirect is not a completed purchase', () => {
  assert.deepEqual(classifyNavigation('/store/product/72/checkout/', 200, '/accounts/login/', null),
    {authRequired:true, unexpectedRedirect:false, observedSafe:true});
});
test('invoice history login redirect is expected, not invoice proof', () => {
  const v=classifyNavigation('/commerce/trx-easy/purchases/', 200, '/accounts/login/', null);
  assert.equal(v.authRequired,true);
  assert.equal(v.observedSafe,true);
});
test('unexpected external redirect fails closed even with HTTP 200', () => {
  const v=classifyNavigation('/store/product/72/checkout/',200,'[external-redirect]',null);
  assert.equal(v.unexpectedRedirect,true);
  assert.equal(v.observedSafe,false);
});
test('unexpected internal redirect fails closed', () => {
  const v=classifyNavigation('/store/product/72/checkout/',200,'/store/',null);
  assert.equal(v.unexpectedRedirect,true);
  assert.equal(v.observedSafe,false);
});
test('HTTP 500, 404, and navigation error never pass', () => {
  for(const status of [0,404,500]) {
    assert.equal(classifyNavigation('/store/',status,'/store/',null).observedSafe,false);
  }
  assert.equal(classifyNavigation('/store/',200,'/store/','TimeoutError').observedSafe,false);
});

test('redirect-only HTTP statuses cannot count as observed safe pages', () => {
  for (const status of [301,302,303,307,308,399]) {
    const v=classifyNavigation('/store/product/72/checkout/',status,'/accounts/login/',null);
    assert.equal(v.authRequired,true);
    assert.equal(v.observedSafe,false);
  }
});
test('invalid or noninteger status cannot pass', () => {
  for (const status of [null,undefined,NaN,'200',200.5,-1]) {
    assert.equal(classifyNavigation('/store/',status,'/store/',null).observedSafe,false);
  }
});

test('login next query must return to the same SKU checkout', () => {
  const path='/store/product/72/checkout/';
  const good=classifyNavigation(path,200,'/accounts/login/',null,'?next=%2Fstore%2Fproduct%2F72%2Fcheckout%2F');
  assert.equal(good.observedSafe,true);
  const wrong=classifyNavigation(path,200,'/accounts/login/',null,'?next=%2Fstore%2Fproduct%2F225%2Fcheckout%2F');
  assert.equal(wrong.authRequired,true);
  assert.equal(wrong.unexpectedRedirect,true);
  assert.equal(wrong.observedSafe,false);
});
test('external and duplicate login return targets fail closed', () => {
  const path='/store/product/72/checkout/';
  for(const search of ['?next=https%3A%2F%2Fevil.example%2F','?next=%2Fstore%2Fproduct%2F72%2Fcheckout%2F&next=%2Fstore%2F']) {
    assert.equal(classifyNavigation(path,200,'/accounts/login/',null,search).observedSafe,false);
  }
});
