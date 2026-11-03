'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const mobile of [false,true]){
   const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:800},isMobile:mobile,hasTouch:mobile});
   await page.goto(process.env.GAME_URL||'http://127.0.0.1:8765/');
   await page.waitForFunction(()=>Boolean(window.RamadanWarDebug));
   const start=await page.evaluate(()=>{const d=window.RamadanWarDebug;d.start();return d.qaMove(8.5,3.5)});
   assert.equal(start,true,'activation target should be reachable');
   await page.waitForFunction(()=>document.querySelector('#objectiveRange')?.textContent.includes('تعامل آماده است'));
   assert.deepEqual(await page.locator('#objectiveArrow').evaluate(e=>[e.style.visibility,e.getAttribute('aria-hidden')]),['hidden','true']);
   const defend=await page.evaluate(()=>{const d=window.RamadanWarDebug;d.qaMission(1);return d.qaMove(8.5,7.5)});
   assert.equal(defend,true,'defense target should be reachable');
   await page.waitForFunction(()=>document.querySelector('#objectiveRange')?.textContent.includes('در منطقه دفاع'));
   assert.deepEqual(await page.locator('#objectiveArrow').evaluate(e=>[e.style.visibility,e.getAttribute('aria-hidden')]),['hidden','true']);
   const extract=await page.evaluate(()=>{const d=window.RamadanWarDebug;d.qaMission(4);return d.qaMove(13.5,13.5)});
   assert.equal(extract,true,'extraction target should be reachable');
   await page.waitForFunction(()=>document.querySelector('#objectiveRange')?.textContent.includes('ابتدا دشمنان'));
   assert.deepEqual(await page.locator('#objectiveArrow').evaluate(e=>[e.style.visibility,e.getAttribute('aria-hidden')]),['hidden','true']);
   await page.close();
  }
  console.log('G01_R28_ARRIVAL_BROWSER_PASS desktop/mobile activation, defense and extraction gating');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
