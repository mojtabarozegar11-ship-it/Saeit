'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {classifyNavigation, assessAnonymousRouteRows, isDirectCheckoutHref, redactObservedHref} = require('../scripts/s01_checkout_route_verdict_20261029.cjs');
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
test('anonymous purchases route accepts only deliberate same-path session denial, never a receipt page', () => {
  const path='/commerce/trx-easy/purchases/';
  const denied=classifyNavigation(path,404,path,null);
  assert.deepEqual(denied,{authRequired:true,unexpectedRedirect:false,observedSafe:true});
  const page=classifyNavigation(path,200,path,null);
  assert.deepEqual(page,{authRequired:true,unexpectedRedirect:true,observedSafe:false});
  assert.equal(classifyNavigation(path,404,'/store/',null).observedSafe,false);
  assert.equal(classifyNavigation(path,404,path,'TimeoutError').observedSafe,false);
  assert.equal(classifyNavigation(path,500,path,null).observedSafe,false);
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

test('registration next=checkout is not a direct or mismatched checkout CTA', () => {
  assert.equal(isDirectCheckoutHref('/accounts/register/?next=/store/product/72/checkout/'),false);
  assert.equal(isDirectCheckoutHref('/accounts/register/?next=%2Fstore%2Fproduct%2F225%2Fcheckout%2F'),false);
  assert.equal(isDirectCheckoutHref('/store/product/72/checkout/'),true);
  assert.equal(isDirectCheckoutHref('/store/product/225/checkout/'),true);
  assert.equal(isDirectCheckoutHref('/store/product/72/checkout/?next=/store/'),false);
  assert.equal(isDirectCheckoutHref('https://evil.example/store/product/72/checkout/'),false);
});

test('redacts signed checkout URLs and fragments before CI artifact serialization', () => {
  const raw='/store/product/72/checkout/?token=secret-123&next=%2Fstore%2F#session=secret';
  const safe=redactObservedHref(raw);
  assert.equal(safe,'/store/product/72/checkout/?[redacted]#[redacted]');
  assert.ok(!JSON.stringify({href:safe}).includes('secret-123'));
  assert.equal(isDirectCheckoutHref(raw),false); // do not misclassify queried CTA
  assert.equal(isDirectCheckoutHref(safe),false);
});
test('preserves canonical SKU CTA and rejects external control destinations', () => {
  assert.equal(redactObservedHref('/store/product/879/checkout/'),'/store/product/879/checkout/');
  assert.equal(redactObservedHref('/accounts/register/?next=%2Fstore%2Fproduct%2F879%2Fcheckout%2F'),
    '/accounts/register/?[redacted]');
  assert.equal(redactObservedHref('[external]'),'[external]');
  assert.equal(redactObservedHref('//evil.example/?token=abc'),'[invalid]');
  assert.equal(redactObservedHref(null),null);
});


test('never serializes unknown path-embedded access tokens', () => {
  for (const value of [
    '/private-download/bearer-SECRET123',
    '/store/product/72/checkout/token-SECRET123/',
    '/store/product/999/checkout/?key=SECRET123',
    '/%2Fprivate-download%2FSECRET123'
  ]) {
    const safe=redactObservedHref(value);
    assert.equal(safe,'[redacted-path]');
    assert.ok(!safe.includes('SECRET123'));
  }
  assert.equal(redactObservedHref('/accounts/login/?next=%2Fsecret'),
    '/accounts/login/?[redacted]');
});
