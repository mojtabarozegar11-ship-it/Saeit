'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const root=process.env.G01_ROOT||'http://127.0.0.1:8766';
 try{
  for(const mobile of [false,true]){
   const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:800},isMobile:mobile,hasTouch:mobile});
   await page.goto(root+'/templates/studio_raha/index.html');
   await page.locator('[data-play="0"]').click();
   await page.evaluate(()=>document.activeElement?.blur());
   for(let n=0;n<3;n++)await page.keyboard.press('Space');
   assert.match(await page.locator('#runScore').innerText(),/3 \/ 8/,'Roham repeated Space jumps');
   await page.locator('#gameOverlay [data-close]').first().click();
   await page.locator('[data-play="0"]').click();
   await page.evaluate(()=>document.activeElement?.blur());
   await page.keyboard.press('Space');
   assert.match(await page.locator('#runScore').innerText(),/1 \/ 8/,'Roham reopened runner must not retain old listener');
   await page.goto(root+'/templates/taniya_studio/index.html');
   await page.locator('[data-game="Cake Maker"]').click();
   await page.locator('[data-action="candle"]').click();
   assert.equal((await page.locator('#cakepreview').innerText()).split('🕯️').length-1,1,'One tap adds exactly one candle');
   await page.locator('[data-action="candle"]').click();
   assert.equal((await page.locator('#cakepreview').innerText()).split('🕯️').length-1,2,'Second tap adds exactly two candles');

   await page.locator('[data-top="🌼"]').click();
   const decorated=await page.locator('#cakepreview').innerText();
   assert.equal((decorated.match(/🕯️/gu)||[]).length,2,'Taniya candles persist after topping switch');
   assert.ok(decorated.includes('🌼'),'Taniya topping stays visible');
   await page.locator('[data-action="cake-reset"]').click();
   assert.equal((await page.locator('#cakepreview').innerText()).includes('🕯️'),false,'Cake reset clears decorations');
   await page.close();
  }
  console.log('G01_R28_STUDIOS_BROWSER_PASS desktop/mobile Roham keyboard and Taniya cake state');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
