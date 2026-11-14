/* Production interior-page visual COLOR census only.
 * No new website/template. No writes, forms, login or payment actions.
 */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const {PAGES,classify,summarize}=require('./zomorod_interior_census_policy_20261114.cjs');
const excludedHomepage='/';
const out=path.join(process.env.RUNNER_TEMP||'/tmp','zm-interior-olive-palette-readonly');
fs.mkdirSync(out,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const all=[];
  try{

    for(const uri of PAGES){
      const item={path:uri,attempts:[],censusComplete:false};
      for(let attempt=1;attempt<=2;attempt++){
        const p=await browser.newPage({viewport:{width:390,height:850},
          locale:'fa-IR',reducedMotion:'reduce'});
        const started=Date.now();
        try{
          // One sequential browser page; bounded retry only if the first fetch fails.
          const response=await p.goto('https://zomorodmelal.ir'+uri,{
            waitUntil:'domcontentloaded',timeout:attempt===1?16000:12000});
          delete item.error;
          item.http=response?.status();
          item.documentPath=new URL(p.url()).pathname;
          if(item.http!==200 || item.documentPath!==uri){
            item.attempts.push({number:attempt,ok:false,http:item.http,
              documentPath:item.documentPath,durationMs:Date.now()-started});
            // 4xx/mismatched paths are definitive observations, not timeouts.
            if(item.documentPath!==uri || (item.http>=400&&item.http<500))break;
            if(attempt<2)await new Promise(r=>setTimeout(r,450));
            continue;
          }
          await p.waitForTimeout(90);
        const styles=await p.evaluate(()=>{
          const rgb=(s)=>{
            const a=(s||'').match(/^rgba?\(([^)]+)\)/);
            if(!a)return null;
            const parts=a[1].split(',').map(x=>parseFloat(x.trim()));
            if(parts.length>3 && parts[3]<0.99)return null; // transparent is not black
            return parts.slice(0,3);
          };
          const info=(el)=>{
            const cs=getComputedStyle(el),box=el.getBoundingClientRect();
            return {tag:el.tagName.toLowerCase(),
              id:(el.id||'').slice(0,42),
              className:typeof el.className==='string'?el.className.split(/\s+/).slice(0,4).join(' '):'',
              w:Math.round(box.width),h:Math.round(box.height),
              top:Math.round(box.top),bg:cs.backgroundColor,
              bgImage:cs.backgroundImage.slice(0,115),
              borderTop:cs.borderTopColor,
              borderBottom:cs.borderBottomColor,
              color:cs.color};
          };
          const structural=[document.body,document.querySelector('main'),
            document.querySelector('header'),document.querySelector('footer'),
            ...[...document.querySelectorAll('body > section, main > section, .ticker, .tools, .footer, .topline, .header')]
              .filter(Boolean).slice(0,22)].filter(Boolean).map(info);
          const bands=structural.filter(x=>x.w>=innerWidth*.88&&x.h>=20);
          const blackBands=bands.filter(x=>{
            const c=rgb(x.bg);
            return c && Math.max(...c)<44 && Math.max(...c)-Math.min(...c)<=7;
          });
          return {
            viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
            bodyBg:getComputedStyle(document.body).backgroundColor,
            bodyImage:getComputedStyle(document.body).backgroundImage.slice(0,130),
            themeColor:document.querySelector('meta[name=theme-color]')?.content||null,
            contentType:document.contentType,
            title:document.title.slice(0,95),
            structural:bands,
            blackBands:blackBands.map(x=>({tag:x.tag,className:x.className,id:x.id,bg:x.bg,h:x.h})),
            visibleBackgroundPalette:[...new Set(bands.map(x=>x.bg))].slice(0,20)
          };
        });

          Object.assign(item,styles,{censusComplete:true});
          // The public HTML marker does NOT prove the identity of a host file.
          const marker=({
            '/ghanadi/':'ZM_INTERIOR_OLIVE_SCOPED_20261114',
            '/ghanadi/cafe-shiraz/':'ZM_INTERIOR_OLIVE_CAFE_20261114',
            '/auctions/':'zm-auctions-inner-olive-20261114'})[uri];
          if(marker){
            item.expectedMarker=marker;
            item.markerInPublicHtml=await p.evaluate(m=>
              document.documentElement.outerHTML.includes(m),marker);
            item.hostFileIdentityProven=false;
          }
          item.attempts.push({number:attempt,ok:true,http:item.http,
            durationMs:Date.now()-started});
          delete item.error;
          break;
        }catch(e){
          delete item.http;
          delete item.documentPath;
          item.error=String(e).slice(0,210);
          item.censusComplete=false;
          item.attempts.push({number:attempt,ok:false,
            error:item.error,durationMs:Date.now()-started});
          if(attempt<2)await new Promise(r=>setTimeout(r,450));
        }finally{
          await p.close();
        }
      }
      item.censusStatus=classify(item);
      console.log('ZM_INTERIOR_PALETTE '+JSON.stringify(item));
      all.push(item);
    }
  }finally{await browser.close()}

  const summary=summarize(all,PAGES);
  console.log('ZM_INTERIOR_PALETTE_SUMMARY '+JSON.stringify(summary));
  fs.writeFileSync(path.join(out,'computed-palette.json'),JSON.stringify({summary,pages:all},null,2));
  if(process.env.GITHUB_STEP_SUMMARY){
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
      '\n## Existing interior pages: computed backgrounds (no site changes)\n\n'+
      '| URL | Background | Result | Dark full-width bands | HTTP | Attempts |\n'+
      '|---|---|---|---:|---:|---:|\n'+
      all.map(x=>'| '+x.path+' | '+(x.bodyBg||'unavailable')+
        ' | '+x.censusStatus+' | '+(x.blackBands?.length||0)+
        ' | '+(x.http||0)+' | '+x.attempts.length+' |\n').join('')+
      '\n**Verified DOM:** '+summary.inspected+'/'+summary.total+
      '; **transient failures recovered:** '+summary.transientFailures.length+
      '; **unknown routes:** '+summary.failedRoutes.length+
      '. Homepage excluded. Timeouts and missing pages are never counted as success.\n');
  }
  if(!summary.allRoutesInspected)process.exitCode=1;
})().catch(e=>{console.error('ZM_INTERIOR_PALETTE_FATAL',e);process.exitCode=1});
