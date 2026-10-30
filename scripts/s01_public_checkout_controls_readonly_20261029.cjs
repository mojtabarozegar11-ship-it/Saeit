'use strict';
// S-01 adopts G-01's checkout-control triage: anonymous GET-only, no checkout
// clicks, submissions, cookies, payment calls, credentials or customer data.
const fs = require('node:fs');
const {chromium} = require('playwright');
const {classifyNavigation} = require('./s01_checkout_route_verdict_20261029.cjs');
const URLS = ['/store/','/store/product/72/','/store/product/225/','/store/product/879/',
  '/store/product/72/checkout/','/store/product/225/checkout/',
  '/store/product/879/checkout/','/commerce/trx-easy/purchases/'];
(async () => {
  const browser = await chromium.launch({headless:true});
  const rows = [];
  try {
    for (const device of [{name:'mobile',width:390,height:844},{name:'desktop',width:1280,height:800}]) {
      const context = await browser.newContext({
        viewport:{width:device.width,height:device.height},
        serviceWorkers:'block',acceptDownloads:false,
        extraHTTPHeaders:{'Cache-Control':'no-cache'}
      });
      // Fail closed: no mutating requests or navigation to third-party hosts.
      // Passive external subresources may still load; external page navigation may not.
      await context.route('**/*', route => {
        const req = route.request();
        if (req.method() !== 'GET') return route.abort('blockedbyclient');
        // Never contact third-party endpoints, even via passive GET assets.
        if (new URL(req.url()).origin !== 'https://mojplaywin.com')
          return route.abort('blockedbyclient');
        return route.continue();
      });
      try {
        for (const path of URLS) {
          const page = await context.newPage();
          let http=0, error=null, finalPath=null, finalSearch='';
          const jsErrors=[];
          page.on('pageerror', e => jsErrors.push((e.name||'JavaScriptError').slice(0,60)));
          try {
            const response=await page.goto('https://mojplaywin.com'+path,
              {waitUntil:'domcontentloaded',timeout:25000});
            http=response?.status()||0;
            const final=new URL(page.url());
            finalPath=final.origin==='https://mojplaywin.com'?final.pathname:'[external-redirect]';
            finalSearch=final.origin==='https://mojplaywin.com'?final.search:'';
          } catch(e) {error=(e.name||'NavigationError').slice(0,60);}
          let controls=[];
          if (http > 0 && finalPath !== '[external-redirect]') {
            try { controls=await page.evaluate(() => [...document.querySelectorAll('button,a[href],input[type="submit"]')]
            .map(el=>{
              const r=el.getBoundingClientRect(),style=getComputedStyle(el);
              const name=(el.getAttribute('aria-label')||el.innerText||el.value||'').trim().slice(0,80);
              const visible=r.width>0&&r.height>0&&style.visibility!=='hidden'&&style.display!=='none';
              const x=r.left+r.width/2,y=r.top+r.height/2;
              const inView=visible&&x>=0&&y>=0&&x<innerWidth&&y<innerHeight;
              const hit=inView?document.elementFromPoint(x,y):null;
              const covered=!!(hit&&hit!==el&&!el.contains(hit));
              // Inspect form-based buyer CTAs without submitting or charging.
              const form=el.form||null;
              const formMethod=form?(el.getAttribute('formmethod')||form.getAttribute('method')||'get').toLowerCase():null;
              const isSubmit=form&&(el.tagName==='BUTTON'||(el.tagName==='INPUT'&&el.type==='submit'));
              let href=null;
              if(el.tagName==='A'||isSubmit){try{
                const raw=el.tagName==='A'?el.getAttribute('href'):
                  (el.getAttribute('formaction')||form.getAttribute('action')||location.pathname);
                const u=new URL(raw,location.href);
                href=u.origin===location.origin?(u.pathname+u.search+u.hash):'[external]';
              }catch(_){href='[invalid]';}}
              const rawHref=el.tagName==='A'?(el.getAttribute('href')||'').trim():null;
              const reasons=[isSubmit&&formMethod!=='get'?'form-requires-authenticated-staging':null,
                isSubmit&&href==='[external]'?'off-origin-form-action':null,
                rawHref!==null&&(!rawHref||rawHref==='#'||/^javascript:/i.test(rawHref))?'invalid-action-link':null,
                el.closest('[aria-hidden="true"]')?'assistive-tech-hidden':null,
                el.disabled?'native-disabled':null,
                el.getAttribute('aria-disabled')==='true'?'aria-disabled':null,
                style.pointerEvents==='none'?'pointer-events-none':null,
                el.closest('fieldset[disabled]')?'disabled-fieldset':null,
                el.closest('[inert]')?'inert-ancestor':null,
                !visible?'hidden':null,covered?'center-obstructed':null].filter(Boolean);
              return {tag:el.tagName,name,href,formMethod,reasons,
                coveredBy:covered?{tag:hit.tagName,id:(hit.id||'').slice(0,60)}:null};
            }).filter(x=>/checkout|invoice|pay|buy|purchase|cart|فاکتور|پرداخت|خرید|سبد/i
              .test(x.name+' '+x.href)).slice(0,60));
            } catch(e) { error = error || ('DOM_'+(e.name||'Error')).slice(0,60); }
          }
          // HTTP 200 at a login redirect is not a completed buyer checkout.
          const verdict = classifyNavigation(path, http, finalPath, error, finalSearch);
          const productId=/^\/store\/product\/(\d+)\/$/.exec(path)?.[1]||null;
          const validCheckoutHref=href=>productId?href===`/store/product/${productId}/checkout/`:
            /^\/store\/product\/\d+\/checkout\/$/.test(href||'');
          rows.push({device:device.name,path,http,finalPath,error,jsErrors,controls,
            ...verdict,authenticatedBuyerFlowVerified:false,
            checkoutLinks:controls.filter(c=>validCheckoutHref(c.href)&&c.reasons.length===0).length,
            mismatchedCheckoutLinks:productId?controls.filter(c=>/\/checkout\/$/.test(c.href||'')&&!validCheckoutHref(c.href)).length:0,
            formSubmissionsNeedingStaging:controls.filter(c=>c.reasons.includes('form-requires-authenticated-staging')).length});
          await page.close();
        }
      } finally {await context.close();}
    }
    const report={schema:'s01-anonymous-get-controls.v1',scope:'GET_ONLY_NO_PAYMENT',
      checkedAt:new Date().toISOString(),ordersCreated:0,paymentsCreated:0,rows,
      complete:rows.length===URLS.length*2 && rows.every(r=>{
        const productDetail=/^\/store\/product\/(72|225|879)\/$/.test(r.path);
        return r.observedSafe && r.jsErrors.length===0 &&
          (!productDetail || (r.checkoutLinks>0 && r.mismatchedCheckoutLinks===0));
      }),
      completeMeaning:'ANONYMOUS_GET_OBSERVATION_AND_CORRECT_SKU_CTA_ONLY',
      authGatedRoutes:rows.filter(r=>r.authRequired).length,
      authenticatedBuyerFlowVerified:false,invoiceVerified:false,
      paymentVerified:false,emailDeliveryVerified:false,downloadVerified:false,
      commercialDeliveryStatus:'NOT_VERIFIED'};
    fs.writeFileSync('s01-public-checkout-controls.json',JSON.stringify(report,null,2));
    if (!report.complete) process.exitCode=2; // A partial scan must not be green.
    console.log(JSON.stringify({schema:report.schema,rows:rows.map(x=>({
      device:x.device,path:x.path,http:x.http,finalPath:x.finalPath,checkoutLinks:x.checkoutLinks,controls:x.controls.length,
      disabled:x.controls.filter(c=>c.reasons.length).length,
      jsErrors:x.jsErrors.length,authRequired:x.authRequired,
      unexpectedRedirect:x.unexpectedRedirect,error:x.error
    }))}));
  } finally {await browser.close();}
})().catch(e=>{console.error('S01_READONLY_DIAGNOSTIC_ERROR='+e.name);process.exitCode=1;});
