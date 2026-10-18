const {chromium}=require('playwright');
const AxeBuilder=require('@axe-core/playwright').default;
const fs=require('fs');
const ORIGIN='https://zomorodmelal.ir';
const paths=['/','/company/','/about/','/research/','/research/directory/centers/bioinformatics/','/research/directory/laboratories/microbiology/','/agriculture/','/agriculture/genetics/','/agriculture/horticulture/','/agriculture/greenhouse/','/agriculture/livestock/','/industry/','/services/','/knowledge/','/news/','/store/','/search/','/topics/','/topics/zm-r01/wheat/','/contact/','/agents/','/economy/','/market/','/business/','/tala/','/studio/','/amozeshgah/','/blog/'];
const AXE=new Set(['/','/company/','/about/','/research/','/agriculture/','/store/','/search/','/topics/','/contact/','/tala/','/business/']);
const photos=new Set(['/','/company/','/about/','/store/','/tala/','/research/','/agriculture/']);
const reports=[],accessibility=[],failures=[];
const start=Date.now();
const thin=s=>String(s||'').replace(/\s+/g,' ').trim().slice(0,170);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  for(const width of [390,1440]){
    const context=await browser.newContext({viewport:{width,height:900},deviceScaleFactor:1,locale:'fa-IR',reducedMotion:'no-preference'});
    for(let i=0;i<paths.length;i++){
      const path=paths[i],page=await context.newPage();
      const jsErrors=[],netFailures=[],httpErrors=[];
      page.on('pageerror',e=>jsErrors.push(thin(e.message)));
      page.on('console',m=>{if(m.type()==='error')jsErrors.push('console:'+thin(m.text()))});
      page.on('requestfailed',r=>{if(netFailures.length<9)netFailures.push({url:r.url(),error:r.failure()?.errorText})});
      page.on('response',r=>{if(r.status()>=400&&httpErrors.length<8)httpErrors.push({url:r.url(),status:r.status()})});
      let response=null,error=null,t0=Date.now();
      try{
        response=await page.goto(ORIGIN+path+'?__sitewide_browser_audit=20261019',{waitUntil:'domcontentloaded',timeout:44000});
        await page.waitForTimeout(320);
      }catch(e){error=thin(e.message,200)}
      let data={};
      if(response){
        try{data=await page.evaluate(()=>{
          const qs=s=>[...document.querySelectorAll(s)];
          const isVisible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
          const select=e=>{const r=e.getBoundingClientRect();return {w:Math.round(r.width),h:Math.round(r.height),x:Math.round(r.x),y:Math.round(r.y)}};
          const allAnchors=qs('a[href]'),visibleLinks=allAnchors.filter(isVisible);
          const small=visibleLinks.filter(e=>{const r=e.getBoundingClientRect();return r.width<24||r.height<24}).slice(0,9).map(x=>({txt:(x.textContent||'').trim().slice(0,35),box:select(x)}));
          const h1=qs('h1').map(e=>({t:e.textContent.trim().slice(0,130),visible:isVisible(e)}));
          const cards=qs('.topic-card'),heads=qs('.shelf-explanation'),shelves=qs('.orbit-shelf');
          const images=qs('img'),broken=images.filter(e=>e.complete&&e.naturalWidth===0).slice(0,8).map(e=>e.getAttribute('src'));
          const main=qs('main,#content')[0],header=qs('header')[0],footer=qs('footer')[0];
          const nav=qs('nav').map(e=>({label:e.getAttribute('aria-label'),links:e.querySelectorAll('a').length})).slice(0,3);
          const metaDescription=document.querySelector('meta[name="description"]')?.content||'';
          const keys=['zm-unified-v7','zm-nova','zm-v10','zm-v7'];
          const buttons=qs('button').filter(isVisible).length;
          return {
            title:document.title,lang:document.documentElement.lang,dir:document.documentElement.dir,
            description:metaDescription.slice(0,210),canonical:document.querySelector('link[rel="canonical"]')?.href||'',
            robots:document.querySelector('meta[name="robots"]')?.content||'',
            h1,h2:qs('h2').length,h3:qs('h3').length,
            pageHeight:document.documentElement.scrollHeight,overflowX:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth,
            headerHeight:header?Math.round(header.getBoundingClientRect().height):null,
            headerLinks:header?header.querySelectorAll('a').length:0,footerPresent:!!footer,nav,mainPresent:!!main,
            images:images.length,missingAlt:images.filter(e=>!e.hasAttribute('alt')).length,brokenImages:broken,
            visibleSmallTargets:small,
            cards:cards.length,shelves:shelves.length,heads:heads.length,
            details:qs('details').length,forms:qs('form').length,buttons,
            elements:qs('*').length,links:allAnchors.length,uniqueDestinations:new Set(allAnchors.map(x=>x.href)).size,
            styleTags:qs('style').length,styleLinks:qs('link[rel="stylesheet"]').length,
            templateClass:document.body.className||'',bgColor:getComputedStyle(document.body).backgroundColor,
            fonts:getComputedStyle(document.body).fontFamily,
            htmlType:(document.documentElement.outerHTML||'').slice(0,135),
            firstContent:(main?.innerText||document.body?.innerText||'').trim().replace(/\s+/g,' ').slice(0,190),
            rootFloating:!!document.getElementById('zm-home-template-repairs-20261018'),
            companyGlass:!!document.getElementById('zm-company-thick-glass-20261018')
          };
        })}catch(e){error='page.evaluate: '+thin(e.message,160)}
      }
      const row={path,width,status:response?.status()||0,elapsedMs:Date.now()-t0,error,jsErrors:jsErrors.slice(0,7),netFailures,httpErrors,...data};
      reports.push(row);
      if(width===390&&AXE.has(path)&&response?.status()===200){
        try{
          const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']).analyze();
          const findings=a.violations.map(v=>({id:v.id,impact:v.impact,count:v.nodes.length,description:v.help,example:v.nodes.slice(0,2).map(n=>({html:thin(n.html),summary:thin(n.failureSummary)}))}));
          accessibility.push({path,width,violations:findings,incomplete:a.incomplete.map(v=>({id:v.id,count:v.nodes.length}))});
          console.log('SITE_AXE='+JSON.stringify({path,width,violations:findings}));
        }catch(e){accessibility.push({path,width,error:thin(e.message)})}
      }
      if(photos.has(path)&&response?.status()===200){
        const name=(path==='/'?'home':path.replace(/\W/g,'-').replace(/^-|-$/g,''))+'-'+width+'.png';
        await page.screenshot({path:name,fullPage:false,animations:'disabled',timeout:16000}).catch(e=>failures.push({path,width,screenshot:thin(e.message)}));
      }
      console.log('SITE_VISUAL='+JSON.stringify({path,width,status:row.status,title:row.title||'',h1:row.h1||[],overflowX:row.overflowX,imgs:row.images,missingAlt:row.missingAlt,brokenImages:row.brokenImages,jsErrors:jsErrors.length,netFailed:netFailures.length,scrollHeight:row.pageHeight,headerLinks:row.headerLinks,styleTags:row.styleTags,styleLinks:row.styleLinks,templateClass:row.templateClass,smallTargets:row.visibleSmallTargets?.slice(0,4),error:row.error}));
      await page.close();
    }
    await context.close();
  }
  const reducer=await browser.newContext({viewport:{width:390,height:900},reducedMotion:'reduce'});
  for(const path of ['/','/company/','/tala/']){
    const p=await reducer.newPage();
    try{
      const resp=await p.goto(ORIGIN+path,{waitUntil:'domcontentloaded',timeout:45000});
      await p.waitForTimeout(300);
      const m=await p.evaluate(()=>{
       const e=document.querySelector('.topic-card,.zm-card,[class*="card"]');return {reducedMotion:matchMedia('(prefers-reduced-motion:reduce)').matches,animation:e?getComputedStyle(e).animationName:null};
      });
      reports.push({path,width:390,test:'reduced-motion',status:resp.status(),...m});
      console.log('SITE_REDUCED_MOTION='+JSON.stringify({path,...m}));
    }catch(e){console.log('SITE_REDUCED_MOTION_ERROR='+JSON.stringify({path,error:thin(e.message)}))}
    await p.close();
  }
  await reducer.close();
  await browser.close();
  const byStatus={};reports.filter(x=>!x.test).forEach(r=>byStatus[r.status]=(byStatus[r.status]||0)+1);
  const issues={badStatus:reports.filter(x=>!x.test&&x.status!==200).map(x=>({path:x.path,width:x.width,status:x.status,error:x.error})),
    overflows:reports.filter(x=>!x.test&&x.overflowX>3).map(x=>({path:x.path,width:x.width,px:x.overflowX})),
    jsErrors:reports.filter(x=>!x.test&&x.jsErrors?.length).map(x=>({path:x.path,width:x.width,errors:x.jsErrors})),
    images:reports.filter(x=>!x.test&&(x.brokenImages?.length||x.missingAlt>0)).map(x=>({path:x.path,width:x.width,missingAlt:x.missingAlt,broken:x.brokenImages})),
    a11y:accessibility.filter(x=>x.violations?.length).map(x=>({path:x.path,issues:x.violations.map(y=>({id:y.id,impact:y.impact,count:y.count}))}))};
  fs.writeFileSync('sitewide-visual.json',JSON.stringify({scope:paths,widths:[390,1440],when:new Date().toISOString(),results:reports,axe:accessibility,issues,screenshotErrors:failures},null,2));
  console.log('SITEWIDE_BROWSER_SUMMARY='+JSON.stringify({paths:paths.length,viewports:2,testedPages:reports.filter(x=>!x.test).length,statuses:byStatus,issueCounts:Object.fromEntries(Object.entries(issues).map(([k,v])=>[k,v.length])),issues,elapsedSeconds:Math.round((Date.now()-start)/1000)}));
})().catch(e=>{console.error('SITEWIDE_AUDIT_FATAL',e.stack);process.exit(1)});
