const {chromium}=require('playwright');
const AxeBuilder=require('@axe-core/playwright').default;
const fs=require('fs');
const BASE='https://zomorodmelal.ir/';
const widths=[320,390,768,1024,1440,1920];
const out={date:new Date().toISOString(),url:BASE,results:[],a11y:[],brokenLinks:[],warnings:[],reducedMotion:null};
function trim(s,n=120){return String(s||'').replace(/\s+/g,' ').trim().slice(0,n)}
function emit(key,val){console.log(key+'='+JSON.stringify(val))}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 for(const width of widths){
  const context=await browser.newContext({viewport:{width,height:900},deviceScaleFactor:1});
  const page=await context.newPage();
  const errors=[],failed=[],responses=[];
  page.on('pageerror',e=>errors.push(trim(e.message)));
  page.on('console',e=>{if(e.type()==='error')errors.push('console: '+trim(e.text(),180))});
  page.on('requestfailed',r=>failed.push({url:r.url(),reason:r.failure()?.errorText}));
  page.on('response',r=>{if(r.status()>=400)responses.push({url:r.url(),status:r.status()})});
  await page.addInitScript(()=>{
   window.__zmPerf={cls:0,lcp:0,shiftCount:0,longTasks:0};
   try{
    new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput){window.__zmPerf.cls+=e.value;window.__zmPerf.shiftCount++}}).observe({type:'layout-shift',buffered:true});
    new PerformanceObserver(list=>{for(const e of list.getEntries())window.__zmPerf.lcp=Math.max(window.__zmPerf.lcp,e.startTime)}).observe({type:'largest-contentful-paint',buffered:true});
    new PerformanceObserver(list=>{for(const e of list.getEntries())window.__zmPerf.longTasks++}).observe({type:'longtask',buffered:true});
   }catch(e){}
  });
  const t0=Date.now();
  const response=await page.goto(BASE+'?__home_template_audit='+width,{waitUntil:'domcontentloaded',timeout:60000});
  await page.locator('.topic-card').first().waitFor({state:'attached',timeout:25000});
  await page.waitForTimeout(1100);
  const data=await page.evaluate(()=>{
   const query=s=>[...document.querySelectorAll(s)];
   const compact=e=>{let r=e.getBoundingClientRect();return {x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height)}};
   const shown=e=>{const cs=getComputedStyle(e),r=e.getBoundingClientRect();return cs.display!=='none'&&cs.visibility!=='hidden'&&r.width>0&&r.height>0};
   const cards=query('.topic-card'),tracks=query('.card-track'),shelves=query('.orbit-shelf');
   const nav=query('header a, nav a').filter(shown);
   const imgs=query('img'),imageSrc=new Map();
   imgs.forEach(im=>{const url=im.currentSrc||im.src;imageSrc.set(url,(imageSrc.get(url)||0)+1)});
   const cardNames=cards.map(c=>trimLocal(c.querySelector('.topic-name')?.textContent||c.textContent||'',80));
   function trimLocal(s,n=100){return (s||'').trim().replace(/\s+/g,' ').slice(0,n)}
   const anchors=query('a[href]').filter(shown);
   const navLinkTexts=nav.map(e=>({t:trimLocal(e.textContent,45),href:e.getAttribute('href')}));
   const ext=query('a[href]').filter(x=>x.href.startsWith(location.origin));
   const rawLinks=[...new Set(ext.map(x=>x.href.split('#')[0]))].filter(Boolean);
   const width=innerWidth,scrollX=Math.max(document.documentElement.scrollWidth,document.body.scrollWidth);
   const isEscaped=query('main *,#content *').filter(shown).filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.left < -4||r.right>innerWidth+4)});
   const badImages=imgs.filter(i=>i.complete && i.naturalWidth===0).map(i=>i.getAttribute('src'));
   const card=cards[0],cardStyle=card&&getComputedStyle(card),pseudo=card&&getComputedStyle(card,'::after');
   const firstLabel=card?.querySelector('.topic-name');
   const hs=query('h1'),h2=query('h2');
   const frame={avg:0,p95:0,max:0,sample:0};
   const navPerf=performance.getEntriesByType('navigation')[0];
   const resources=performance.getEntriesByType('resource');
   const totalEncoded=resources.reduce((a,r)=>a+(r.encodedBodySize||0),0);
   const uniqueImages=[...imageSrc.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8);
   const smallTargets=anchors.filter(x=>{let r=x.getBoundingClientRect();return r.height<24||r.width<24}).slice(0,15).map(x=>({name:trimLocal(x.textContent,35),box:compact(x)}));
   const stats={
     title:document.title,htmlLang:document.documentElement.lang,htmlDir:document.documentElement.dir,
     robots:document.querySelector('meta[name=robots]')?.content||null,
     description:document.querySelector('meta[name=description]')?.content||null,
     canonical:document.querySelector('link[rel=canonical]')?.href||null,
     viewport:document.querySelector('meta[name=viewport]')?.content||null,
     h1:hs.map(e=>trimLocal(e.textContent,160)),h2:h2.map(e=>trimLocal(e.textContent,100)).slice(0,20),
     rowCount:tracks.length,shelfCount:shelves.length,cardCount:cards.length,uniqueCardNames:new Set(cardNames).size,
     emptyCardNames:cardNames.filter(x=>!x).length,uniqueCardURLs:new Set(cards.map(c=>c.href||c.querySelector('a')?.href).filter(Boolean)).size,
     firstCardNames:cardNames.slice(0,8),
     navCount:nav.length,navSample:navLinkTexts.slice(0,16),
     bodyHeight:document.documentElement.scrollHeight,screenWidth:width,overflowX:scrollX-width,
     escapedCount:isEscaped.length,escapedExamples:isEscaped.slice(0,8).map(e=>({tag:e.tagName,cls:trimLocal(e.className,45),box:compact(e)})),
     images:imgs.length,badImages,missingAlt:imgs.filter(i=>!i.hasAttribute('alt')).length,emptyAlt:imgs.filter(i=>i.getAttribute('alt')==='').length,duplicates:uniqueImages,
     cardImage:!!card?.querySelector('img'),cardColor:cardStyle?.color,cardBG:cardStyle?.backgroundColor,cardBackdrop:cardStyle?.backdropFilter,
     cardShadow:cardStyle?.boxShadow?.slice(0,270),cardAnimation:cardStyle?.animationName,cardTransform:cardStyle?.transform,cardOverlay:pseudo?.content,cardOverlayEvents:pseudo?.pointerEvents,
     labelColor:firstLabel&&getComputedStyle(firstLabel).color,
     fixedBackground:getComputedStyle(document.body).backgroundAttachment,
     cssStyleTags:query('style').length,stylesheetLinks:query('link[rel=stylesheet]').length,
     activeAnimations:document.getAnimations().length,
     anchorCount:query('a[href]').length,uniqueInternalLinkCount:rawLinks.length,
     firstInternalURLs:rawLinks.slice(0,80),
     smallTargets,
     documentLoadMs:Math.round(navPerf?.domContentLoadedEventEnd||0), navTTFB:Math.round(navPerf?.responseStart||0),
     totalResponseBodyBytes:Math.round(totalEncoded),resourceCount:resources.length,
     resources:resources.map(r=>({url:r.name,bytes:r.encodedBodySize||0,duration:Math.round(r.duration)})).sort((a,b)=>b.bytes-a.bytes).slice(0,7),
     perf:{...window.__zmPerf}
   };
   return stats;
  });
  const frames=await page.evaluate(async()=>new Promise(done=>{const samples=[];let last=0;function tick(t){if(last)samples.push(t-last);last=t;if(samples.length<80)requestAnimationFrame(tick);else{let s=[...samples].sort((a,b)=>a-b);done({avg:Math.round(samples.reduce((a,b)=>a+b,0)/samples.length*10)/10,p95:Math.round(s[Math.floor(s.length*.95)]*10)/10,max:Math.round(s[s.length-1]*10)/10})}}requestAnimationFrame(tick)}));
  const res={width,status:response.status(),elapsedMs:Date.now()-t0,errors:errors.slice(0,12),failed:failed.slice(0,12),httpErrors:responses.slice(0,12),...data,frames};
  if(width===390||width===1440){
   const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']).analyze();
   const violations=axe.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,count:v.nodes.length,examples:v.nodes.slice(0,5).map(n=>({html:trim(n.html,180),failure:trim(n.failureSummary,160)}))}));
   out.a11y.push({width,violations,incomplete:axe.incomplete.map(v=>({id:v.id,count:v.nodes.length}))});
   await page.screenshot({path:'home-'+width+'.png',fullPage:false,animations:'disabled',timeout:20000});
   if(width===390)await page.screenshot({path:'home-390-full.png',fullPage:true,animations:'disabled',timeout:40000}).catch(e=>out.warnings.push('full screenshot: '+e.message));
  }
  if(width===1440){
   out.checkURLs=data.firstInternalURLs;
   await page.evaluate(()=>window.scrollTo(0,Math.floor(document.documentElement.scrollHeight/2)));
   await page.waitForTimeout(350);
   res.midScroll=await page.evaluate(()=>({y:scrollY,stickyHeaders:[...document.querySelectorAll('header')].filter(x=>getComputedStyle(x).position==='sticky').length}));
  }
  delete res.firstInternalURLs;
  out.results.push(res);
  emit('HOME_AUDIT_VIEWPORT',{width,status:res.status,rows:res.rowCount,shelves:res.shelfCount,cards:res.cardCount,uniqueNames:res.uniqueCardNames,uniqueDestinations:res.uniqueCardURLs,images:res.images,badImages:res.badImages,overflowX:res.overflowX,escaped:res.escapedCount,h1:res.h1,h2:res.h2,errors:res.errors.length,failed:res.failed.length,frames:res.frames,perf:res.perf,bodyHeight:res.bodyHeight,cssStyles:res.cssStyleTags,nav:res.navSample.slice(0,10)});
  await context.close();
 }
 const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});
 const page=await context.newPage();await page.goto(BASE+'?__home_audit_reduce_motion=1',{waitUntil:'domcontentloaded',timeout:50000});
 await page.locator('.topic-card').first().waitFor({timeout:15000});
 out.reducedMotion=await page.locator('.topic-card').first().evaluate(e=>({animation:getComputedStyle(e).animationName,transition:getComputedStyle(e).transitionDuration,media:matchMedia('(prefers-reduced-motion: reduce)').matches}));
 await context.close();
 const req=await browser.newContext();
 for(const url of (out.checkURLs||[]).slice(0,45)){
   try{const r=await req.request.get(url,{timeout:19000});if(r.status()>=400)out.brokenLinks.push({url,status:r.status()});}
   catch(e){out.brokenLinks.push({url,error:trim(e.message,120)})}
 }
 await req.close();
 fs.writeFileSync('home-audit.json',JSON.stringify(out,null,2));
 emit('HOME_AUDIT_AXE',out.a11y);
 emit('HOME_AUDIT_BROKEN_LINKS',out.brokenLinks);
 emit('HOME_AUDIT_REDUCED_MOTION',out.reducedMotion);
 emit('HOME_AUDIT_SUMMARY',{
  screens:out.results.length,overflow:out.results.filter(x=>x.overflowX>3).map(x=>({width:x.width,px:x.overflowX})),
  errors:out.results.reduce((a,x)=>a+x.errors.length,0),requestsFailed:out.results.reduce((a,x)=>a+x.failed.length,0),
  brokenLinks:out.brokenLinks.length,axe:out.a11y.map(x=>({width:x.width,violations:x.violations.map(v=>({id:v.id,n:v.count,impact:v.impact}))}))
 });
 await browser.close();
})().catch(e=>{console.error('HOME_AUDIT_FATAL',e.stack||e);process.exit(1)});
