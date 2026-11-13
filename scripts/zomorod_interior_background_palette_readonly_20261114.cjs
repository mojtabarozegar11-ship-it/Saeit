/* Production interior-page visual COLOR census only.
 * No new website/template. No writes, forms, login or payment actions.
 */
'use strict';
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const pages=['/about/','/company/','/services/','/research/','/agriculture/',
'/industry/','/knowledge/','/economy/','/market/','/contact/','/store/',
'/tala/','/ghanadi/','/faremah/','/amozeshgah/','/business/','/apps/',
'/games/','/news/','/newsletter/','/studio/','/auctions/'];
const excludedHomepage='/';
const out=path.join(process.env.RUNNER_TEMP||'/tmp','zm-interior-olive-palette-readonly');
fs.mkdirSync(out,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const all=[];
  try{
    for(const uri of pages){
      const p=await browser.newPage({viewport:{width:390,height:850},
        locale:'fa-IR',reducedMotion:'reduce'});
      const item={path:uri};
      try{
        const response=await p.goto('https://zomorodmelal.ir'+uri,{
          waitUntil:'domcontentloaded',timeout:24000});
        await p.waitForTimeout(90);
        const styles=await p.evaluate(()=>{
          const rgb=(s)=>{
            const a=(s||'').match(/^rgba?\(([^)]+)\)/);
            return a?a[1].split(',').slice(0,3).map(v=>+parseFloat(v.trim())):null;
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
            return c && Math.max(...c)<44;
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
        Object.assign(item,{http:response?.status(),...styles});
      }catch(e){item.error=String(e).slice(0,210);}
      console.log('ZM_INTERIOR_PALETTE '+JSON.stringify(item));
      all.push(item);
      await p.close();
    }
  }finally{await browser.close()}
  const ok=all.filter(x=>x.http===200).length;
  const summary={total:all.length,http200:ok,fetchErrors:all.length-ok,
    pageSourcesUnchanged:true,liveWrites:0,formsSubmitted:0,
    excludedHomepage,pathsWithBlackBands:all.filter(x=>x.blackBands?.length).map(x=>x.path)};
  console.log('ZM_INTERIOR_PALETTE_SUMMARY '+JSON.stringify(summary));
  fs.writeFileSync(path.join(out,'computed-palette.json'),JSON.stringify({summary,pages:all},null,2));
  if(process.env.GITHUB_STEP_SUMMARY){
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
      '\n## Existing interior pages: computed background palette (no changes)\n\n'+
      '| URL | Background | Dark full-width bands | HTTP |\n|---|---|---:|---:|\n'+
      all.map(x=>'| '+x.path+' | '+(x.bodyBg||'no response')+
        ' | '+(x.blackBands?.length||0)+' | '+(x.http||0)+' |\n').join('')+
      '\nHomepage excluded. This is a style census, not release or approved redesign.\n');
  }
  if(ok<all.length-3)process.exitCode=1;
})().catch(e=>{console.error('ZM_INTERIOR_PALETTE_FATAL',e);process.exitCode=1});
