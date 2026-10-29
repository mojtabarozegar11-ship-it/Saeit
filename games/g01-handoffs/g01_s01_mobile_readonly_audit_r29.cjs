#!/usr/bin/env node
// G-01 -> S-01 read-only mobile checkout accessibility handoff.
// No clicks, submissions, cookies, authentication, screenshots, or customer content in output.
'use strict';
const fs=require('node:fs');
const {chromium}=require('playwright');
const target=process.argv[2]||'--self-test';
const ALLOWED=new Set(['mojplaywin.com','www.mojplaywin.com','localhost','127.0.0.1']);
async function audit(page){
 return page.evaluate(()=>{
  const interactive='button,a[href],input:not([type="hidden"]),select,textarea,[role="button"]';
  const nodes=[...document.querySelectorAll(interactive)].filter(el=>{
   const s=getComputedStyle(el),r=el.getBoundingClientRect();
   return s.visibility!=='hidden'&&s.display!=='none'&&r.width>0&&r.height>0;
  });
  const named=el=>Boolean((el.getAttribute('aria-label')||'').trim()||(el.getAttribute('title')||'').trim()||(el.innerText||'').trim()||(el.labels&&[...el.labels].some(x=>x.textContent.trim())));
  const tiny=nodes.filter(el=>{const r=el.getBoundingClientRect();return r.width<24||r.height<24}).length;
  const unlabeled=nodes.filter(el=>!named(el)).length;
  const overflow=document.documentElement.scrollWidth>document.documentElement.clientWidth+4;
  return {viewport:innerWidth,interactive:nodes.length,tinyTargets:tiny,unlabeledControls:unlabeled,horizontalOverflow:overflow,forms:document.forms.length};
 });
}
(async()=>{
 const isFixture=target==='--self-test'||target.startsWith('--fixture=');
 if(!isFixture){const u=new URL(target);if(u.protocol!=='https:'&&!(['localhost','127.0.0.1'].includes(u.hostname)&&u.protocol==='http:'))throw Error('Only HTTPS MojPlayWin or local fixture allowed');if(!ALLOWED.has(u.hostname)||u.username||u.password)throw Error('Unapproved target');}
 const browser=await chromium.launch({headless:true});
 try{
  const output=[];
  for(const width of [390,1280]){
   const context=await browser.newContext({viewport:{width,height:844},isMobile:width===390,hasTouch:width===390});
   const page=await context.newPage();
   await page.route('**/*',route=>['GET','HEAD'].includes(route.request().method())?route.continue():route.abort());
   if(target==='--self-test')await page.setContent('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><main><label for="email">Email</label><input id="email" style="width:180px;height:40px"><button style="width:120px;height:44px">View invoice</button></main></body></html>');
   else if(target.startsWith('--fixture='))await page.setContent(fs.readFileSync(target.slice(10),'utf8'));
   else await page.goto(target,{waitUntil:'domcontentloaded',timeout:25000});
   const result=await audit(page);
   output.push({device:width===390?'mobile':'desktop',...result});
   await context.close();
  }
  if(target==='--self-test'&&!output.every(x=>x.interactive===2&&x.tinyTargets===0&&x.unlabeledControls===0&&!x.horizontalOverflow))throw Error('Self-test failed');
  console.log(JSON.stringify({mode:isFixture?'offline-fixture':'GET-only',status:'OBSERVATION_ONLY_NOT_BUYER_PROOF',results:output},null,2));
  if(!isFixture&&output.some(x=>x.horizontalOverflow||x.unlabeledControls>0))process.exitCode=2;
 }finally{await browser.close()}
})().catch(e=>{console.error('G01_S01_AUDIT_ERROR:',e.message);process.exitCode=1});
