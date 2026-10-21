// Read-only audit of live homepage rows. Never changes site contents or settings.
const {chromium} = require('playwright');
const fs = require('fs');
(async () => {
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const report={timestamp:new Date().toISOString(),url:'https://zomorodmelal.ir/',viewports:[]};
 for(const width of [1440,390,320]){
  const page=await browser.newPage({viewport:{width,height:900},deviceScaleFactor:1,isMobile:width<500,hasTouch:width<500});
  const errors=[],responseErrors=[];
  page.on('pageerror',x=>errors.push(String(x.message).slice(0,180)));
  page.on('console',x=>{if(x.type()==='error')errors.push('console: '+x.text().slice(0,180))});
  page.on('response',r=>{if(r.status()>=400)responseErrors.push({status:r.status(),url:r.url().slice(0,180)})});
  const response=await page.goto('https://zomorodmelal.ir/?__audit_home_row_visibility_20261019='+width,{
   waitUntil:'domcontentloaded',timeout:50000});
  await page.locator('.topic-card').first().waitFor({state:'attached',timeout:24000});
  await page.waitForTimeout(550);
  const start=await page.evaluate(()=>{
   const q=s=>[...document.querySelectorAll(s)];
   const shelves=q('.orbit-shelf');
   return {
    h1:q('h1').map(x=>x.textContent.trim()).slice(0,4),
    rows:shelves.length,tracks:q('.card-track').length,cards:q('.topic-card').length,
    shelfIds:shelves.map(x=>x.id),keys:shelves.map(x=>x.querySelector('.shelf-heading-line h3')?.textContent.trim()||''),
    existingContact:q('#zm-official-contacts-20261019').length,
    existingFooter:q('#site-footer').length,
    uninitialized:shelves.filter(x=>x.classList.contains('zm-home-shelf-offscreen')).map(x=>x.id),
    bodyScrollHeight:document.documentElement.scrollHeight,viewport:innerWidth,
    overflow:document.documentElement.scrollWidth-innerWidth,
    documentOuterHTMLCount:document.documentElement.outerHTML.length
   };
  });
  console.log('ROW_AUDIT_INITIAL='+JSON.stringify({width,...start}));
  // Reproduce a real fast finger-swipe scenario: jump immediately to the
  // last shelf before normal sequential sweep, then inspect lazy activation.
  await page.evaluate(()=>document.querySelector('#orbit-17')?.scrollIntoView({behavior:'instant',block:'center'}));
  await page.waitForTimeout(450);
  const fastScroll=await page.evaluate(()=>{
    const last=document.querySelector('#orbit-17');
    const r=last?.getBoundingClientRect(),c=last&&getComputedStyle(last);
    return {present:!!last,visible:!!last&&r.height>0&&r.bottom>0&&r.top<innerHeight&&
       c.display!=='none'&&c.visibility!=='hidden'&&Number(c.opacity)>.05,
       className:last?.className,opacity:c?.opacity,box:r&&[r.y,r.height],
       scrollY,viewport:innerWidth};
  });
  console.log('ROW_AUDIT_FAST_SCROLL='+JSON.stringify({width,...fastScroll}));
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.waitForTimeout(150);
  const perRow=[];
  for(let i=0;i<start.rows;i++){
   await page.evaluate(i=>{const s=document.querySelectorAll('.orbit-shelf')[i];
      if(s) s.scrollIntoView({behavior:'instant',block:'center',inline:'nearest'});
   },i);
   await page.waitForTimeout(150);
   const sample=await page.evaluate(i=>{
    const shelf=document.querySelectorAll('.orbit-shelf')[i];
    const style=getComputedStyle(shelf),rect=shelf.getBoundingClientRect();
    const track=shelf.querySelector('.card-track');
    const tstyle=track&&getComputedStyle(track),tr=track?.getBoundingClientRect();
    const cards=[...shelf.querySelectorAll('.topic-card')];
    const header=shelf.querySelector('.shelf-heading-line h3');
    const visible=rect.height>24&&style.display!=='none'&&style.visibility!=='hidden'&&
      Number(style.opacity)>0.05&&rect.width>24&&rect.bottom>0&&rect.top<innerHeight;
    const visibleTrack=!!track&&tr.height>20&&tstyle.display!=='none'&&tstyle.visibility!=='hidden'&&Number(tstyle.opacity)>0.05;
    const firstCard=cards[0],cr=firstCard?.getBoundingClientRect(),cs=firstCard?getComputedStyle(firstCard):null;
    return {
      index:i,id:shelf.id,heading:header?.textContent.trim()||'',
      classes:shelf.className,cardCount:cards.length,
      cardsNamed:cards.filter(c=>c.querySelector('.topic-name')?.textContent.trim()).length,
      visible,visibleTrack,
      shelfBox:[Math.round(rect.x),Math.round(rect.y),Math.round(rect.width),Math.round(rect.height)],
      trackBox:tr?[Math.round(tr.x),Math.round(tr.y),Math.round(tr.width),Math.round(tr.height)]:null,
      shelfDisplay:style.display,shelfOpacity:style.opacity,shelfVisibility:style.visibility,
      trackDisplay:tstyle?.display,trackOpacity:tstyle?.opacity,trackVisibility:tstyle?.visibility,
      firstCardSize:cr?[Math.round(cr.width),Math.round(cr.height)]:null,
      firstCardVisibility:cs?.visibility,
      lastCardLabel:cards.at(-1)?.querySelector('.topic-name')?.textContent.trim().slice(0,60)||''
    };
   },i);
   perRow.push(sample);
  }
  const last=await page.evaluate(()=>{
   const shelves=[...document.querySelectorAll('.orbit-shelf')];
   const contacts=document.querySelector('#zm-official-contacts-20261019');
   const footer=document.querySelector('#site-footer');
   const rows=[...document.querySelectorAll('.card-track')];
   const isLastBeforeContact=shelves.length>0&&
     shelves.at(-1).compareDocumentPosition(contacts)&Node.DOCUMENT_POSITION_FOLLOWING;
   const contactBeforeFooter=!!contacts&&!!footer&&contacts.nextElementSibling===footer;
   const n=contacts?.getBoundingClientRect(),f=footer?.getBoundingClientRect();
   return {
     ids:shelves.map(x=>x.id),
     uniqueIDs:new Set(shelves.map(x=>x.id)).size,
     cardCounts:shelves.map(x=>x.querySelectorAll('.topic-card').length),
     contactBeforeFooter:!!contactBeforeFooter,
     lastShelfBeforeContact:!!isLastBeforeContact,
     contactCount:document.querySelectorAll('#zm-official-contacts-20261019').length,
     contactBox:n?[Math.round(n.width),Math.round(n.height)]:null,
     footerBox:f?[Math.round(f.width),Math.round(f.height)]:null,
     backdrop:getComputedStyle(document.body).backgroundAttachment,
     headerGlass:!!document.getElementById('zm-home-header-footer-glass-20261019'),
     copyGlass:!!document.getElementById('zm-home-copy-cinematic-glass-20261019'),
     rowGlass:!!document.getElementById('zm-glass-row-headers-20261018'),
     contactGlass:!!document.getElementById('zm-official-contacts-glass-css-20261019'),
     shellChildren:[...document.querySelectorAll('#main-view > *')].map(x=>x.id||x.className),
     totalHeight:document.documentElement.scrollHeight,
     pageWidth:document.documentElement.scrollWidth
   };
  });
  const ids=perRow.map(r=>r.id),expected=Array.from({length:29},(_,i)=>'orbit-'+String(i+1).padStart(2,'0'));
  const result={
   width,httpStatus:response.status(),initial:start,fastScroll,
   summary:{
    rows:perRow.length,visibleRows:perRow.filter(x=>x.visible).length,
    invisibleRows:perRow.filter(x=>!x.visible).map(x=>({id:x.id,title:x.heading,reason:x.classes,height:x.shelfBox[3],opacity:x.shelfOpacity})),
    unpopulatedRows:perRow.filter(x=>x.cardCount===0).map(x=>x.id),
    invisibleTracks:perRow.filter(x=>!x.visibleTrack).map(x=>x.id),
    expectedIdsMissing:expected.filter(x=>!ids.includes(x)),
    unexpectedIds:ids.filter(x=>!expected.includes(x)),
    cards:perRow.reduce((a,b)=>a+b.cardCount,0),
    rowsWithNoTitle:perRow.filter(x=>!x.heading).map(x=>x.id),
    gaps:perRow.filter((x,i)=>i&&x.shelfBox[3]===0).map(x=>x.id),
   },
   perRow,last,errors,responseErrors
  };
  report.viewports.push(result);
  console.log('ROW_AUDIT_SUMMARY='+JSON.stringify({width,status:result.httpStatus,...result.summary,fastScroll,last,jsErrors:errors.slice(0,5),httpErrors:responseErrors.slice(0,5)}));
  console.log('ROW_AUDIT_EACH='+JSON.stringify({width,rows:perRow.map(r=>({id:r.id,title:r.heading,cards:r.cardCount,shown:r.visible,track:r.visibleTrack,opacity:r.shelfOpacity,height:r.shelfBox[3],classes:r.classes}))}));
  try{
   await page.locator('#zm-official-contacts-20261019').scrollIntoViewIfNeeded({timeout:5000});
   await page.screenshot({path:'home-contact-'+width+'.png',animations:'disabled',timeout:10000});
  }catch(e){console.log('ROW_AUDIT_SCREENSHOT_WARNING='+String(e).slice(0,180))}
  await page.close();
 }
 fs.writeFileSync('row-audit-20261019.json',JSON.stringify(report,null,2));
 await browser.close();
 console.log('ROW_AUDIT_READ_ONLY_DONE=yes');
})().catch(e=>{console.error('ROW_AUDIT_FATAL',e.stack||e);process.exitCode=1});
