'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const mobile of [false,true]){
   const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1100,height:800},isMobile:mobile,hasTouch:mobile});
   const page=await context.newPage();
   await page.addInitScript(()=>{Math.random=()=>0});
   await page.goto('http://127.0.0.1:8766/games/echoform/signal-lattice.html');
   await page.locator('#start').click();
   await page.waitForFunction(()=>!document.querySelector('.tile').disabled,{timeout:5000});
   await page.locator('.tile').nth(1).focus();
   await page.keyboard.press('1');
   assert.equal(await page.locator('#progress').innerText(),'1 / 1','keyboard shortcut must work while a tile has focus');
   await context.close();
  }
  const context=await browser.newContext({viewport:{width:1000,height:800}});
  const page=await context.newPage();
  await page.addInitScript(()=>{const original=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key==='mpw-crown-v10-save')throw Error('simulated quota');return original.call(this,key,value)}});
  await page.goto('http://127.0.0.1:8766/games/crown-defender/index.html');
  await page.locator('#autofire').evaluate(el=>el.click());
  assert.match(await page.locator('#announcement').innerText(),/Progress not saved on this device/);
  await context.close();
  console.log('G01_R27_ROTATION_BROWSER_PASS echoform desktop/mobile focused keyboard; crown save failure notice');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
