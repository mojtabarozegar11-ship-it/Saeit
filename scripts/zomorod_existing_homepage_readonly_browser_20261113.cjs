/* Current production homepage-only browser quality audit.
 * No source/template edits, forms, payments or site writes.
 * Usage: npm install --no-save playwright@1.55.0; npx playwright install chromium;
 *        node scripts/zomorod_existing_homepage_readonly_browser_20261113.cjs
 */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const output=path.join(process.env.RUNNER_TEMP||'/tmp','zm-existing-homepage-browser-evidence');
fs.mkdirSync(output,{recursive:true});
const results=[];
function record(check,pass,details={}){
  const r={check,pass:Boolean(pass),...details};
  results.push(r);
  console.log('ZM_EXISTING_HOMEPAGE_BROWSER '+JSON.stringify(r));
}
async function check(name,operation){
  try{
    const d=await operation();
    record(name,d.ok,d.details||{});
  }catch(e){record(name,false,{error:String(e).slice(0,300)});}
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  for(const width of [390,768,1440]){
   const page=await browser.newPage({
     viewport:{width,height:850},
     locale:'fa-IR',
     reducedMotion:'no-preference',
     isMobile:width===390,
     hasTouch:width===390
   });
   const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await check('load_'+width,async()=>{
     const response=await page.goto('https://zomorodmelal.ir/',{
       waitUntil:'domcontentloaded',timeout:40000
     });
     await page.locator('#main').waitFor({timeout:13000});
     await page.waitForTimeout(500);
     return {ok:response.status()===200,details:{status:response.status()}};
   });
   const shape=await page.evaluate(()=>({
     viewport:innerWidth,
     width:document.documentElement.scrollWidth,
     h1:document.querySelectorAll('h1').length,
     strips:document.querySelectorAll('[data-auto-strip]').length,
     contact:!!document.querySelector('a[href="/contact/"]'),
     service:!!document.querySelector('a[href="/services/"]')
   })).catch(()=>({viewport:width,width:-1,h1:0,strips:0}));
   record('viewport_and_headings_'+width,shape.viewport===width&&
          shape.h1===1&&shape.contact&&shape.service,shape);
   record('whole_page_no_horizontal_overflow_'+width,
          shape.width>=width&&shape.width<=width+3,
          {viewport:width,documentWidth:shape.width});
   record('three_existing_rotating_rows_'+width,
          shape.strips===3,{count:shape.strips});
   if(width===390){
    await check('mobile_menu_toggle_and_escape',async()=>{
      const menu=page.locator('.mobile-menu-btn');
      await menu.click({timeout:10000});
      const opened=await page.locator('#mobile-nav').isVisible();
      const expanded=await menu.getAttribute('aria-expanded');
      await page.keyboard.press('Escape');
      const closed=!(await page.locator('#mobile-nav').isVisible());
      return {ok:opened&&closed&&expanded==='true',
              details:{opened,expanded,closed}};
    });
   }
   await check('search_toggle_focus_escape_'+width,async()=>{
     const btn=page.locator('.search-toggle');
     await btn.click({timeout:10000});
     const opened=await page.locator('#search-wrap').isVisible();
     const focused=await page.locator('#site-search')
       .evaluate(e=>document.activeElement===e);
     await page.keyboard.press('Escape');
     const closed=!(await page.locator('#search-wrap').isVisible());
     return {ok:opened&&focused&&closed,
             details:{opened,focused,closed,formSubmitted:false}};
   });
   await check('services_row_pause_resume_'+width,async()=>{
     const toggle=page.locator('[data-rotator-toggle="services-strip"]');
     const before=await toggle.getAttribute('aria-pressed');
     await toggle.click({timeout:10000});
     const paused=await toggle.getAttribute('aria-pressed');
     await toggle.click({timeout:10000});
     const resumed=await toggle.getAttribute('aria-pressed');
     return {ok:before==='true'&&paused==='false'&&resumed==='true',
             details:{before,paused,resumed}};
   });
   if(width===390||width===1440){
    await check('snapshot_'+width,async()=>{
      await page.screenshot({path:path.join(output,'current-home-'+width+'.png'),
             fullPage:true,animations:'disabled',timeout:20000});
      return {ok:true,details:{snapshot:'current-home-'+width+'.png'}};
    });
   }
   record('uncaught_page_exceptions_'+width,errors.length===0,
          {count:errors.length,messages:errors.slice(0,3)});
   await page.close();
  }
  const page=await browser.newPage({viewport:{width:390,height:850},
      locale:'fa-IR',reducedMotion:'reduce'});
  await check('respect_reduced_motion',async()=>{
    await page.goto('https://zomorodmelal.ir/',{
      waitUntil:'domcontentloaded',timeout:40000});
    const toggle=page.locator('[data-rotator-toggle="services-strip"]');
    await toggle.waitFor({timeout:10000});
    await page.waitForTimeout(400);
    const state=await toggle.getAttribute('aria-pressed');
    return {ok:state==='false',details:{ariaPressed:state}};
  });
  await page.close();
 }finally{await browser.close();}
 const passed=results.filter(r=>r.pass).length;
 const summary={passed,failed:results.length-passed,total:results.length,
    scope:'CURRENT_PRODUCTION_HOMEPAGE_ONLY',siteMutations:0,
    formSubmissions:0,templateChanges:0};
 console.log('ZM_EXISTING_HOMEPAGE_BROWSER_SUMMARY '+JSON.stringify(summary));
 fs.writeFileSync(path.join(output,'results.json'),
    JSON.stringify({summary,results},null,2));
 if(process.env.GITHUB_STEP_SUMMARY){
   fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
     '\n## Current homepage responsive Chromium audit (read-only)\n\n'+
     '**'+passed+'/'+results.length+' passed**. No site mutations or form submissions.\n\n'+
     results.map(x=>'- '+(x.pass?'PASS':'FAIL')+' '+x.check+'\n').join(''));
 }
 if(summary.failed) process.exitCode=1;
})().catch(e=>{
 console.error('ZM_EXISTING_HOMEPAGE_BROWSER_FATAL',e);
 process.exitCode=1;
});
