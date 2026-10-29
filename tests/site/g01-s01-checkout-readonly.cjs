// G-01 -> S-01 read-only mobile + desktop storefront accessibility evidence.
// No forms, wallet, purchases, login, or production writes; GET requests only.
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const out=process.env.RUNNER_TEMP||'/tmp';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try{
  for(const device of [{name:'mobile',width:390,height:844,isMobile:true},{name:'desktop',width:1280,height:800,isMobile:false}]){
   const context=await browser.newContext({viewport:{width:device.width,height:device.height},isMobile:device.isMobile,hasTouch:device.isMobile,serviceWorkers:'block'});
   try{
    await context.route('**/*',route=>route.request().method()==='GET'?route.continue():route.abort('blockedbyclient'));
    for(const slug of ['/store/','/store/product/72/','/store/product/225/','/store/product/879/']){
     const page=await context.newPage(),errors=[];
     page.on('pageerror',e=>errors.push(e.message.slice(0,240)));
     const response=await page.goto('https://mojplaywin.com'+slug,{waitUntil:'domcontentloaded',timeout:40000});
     const details=await page.evaluate(()=>{
      const controls=[...document.querySelectorAll('button,input[type=submit],a[href]')];
      const unlabeled=controls.filter(el=>!(el.getAttribute('aria-label')||el.getAttribute('title')||el.textContent||el.querySelector('img')?.alt||el.value||'').trim()).slice(0,25).map(el=>({tag:el.tagName,href:el.tagName==='A'?el.getAttribute('href'):null}));
      return {title:document.title,landmarks:document.querySelectorAll('main,[role=main]').length,links:document.querySelectorAll('a[href]').length,unlabeled,disabledButtons:[...document.querySelectorAll('button:disabled')].length,horizontalOverflowPx:Math.max(0,document.documentElement.scrollWidth-document.documentElement.clientWidth),imagesWithoutAlt:document.querySelectorAll('img:not([alt])').length,invoiceLinkCount:[...document.querySelectorAll('a[href]')].filter(a=>/invoice|فاکتور/i.test((a.textContent||'')+' '+a.getAttribute('href'))).length};
     });
     const result={device:device.name,path:slug,http:response?.status()||0,pageErrors:errors,...details};
     await page.screenshot({path:path.join(out,'g01-s01-'+device.name+'-'+slug.replace(/[^a-z0-9]+/gi,'-')+'.png'),fullPage:true,animations:'disabled'});
     results.push(result);await page.close();
    }
   }finally{await context.close()}
  }
  fs.writeFileSync(path.join(out,'g01-s01-checkout-readonly.json'),JSON.stringify({checkedAt:new Date().toISOString(),readOnly:true,results},null,2));
  console.log(JSON.stringify(results.map(x=>({device:x.device,path:x.path,http:x.http,unlabeled:x.unlabeled.length,overflow:x.horizontalOverflowPx,jsErrors:x.pageErrors.length})),null,2));
  assert(results.every(x=>x.http===200),'at least one public store page is unavailable');
  assert(results.every(x=>x.pageErrors.length===0),'storefront has a JavaScript runtime exception');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
