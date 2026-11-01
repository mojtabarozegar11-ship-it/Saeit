'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const mobile of [false,true]){
   const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:800},isMobile:mobile,hasTouch:mobile});
   await page.goto(process.env.GAME_URL||'http://127.0.0.1:8765/');
   await page.waitForFunction(()=>!!window.RamadanWarDebug);
   await page.evaluate(()=>window.RamadanWarDebug.start());
   await page.waitForTimeout(250);
   const status=await page.locator('#objectiveRange').innerText();
   const arrow=await page.locator('#objectiveArrow').evaluate(el=>({visibility:el.style.visibility,hidden:el.getAttribute('aria-hidden')}));
   if(status.includes('مسیر بسته است')){assert.equal(arrow.visibility,'hidden');assert.equal(arrow.hidden,'true')}
   else if(status.includes('خانه مسیر')||status.includes('متر')){assert.equal(arrow.visibility,'visible');assert.equal(arrow.hidden,'false')}
   else throw Error('Unexpected objective status: '+status);
   await page.close();
  }
  console.log('G01_R27_OBJECTIVE_BROWSER_PASS desktop/mobile guidance and arrow accessibility');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
