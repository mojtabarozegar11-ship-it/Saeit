/* Chromium read-only visual rehearsal of approved interior dark-olive background.
 * CSS is injected into an isolated browser session ONLY; no site or form writes.
 */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const OUT=path.join(process.env.RUNNER_TEMP||'/tmp','zm-interior-palette-rehearsal');
fs.mkdirSync(OUT,{recursive:true});
const targets=[
 {route:'/tala/',type:'tala',selectors:['body','.header','.tala-live-market','.ticker','.tools','.footer'],
  css:':root{--bg:#252b19;--panel:#303822;--panel2:#39432a}body{background:var(--bg)!important}.header,.tala-live-market,.ticker,.tools,.footer{background:var(--bg)!important}'},
 {route:'/amozeshgah/',type:'academy',selectors:['body','header','.topline','main','.section.alt','footer'],
  css:'body,header,.topline,main,.section.alt,footer{background:#252b19!important;background-image:none!important}'}
 ,{route:'/store/',type:'store',selectors:['body','header','footer'],css:'body,header,footer{background:#252b19!important;background-image:none!important}'}
 ,...['/company/','/services/','/research/','/industry/'].map(route=>({
  route,type:'v7-'+route.replace(/\//g,''),
  selectors:['body','main','.zm-v7-header','.zm-v7-footer','.zm-hero','.zm-narrative','.zm-next'],
  css:':root{--zm7-bg:#252b19}body.zm-unified-v7,body.zm-unified-v7 main,body.zm-unified-v7 .zm-v7-header,body.zm-unified-v7 .zm-v7-footer,body.zm-unified-v7 main .zm-hero,body.zm-unified-v7 main .zm-narrative,body.zm-unified-v7 main .zm-next{background:#252b19!important;background-image:none!important}'
}))
];
const successes=[];
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  for(const target of targets){
   for(const width of (target.route==='/tala/'?[390,1440]:[390])){
    const page=await browser.newPage({viewport:{width,height:820},locale:'fa-IR',reducedMotion:'reduce'});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const response=await page.goto('https://zomorodmelal.ir'+target.route,
      {waitUntil:'domcontentloaded',timeout:35000});
    await page.waitForTimeout(160);
    const scan=async()=>page.evaluate(selectors=>{
      const rgb=e=>getComputedStyle(e).backgroundColor;
      const where=s=>[...document.querySelectorAll(s)].filter(e=>getComputedStyle(e).display!=='none')
        .slice(0,12).map(e=>({background:rgb(e),left:Math.round(e.getBoundingClientRect().left),
          width:Math.round(e.getBoundingClientRect().width),
          height:Math.round(e.getBoundingClientRect().height)}));
      const title=document.querySelector('h1');
      const heading=title?title.getBoundingClientRect():null;
      const sites={};
      for(const selector of selectors)sites[selector]=where(selector);
      return {sites,documentWidth:document.documentElement.scrollWidth,bodyClass:document.body.className,
        heading:{x:Math.round(heading?.x||0),y:Math.round(heading?.y||0),w:Math.round(heading?.width||0)},
        h1Count:document.querySelectorAll('h1').length};
    },target.selectors);
    const before=await scan();
    await page.addStyleTag({content:target.css});
    await page.waitForTimeout(140);
    const after=await scan();
    const olive='rgb(37, 43, 25)';
    const backgrounds=Object.values(after.sites).flatMap(x=>x.map(a=>a.background));
    const allOlive=backgrounds.length>0&&backgrounds.every(x=>x===olive);
    const dx=Math.abs(before.heading.x-after.heading.x);
    const dy=Math.abs(before.heading.y-after.heading.y);
    const dw=Math.abs(before.heading.w-after.heading.w);
    const stable=dx<=2&&dy<=2&&dw<=2;
    const result={route:target.route,viewport:width,http:response.status(),
      liveBodyClass:before.bodyClass,
      sourceSelectorMatches:target.type!=='academy'||before.bodyClass.includes('academy-page'),
      before:before.sites,after:after.sites,allOlive,stable,
      headingDelta:{x:dx,y:dy,width:dw},
      horizontalOverflowBefore:Math.max(0,before.documentWidth-width),
      horizontalOverflowAfter:Math.max(0,after.documentWidth-width),
      jsErrors:errors.length,isolatedBrowserOnly:true,siteWrites:0};
    console.log('ZM_INTERIOR_REHEARSAL '+JSON.stringify(result));
    successes.push(result);
    await page.screenshot({path:path.join(OUT,target.type+'-'+width+'.png'),
      fullPage:false,animations:'disabled'});
    await page.close();
   }
  }
 }finally{await browser.close()}
 const count=successes.filter(x=>x.allOlive&&x.stable&&x.http===200&&x.jsErrors===0).length;
 const summary={success:count,total:successes.length,sourceFilesNotDeployed:true,
  siteWrites:0,homepageUnaffected:true};
 console.log('ZM_INTERIOR_REHEARSAL_SUMMARY '+JSON.stringify(summary));
 fs.writeFileSync(path.join(OUT,'rehearsal.json'),JSON.stringify({summary,results:successes},null,2));
 if(process.env.GITHUB_STEP_SUMMARY){
  fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
    '\n## Existing interior dark-olive CSS rehearsal in isolated browser only\n\n'+
    count+'/'+successes.length+' visual and structural checks passed. No site changes.\n\n'+
    successes.map(x=>'- '+x.route+' '+x.viewport+'px: olive='+x.allOlive+
      ', heading-stable='+x.stable+', exceptions='+x.jsErrors+'\n').join(''));
 }
 if(count!==successes.length)process.exitCode=1;
})().catch(e=>{console.error('ZM_INTERIOR_REHEARSAL_FATAL',e);process.exitCode=1});
