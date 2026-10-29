'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const device of [
   {name:'desktop',viewport:{width:1280,height:800}},
   {name:'mobile',viewport:{width:390,height:844},isMobile:true,hasTouch:true}
  ]){
   const context=await browser.newContext(device);
   const page=await context.newPage();
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const response=await page.goto('http://127.0.0.1:8766/games/arrow-escape/',{waitUntil:'domcontentloaded'});
   assert.equal(response.status(),200);
   for(const key of ['Enter','Space']){
    const choice=await page.evaluate(()=>{
     const puzzle=window.ArrowMazeDebug.getPuzzle();
     const piece=puzzle.faces.flatMap(f=>f.pieces).find(p=>window.ArrowCubeCore.canExit(puzzle,p,new Set(
      puzzle.faces.flatMap(f=>f.pieces).filter(p=>!document.querySelector('[data-arrow-id="'+p.id+'"]')).map(p=>p.id)
     )));
     return piece?.id??null;
    });
    assert.ok(choice,'at least one legal arrow');
    const before=await page.evaluate(()=>window.ArrowMazeDebug.getState().remaining);
    const selector='[data-arrow-id="'+choice+'"]';
    await page.locator(selector).focus();
    assert.equal(await page.locator(selector).getAttribute('tabindex'),'0');
    await page.keyboard.press(key==='Space'?'Space':key);
    await page.waitForTimeout(550);
    const after=await page.evaluate(()=>window.ArrowMazeDebug.getState().remaining);
    assert.equal(after,before-1,device.name+' '+key+' must remove one legal arrow');
   }
   assert.deepEqual(errors,[],device.name+' no JavaScript errors');
   console.log(device.name+' keyboard Enter/Space legal arrows PASS');
   await context.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
