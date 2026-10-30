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
     let response;
     try{response=await page.goto('https://mojplaywin.com'+slug,{waitUntil:'domcontentloaded',timeout:40000})}
     catch(e){
      results.push({device:device.name,path:slug,http:0,pageErrors:errors,navigationError:String(e.message||e).slice(0,240)});
      await page.close();continue;
     }
     const details=await page.evaluate(()=>{
      const controls=[...document.querySelectorAll('button,input[type=submit],a[href]')];
      const unlabeled=controls.filter(el=>!(el.getAttribute('aria-label')||el.getAttribute('title')||el.textContent||el.querySelector('img')?.alt||el.value||'').trim()).slice(0,25).map(el=>({tag:el.tagName,href:el.tagName==='A'?el.getAttribute('href'):null}));
      const ids=[...document.querySelectorAll('[id]')].map(el=>el.id);const duplicateIds=[...new Set(ids.filter((id,i)=>id&&ids.indexOf(id)!==i))].slice(0,20);
      const focusable=[...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')].filter(el=>!el.disabled&&el.getAttribute('aria-disabled')!=='true'&&el.tabIndex>=0&&getComputedStyle(el).visibility!=='hidden'&&getComputedStyle(el).display!=='none');
      const purchaseControls=controls.filter(el=>/buy|checkout|pay|purchase|خرید|پرداخت|فاکتور|invoice/i.test([el.textContent,el.getAttribute('aria-label'),el.getAttribute('href')].filter(Boolean).join(' ')));
      return {duplicateIds,focusableCount:focusable.length,purchaseControls:purchaseControls.slice(0,20).map(el=>({tag:el.tagName,label:(el.textContent||el.getAttribute('aria-label')||'').trim().slice(0,90),disabled:!!el.disabled,ariaDisabled:el.getAttribute('aria-disabled'),ariaBusy:el.getAttribute('aria-busy'),checkoutIntent:/checkout|buy|purchase|order|invoice|خرید|فاکتور/i.test([el.textContent,el.getAttribute('href')].filter(Boolean).join(' ')),pointerEvents:getComputedStyle(el).pointerEvents,visible:getComputedStyle(el).display!=='none'&&getComputedStyle(el).visibility!=='hidden',hitTargetObscured:(()=>{const r=el.getBoundingClientRect();if(r.width<=0||r.height<=0)return null;if(r.bottom<=0||r.top>=innerHeight||r.right<=0||r.left>=innerWidth)return null;const x=Math.max(0,Math.min(innerWidth-1,r.left+r.width/2)),y=Math.max(0,Math.min(innerHeight-1,r.top+r.height/2));const top=document.elementFromPoint(x,y);return top?!(el===top||el.contains(top)):null})(),href:el.tagName==='A'?el.getAttribute('href'):null})),title:document.title,landmarks:document.querySelectorAll('main,[role=main]').length,links:document.querySelectorAll('a[href]').length,unlabeled,disabledButtons:[...document.querySelectorAll('button:disabled')].length,horizontalOverflowPx:Math.max(0,document.documentElement.scrollWidth-document.documentElement.clientWidth),imagesWithoutAlt:document.querySelectorAll('img:not([alt])').length,invoiceLinkCount:[...document.querySelectorAll('a[href]')].filter(a=>/invoice|فاکتور/i.test((a.textContent||'')+' '+a.getAttribute('href'))).length};
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
