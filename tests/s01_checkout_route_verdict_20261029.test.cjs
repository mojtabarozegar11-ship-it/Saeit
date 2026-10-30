'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {classifyNavigation, assessAnonymousRouteRows} = require('../scripts/s01_checkout_route_verdict_20261029.cjs');
test('healthy public product route is anonymous GET only', () => {
  assert.deepEqual(classifyNavigation('/store/product/72/', 200, '/store/product/72/', null),
    {authRequired:false, unexpectedRedirect:false, observedSafe:true});
});
test('buyer checkout login redirect is not a completed purchase', () => {
  assert.deepEqual(classifyNavigation('/store/product/72/checkout/', 200, '/accounts/login/', null,
    '?next=%2Fstore%2Fproduct%2F72%2Fcheckout%2F'),
    {authRequired:true, unexpectedRedirect:false, observedSafe:true});
});
test('invoice history login redirect is expected, not invoice proof', () => {
  const v=classifyNavigation('/commerce/trx-easy/purchases/', 200, '/accounts/login/', null,
    '?next=%2Fcommerce%2Ftrx-easy%2Fpurchases%2F');
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

test('missing or ambiguous login return is not a usable buyer route', () => {
  const path='/store/product/72/checkout/';
  for (const search of ['', '?', '?campaign=ad', '?next=',
    '?next=%2Fstore%2Fproduct%2F72%2Fcheckout%2F&campaign=ad']) {
    const v=classifyNavigation(path,200,'/accounts/login/',null,search);
    assert.equal(v.observedSafe,false,search);
    assert.equal(v.unexpectedRedirect,true,search);
  }
});
test('canonical checkout redirected with an unexpected query is not a safe observation', () => {
  const v=classifyNavigation('/store/product/72/checkout/',200,
    '/store/product/72/checkout/',null,'?next=%2Fstore%2Fproduct%2F225%2Fcheckout%2F');
  assert.equal(v.observedSafe,false);
});

test('checkout observation matrix passes only exact complete SKU+device rows', () => {
  const paths=['/store/product/72/','/store/product/225/'];
  const devices=['mobile','desktop'];
  const rows=devices.flatMap(device=>paths.map(path=>({
    device,path,observedSafe:true,jsErrors:[],checkoutLinks:1,mismatchedCheckoutLinks:0
  })));
  assert.deepEqual(assessAnonymousRouteRows(rows,paths,devices),{complete:true,failures:[]});
  assert.equal(assessAnonymousRouteRows(rows.slice(1),paths,devices).complete,false);
  assert.ok(assessAnonymousRouteRows([...rows,rows[0]],paths,devices).failures.some(
    x=>x.startsWith('DUPLICATE_ROW:')));
});
test('checkout matrix reveals cross-SKU CTA without a false delivery claim', () => {
  const path='/store/product/72/';
  const rows=[{device:'mobile',path,observedSafe:true,jsErrors:[],
    checkoutLinks:1,mismatchedCheckoutLinks:1}];
  const verdict=assessAnonymousRouteRows(rows,[path],['mobile']);
  assert.equal(verdict.complete,false);
  assert.deepEqual(verdict.failures,['MISMATCHED_SKU_CHECKOUT_CTA:mobile:'+path]);
  rows[0].mismatchedCheckoutLinks=0;
  rows[0].checkoutLinks=0;
  assert.deepEqual(assessAnonymousRouteRows(rows,[path],['mobile']).failures,
    ['NO_USABLE_SKU_CHECKOUT_CTA:mobile:'+path]);
});
test('checkout matrix rejects safe-looking HTTP with JS errors or unknown row', () => {
  const path='/store/product/879/';
  const row={device:'desktop',path,observedSafe:true,jsErrors:['TypeError'],
    checkoutLinks:1,mismatchedCheckoutLinks:0};
  assert.ok(assessAnonymousRouteRows([row],[path],['desktop']).failures.some(
    x=>x.startsWith('JS_ERRORS:')));
  row.jsErrors=[];
  row.observedSafe=false;
  assert.ok(assessAnonymousRouteRows([row],[path],['desktop']).failures.some(
    x=>x.startsWith('UNSAFE_NAVIGATION:')));
});
