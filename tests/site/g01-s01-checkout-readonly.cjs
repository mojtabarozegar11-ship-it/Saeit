// G-01 -> S-01 non-invasive browser QA handoff. GET-only; never click purchase or payment.
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const out=process.env.RUNNER_TEMP||'/tmp';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
  await context.route('**/*',route=>{
   const req=route.request();
   if(req.method()!=='GET')return route.abort('blockedbyclient');
   return route.continue();
  });
  for(const slug of ['/store/','/store/product/72/','/store/product/225/','/store/product/879/']){
   const page=await context.newPage();const errors=[];
   page.on('pageerror',e=>errors.push(e.message.slice(0,240)));
   const response=await page.goto('https://mojplaywin.com'+slug,{waitUntil:'domcontentloaded',timeout:40000});
   const result=await page.evaluate(()=>({title:document.title,landmarks:document.querySelectorAll('main,[role=main]').length,links:[...document.querySelectorAll('a[href]')].length,controls:[...document.querySelectorAll('button,input[type=submit],a[href]')].map(e=>({label:(e.getAttribute('aria-label')||e.getAttribute('title')||e.textContent||e.querySelector('img')?.alt||'').trim().slice(0,90),disabled:e.disabled===true,href:e.tagName==='A'?e.getAttribute('href'):null})).filter(e=>!e.label).slice(0,25)}));
   result.path=slug;result.http=response?.status()||0;result.pageErrors=errors;result.mobileLayout=await page.evaluate(()=>({horizontalOverflowPx:Math.max(0,document.documentElement.scrollWidth-document.documentElement.clientWidth),imagesWithoutAlt:[...document.querySelectorAll('img:not([alt])')].length,invoiceLinkCount:[...document.querySelectorAll('a[href]')].filter(a=>/invoice|فاکتور/i.test((a.textContent||'')+' '+a.getAttribute('href'))).length}));
   await page.screenshot({path:path.join(out,'g01-s01-'+slug.replace(/[^a-z0-9]+/gi,'-')+'.png'),fullPage:true,animations:'disabled'});
   results.push(result);await page.close();
  }
  fs.writeFileSync(path.join(out,'g01-s01-checkout-readonly.json'),JSON.stringify({checkedAt:new Date().toISOString(),readOnly:true,results},null,2));
  console.log(JSON.stringify(results.map(x=>({path:x.path,http:x.http,unlabelled:x.controls.length,jsErrors:x.pageErrors.length})),null,2));
  assert(results.every(x=>x.http===200),'at least one public store page is unavailable');
  assert(results.every(x=>x.pageErrors.length===0),'storefront has a JavaScript runtime exception');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
