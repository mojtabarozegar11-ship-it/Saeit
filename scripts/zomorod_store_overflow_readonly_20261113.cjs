/* Read-only browser diagnostic for the EXISTING Zomorod store page.
 * No template edits, form submissions, login, payments or writes to production.
 */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const artifact=path.join(process.env.RUNNER_TEMP||'/tmp','zm-store-overflow-readonly');
fs.mkdirSync(artifact,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const rows=[];
 try{
  for(const width of [320,390,768,1440]){
   const page=await browser.newPage({viewport:{width,height:870},locale:'fa-IR'});
   const errors=[];page.on('pageerror',e=>errors.push(e.message.slice(0,180)));
   const response=await page.goto('https://zomorodmelal.ir/store/',{waitUntil:'domcontentloaded',timeout:45000});
   await page.waitForTimeout(300);
   const detail=await page.evaluate(()=>{
    const width=innerWidth;
    const candidates=[];
    for(const e of document.querySelectorAll('body *')){
      if(candidates.length>20000)break;
      const st=getComputedStyle(e),b=e.getBoundingClientRect();
      if(st.display==='none'||st.visibility==='hidden'||b.width===0||b.height===0)continue;
      const right=Math.max(0,b.right-width),left=Math.max(0,-b.left);
      if(Math.max(right,left)<6)continue;
      const id=e.id?('#'+e.id):'';
      const cls=typeof e.className==='string'?e.className.trim().split(/\s+/).slice(0,3).join('.'):'';
      const selector=e.tagName.toLowerCase()+id+(cls?'.'+cls:'');
      const ancestor=e.parentElement;
      candidates.push({selector,right:Math.round(right),left:Math.round(left),
        x:Math.round(b.left),w:Math.round(b.width),minWidth:st.minWidth,
        maxWidth:st.maxWidth,display:st.display,overflowX:st.overflowX,
        whiteSpace:st.whiteSpace,position:st.position,
        scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,
        ancestor:ancestor?(ancestor.tagName.toLowerCase()+(ancestor.id?'#'+ancestor.id:'')):'',
        html:e.outerHTML.replace(/\s+/g,' ').slice(0,200)});
    }
    candidates.sort((a,b)=>Math.max(b.right,b.left)-Math.max(a.right,a.left));
    return {width,documentWidth:document.documentElement.scrollWidth,
      bodyWidth:document.body.scrollWidth,
      title:document.title,htmlClass:document.documentElement.className,
      bodyClass:document.body.className,
      count:candidates.length,top:candidates.slice(0,22)};
   });
   const row={width,http:response.status(),url:page.url(),errorCount:errors.length,...detail};
   rows.push(row);
   console.log('ZM_STORE_OVERFLOW_DIAGNOSTIC '+JSON.stringify(row));
   if(width===320||width===390){
      await page.screenshot({path:path.join(artifact,'store-'+width+'.png'),
        fullPage:true,animations:'disabled',timeout:20000});
   }
   await page.close();
  }
 }finally{await browser.close()}
 fs.writeFileSync(path.join(artifact,'store-overflow.json'),JSON.stringify(rows,null,2));
 if(process.env.GITHUB_STEP_SUMMARY){
  fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
  '\n## Existing store mobile overflow — read only\n\n'+
  '| Viewport | Document width | Overflow | HTTP |\n|---:|---:|---:|---:|\n'+
  rows.map(r=>'| '+r.width+' | '+r.documentWidth+' | '+
     Math.max(0,r.documentWidth-r.width)+' | '+r.http+' |\n').join('')+
  '\nThe full element-level evidence is in this run artifact. No production writes.\n');
 }
 if(rows.some(r=>r.http!==200))process.exitCode=1;
})().catch(e=>{console.error('ZM_STORE_DIAGNOSTIC_FATAL',e);process.exitCode=1});
