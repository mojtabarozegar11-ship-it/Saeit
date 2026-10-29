'use strict';
// S-01 adopts G-01's checkout-control triage: anonymous GET-only, no checkout
// clicks, submissions, cookies, payment calls, credentials or customer data.
const fs = require('node:fs');
const {chromium} = require('playwright');
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
      // Fail closed: no POST, PUT, PATCH, DELETE, websocket or other mutation.
      await context.route('**/*', route => route.request().method()==='GET'
        ? route.continue() : route.abort('blockedbyclient'));
      try {
        for (const path of URLS) {
          const page = await context.newPage();
          let http=0, error=null, finalPath=null;
          const jsErrors=[];
          page.on('pageerror', e => jsErrors.push((e.name||'JavaScriptError').slice(0,60)));
          try {
            const response=await page.goto('https://mojplaywin.com'+path,
              {waitUntil:'domcontentloaded',timeout:25000});
            http=response?.status()||0;
            const final=new URL(page.url());
            finalPath=final.origin==='https://mojplaywin.com'?final.pathname:'[external-redirect]';
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
              let href=null;
              if(el.tagName==='A'){try{
                const u=new URL(el.href);href=u.origin===location.origin?u.pathname:'[external]';
              }catch(_){href='[invalid]';}}
              const reasons=[el.disabled?'native-disabled':null,
                el.getAttribute('aria-disabled')==='true'?'aria-disabled':null,
                style.pointerEvents==='none'?'pointer-events-none':null,
                el.closest('fieldset[disabled]')?'disabled-fieldset':null,
                el.closest('[inert]')?'inert-ancestor':null,
                !visible?'hidden':null,covered?'center-obstructed':null].filter(Boolean);
              return {tag:el.tagName,name,href,reasons,
                coveredBy:covered?{tag:hit.tagName,id:(hit.id||'').slice(0,60)}:null};
            }).filter(x=>/checkout|invoice|pay|buy|purchase|cart|فاکتور|پرداخت|خرید|سبد/i
              .test(x.name+' '+x.href)).slice(0,60));
            } catch(e) { error = error || ('DOM_'+(e.name||'Error')).slice(0,60); }
          }
          rows.push({device:device.name,path,http,finalPath,error,jsErrors,controls,
            checkoutLinks:controls.filter(c=>/\/checkout\/$/.test(c.href||'')&&c.reasons.length===0).length});
          await page.close();
        }
      } finally {await context.close();}
    }
    const report={schema:'s01-anonymous-get-controls.v1',scope:'GET_ONLY_NO_PAYMENT',
      checkedAt:new Date().toISOString(),ordersCreated:0,paymentsCreated:0,rows,
      complete:rows.length===URLS.length*2 && rows.every(r=>r.http>=200&&r.http<500&&!r.error)};
    fs.writeFileSync('s01-public-checkout-controls.json',JSON.stringify(report,null,2));
    if (!report.complete) process.exitCode=2; // A partial scan must not be green.
    console.log(JSON.stringify({schema:report.schema,rows:rows.map(x=>({
      device:x.device,path:x.path,http:x.http,finalPath:x.finalPath,checkoutLinks:x.checkoutLinks,controls:x.controls.length,
      disabled:x.controls.filter(c=>c.reasons.length).length,
      jsErrors:x.jsErrors.length,error:x.error
    }))}));
  } finally {await browser.close();}
})().catch(e=>{console.error('S01_READONLY_DIAGNOSTIC_ERROR='+e.name);process.exitCode=1;});
