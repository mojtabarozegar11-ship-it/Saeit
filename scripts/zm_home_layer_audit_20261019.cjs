const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:900},isMobile:width<500,hasTouch:width<500});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('https://zomorodmelal.ir/?__glass_overlap_preflight='+width,{waitUntil:'domcontentloaded',timeout:50000});
  await page.locator('.topic-card').first().waitFor({timeout:25000});
  await page.waitForTimeout(800);
  const data=await page.evaluate(()=>{
   const $=q=>[...document.querySelectorAll(q)];
   const brief=e=>{if(!e)return null;const c=getComputedStyle(e),r=e.getBoundingClientRect();
    return {tag:e.tagName,id:e.id,classes:String(e.className).slice(0,140),text:e.textContent.trim().slice(0,120),
    box:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],display:c.display,
    position:c.position,opacity:c.opacity,overflow:c.overflow,transform:c.transform,filter:c.backdropFilter,
    z:c.zIndex,padding:c.padding,margin:c.margin,align:c.alignItems,lineHeight:c.lineHeight,
    bg:c.backgroundImage.slice(0,170),pseudoBefore:{z:getComputedStyle(e,'::before').zIndex,position:getComputedStyle(e,'::before').position,background:getComputedStyle(e,'::before').backgroundImage.slice(0,150)}};
   };
   const shells=['header.topbar','.hero-text','.orbit-intro','.shelf-heading-line','.shelf-explanation','.shelf-desc','.shelf-head','.orbit-shelf','.shelf-title','.card-track','.topic-card','#zm-official-contacts-20261019','.zm-contact-heading','.zm-contact-card','#site-footer .footer-shell','.footer-grid > *','.footer-copyright','.footer-intro'];
   const samples=shells.map(sel=>({sel,count:$(sel).length,first:brief($(sel)[0]),last:brief($(sel).at(-1))}));
   const emptyH1=$('h1').filter(x=>!x.textContent.trim()).map(x=>({html:x.outerHTML.slice(0,850),parent:x.parentElement?.outerHTML.slice(0,1200),style:brief(x)}));
   const gapSelectors=['.hero-text','.orbit-intro','.shelf-heading-line','.shelf-explanation','#zm-official-contacts-20261019','.footer-copyright'];
   const boundaries=gapSelectors.map(sel=>{
    const e=$(sel)[0];if(!e)return {sel,missing:true};const cr=e.getBoundingClientRect(),txt=[];
    for(const descendant of e.querySelectorAll('h1,h2,h3,h4,p,span,strong,small,a')){
     const rr=descendant.getBoundingClientRect();
     const d=getComputedStyle(descendant);
     if(rr.width<3||rr.height<3)continue;
     txt.push({tag:descendant.tagName,text:descendant.textContent.trim().slice(0,60),
      dTop:Math.round(rr.top-cr.top),dBottom:Math.round(rr.bottom-cr.top),
      boxH:Math.round(cr.height),z:d.zIndex,position:d.position,overflow:d.overflow,
      pTop:d.paddingTop,pBottom:d.paddingBottom});
    }
    return {sel,panel:brief(e),kids:txt.slice(0,18),
      under:txt.filter(x=>x.dBottom>cr.height+3||x.dTop< -3).slice(0,9)};
   });
   const off=$('.zm-home-shelf-offscreen');
   const cardStyles=$('.topic-card').slice(0,2).map(brief);
   const styleTags=$('style').map(x=>({id:x.id,len:x.textContent.length})).filter(x=>x.id||x.len>2000).slice(-25);
   const animations=document.getAnimations().reduce((o,a)=>{let n=a.effect?.target?.className||a.effect?.target?.tagName||'unknown';n=String(n).slice(0,60);o[n]=(o[n]||0)+1;return o},{});
   return {html:document.documentElement.outerHTML.length,bodyHtml:document.body.innerHTML.length,
    h1s:$('h1').map(x=>({text:x.textContent.slice(0,100),html:x.outerHTML.slice(0,500)})),
    emptyH1,offscreenCount:off.length,offscreenIDs:off.map(x=>x.id),
    cardCount:$('.topic-card').length,shelfCount:$('.orbit-shelf').length,
    visibilityStyle:styleTags,
    animationCount:document.getAnimations().length,animations,scrollHeight:document.documentElement.scrollHeight,
    width:document.documentElement.scrollWidth,viewport:innerWidth,
    samples,boundaries,cardStyles,
    scripts:$('script').map(x=>({src:x.src,inlineLen:x.textContent.length})).slice(-20)};
  });
  console.log('DEEP_GLASS_PREFLIGHT='+JSON.stringify({width,...data,errors}).slice(0,85000));
  await page.close();
 }
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
