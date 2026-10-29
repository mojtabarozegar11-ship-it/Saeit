'use strict';
// G-01 -> S-01: unauthenticated GET-only checkout-control triage.
// Never clicks payment, submits a form, opens a wallet or records user data.
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const out='g01-s01-audit-output';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const rows=[];
 try{
  for(const device of [{name:'mobile',width:390,height:844},{name:'desktop',width:1280,height:800}]){
   const ctx=await browser.newContext({viewport:{width:device.width,height:device.height},serviceWorkers:'block'});
   await ctx.route('**/*',route=>route.request().method()==='GET'?route.continue():route.abort('blockedbyclient'));
   try{
    for(const slug of ['/store/','/store/product/72/','/store/product/225/','/store/product/879/']){
     const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push((e.name||'JavaScriptError').slice(0,80)));
     let response=null,error=null;
     try{response=await page.goto('https://mojplaywin.com'+slug,{waitUntil:'domcontentloaded',timeout:35000})}catch(e){error=String(e.message).slice(0,180)}
     const controls=await page.evaluate(()=>[...document.querySelectorAll('button,a[href],input[type=submit]')].filter(el=>/checkout|invoice|pay|buy|purchase|cart|فاکتور|پرداخت|خرید|سبد/i.test((el.getAttribute('aria-label')||el.innerText||el.value||'')+' '+(el.getAttribute('href')||''))).slice(0,60).map(el=>{try{el.scrollIntoView({block:'center',inline:'center',behavior:'instant'})}catch(_){}
      const rect=el.getBoundingClientRect(),style=getComputedStyle(el),name=(el.getAttribute('aria-label')||el.innerText||el.value||'').trim().slice(0,80);
      const visible=rect.width>0&&rect.height>0&&style.visibility!=='hidden'&&style.display!=='none';
      const x=rect.left+rect.width/2,y=rect.top+rect.height/2,inViewport=visible&&x>=0&&y>=0&&x<innerWidth&&y<innerHeight;
      const hit=inViewport?document.elementFromPoint(x,y):null,centerBlocked=!!(hit&&hit!==el&&!el.contains(hit));
      let href=null;if(el.tagName==='A'){try{const u=new URL(el.href);href=u.origin===location.origin?u.pathname:'[external]'}catch(_){href='[invalid]'}}
      const blockedBy=centerBlocked?{tag:hit.tagName,id:(hit.id||'').slice(0,60),className:typeof hit.className==='string'?hit.className.slice(0,80):''}:null;
      const disabledReasons=[el.disabled?'native-disabled':null,el.getAttribute('aria-disabled')==='true'?'aria-disabled':null,style.pointerEvents==='none'?'pointer-events-none':null,el.closest('fieldset[disabled]')?'disabled-fieldset':null,el.closest('[inert]')?'inert-ancestor':null,!visible?'hidden':null,centerBlocked?'center-obstructed':null].filter(Boolean);
      return {tag:el.tagName,id:(el.id||'').slice(0,80),name,href,disabled:!!el.disabled,ariaDisabled:el.getAttribute('aria-disabled'),visible,pointerEvents:style.pointerEvents,tabIndex:el.tabIndex,centerBlocked,centerChecked:inViewport,blockedBy,disabledReasons};
     }));
     const record={device:device.name,path:slug,http:response?.status()||0,error,jsErrors:errors,controls};
     rows.push(record);
     await page.screenshot({path:path.join(out,device.name+'-'+slug.replace(/[^a-z0-9]+/gi,'-')+'.png'),fullPage:true,animations:'disabled'});
     await page.close();
    }
   }finally{await ctx.close()}
  }
  fs.writeFileSync(path.join(out,'checkout-controls.json'),JSON.stringify({scope:'public GET only',checkedAt:new Date().toISOString(),rows},null,2));
  console.log(JSON.stringify(rows.map(x=>({device:x.device,path:x.path,http:x.http,disabled:x.controls.filter(c=>c.disabled||c.ariaDisabled==='true'||c.pointerEvents==='none').length,controls:x.controls.length,jsErrors:x.jsErrors.length,error:x.error})),null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
