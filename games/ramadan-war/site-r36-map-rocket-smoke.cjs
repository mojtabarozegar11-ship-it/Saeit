'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const mobile of [false,true]){
   const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:800},isMobile:mobile,hasTouch:mobile});
   const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   await page.goto(process.env.GAME_URL||'http://127.0.0.1:8765/');
   await page.waitForFunction(()=>Boolean(window.RamadanWarDebug));
   await page.evaluate(()=>window.RamadanWarDebug.start());
   await page.keyboard.press('m');
   assert.equal(await page.locator('#mapToggle').getAttribute('aria-pressed'),'true');
   assert.equal(await page.locator('#tacticalMap').isVisible(),true);
   await page.locator('#mapToggle').focus();
   await page.keyboard.press('m');
   assert.equal(await page.locator('#mapToggle').getAttribute('aria-pressed'),'true','focused button must not trigger gameplay shortcut');
   await page.evaluate(()=>document.activeElement?.blur());
   await page.keyboard.press('m');
   assert.equal(await page.locator('#mapToggle').getAttribute('aria-pressed'),'false');
   const blocked=await page.evaluate(()=>{const d=window.RamadanWarDebug;d.qaMove(2.5,7.5);d.spawnTestEnemy();const before=d.getState().rockets;d.rocket();return {before,after:d.getState().rockets}});
   assert.equal(blocked.after,blocked.before,'wall-occluded enemy must not spend a rocket');
   const clear=await page.evaluate(()=>{const d=window.RamadanWarDebug;d.qaMove(6.5,7.5);const before=d.getState().rockets;d.rocket();return {before,after:d.getState().rockets}});
   assert.equal(clear.after,clear.before-1,'visible enemy must be targetable');
   assert.deepEqual(errors,[],'browser script errors');
   await page.close();
  }
  console.log('G01_R36_BROWSER_PASS desktop/mobile radar shortcut, focus guard, rocket LOS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
