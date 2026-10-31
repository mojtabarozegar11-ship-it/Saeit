// G-01 R57 real-browser GPU eviction UI safety. Synthetic DOM event, not actual driver reset.
// No production URL, wallet, payment or server writes.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader']});
 try{
  for(const variant of [{name:'desktop',width:1280,height:800,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
   for(const storageBlocked of [false,true]){
    const context=await browser.newContext({viewport:{width:variant.width,height:variant.height},isMobile:variant.mobile,hasTouch:variant.mobile});
    try{
     const page=await context.newPage(),errors=[];
     page.on('pageerror',e=>errors.push(e.message));
     if(storageBlocked)await page.addInitScript(()=>{Storage.prototype.setItem=function(){throw new Error('blocked-for-r57-qa')}});
     const response=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});
     assert.equal(response.status(),200);
     await page.waitForFunction(()=>window.RamadanWarDebug?.start);
     await page.evaluate(()=>window.RamadanWarDebug.start());
     await page.waitForFunction(()=>document.querySelector('#game').classList.contains('playing'));
     const prevented=await page.evaluate(()=>{
      const event=new Event('webglcontextlost',{bubbles:false,cancelable:true});
      document.querySelector('#view').dispatchEvent(event);
      return event.defaultPrevented;
     });
     assert.equal(prevented,true,'context-loss handler must prevent browser default');
     assert(await page.locator('#pausePanel').isVisible(),'graphics failure must pause the battle');
     assert(await page.locator('#resume').isDisabled(),'resume must be blocked after GPU eviction');
     assert(await page.locator('#reloadGraphics').isVisible(),'explicit recovery control must be offered');
     assert.equal(await page.locator('#reloadGraphics').isEnabled(),!storageBlocked,'reload must require verified durable save');
     await page.evaluate(()=>document.querySelector('#view').dispatchEvent(new Event('webglcontextrestored')));
     assert(await page.locator('#resume').isDisabled(),'context restoration must not silently resume');
     assert(await page.locator('#pausePanel').isVisible());
     assert.deepEqual(errors,[]);
     console.log('R57_GPU_RECOVERY',variant.name,storageBlocked?'storage-denied':'storage-ok','PASS');
    }finally{await context.close()}
   }
  }
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
