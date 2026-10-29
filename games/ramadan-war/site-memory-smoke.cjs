// Browser regression: blocked storage must never silently discard an active campaign.
// Local CI preview only. No production, wallet or payments.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader']});
 try{
  for(const v of [{name:'desktop',width:1200,height:800,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
   const context=await browser.newContext({viewport:{width:v.width,height:v.height},isMobile:v.mobile,hasTouch:v.mobile,acceptDownloads:true});
   try{
    await context.addInitScript(()=>{Storage.prototype.setItem=function(){throw new DOMException('Storage unavailable','QuotaExceededError')}});
    const page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    // Playwright dialog callbacks are async: a pending dismiss can reject after
    // the context closes, causing an unhandled rejection and a false CI failure.
    // Handle the rejection explicitly without masking errors on a live page.
    page.on('dialog',dialog=>{void dialog.dismiss().catch(error=>{
     if(!page.isClosed())errors.push('dialog dismiss failed: '+error.message);
    })});
    const response=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});
    assert.equal(response.status(),200);
    await page.waitForFunction(()=>window.RamadanWarDebug?.getState);
    await page.locator('#start').click();
    assert.equal((await page.evaluate(()=>window.RamadanWarDebug.getState())).mode,'game');
    await page.locator('#pause').click();
    assert((await page.locator('#pauseSaveStatus').innerText()).includes('انجام نشد'));
    await page.locator('#goHome').click();
    assert.equal(await page.locator('#start').innerText(),'ادامهٔ نبرد');
    await page.locator('#start').click();
    assert.equal((await page.evaluate(()=>window.RamadanWarDebug.getState())).mode,'game');
    await page.locator('#pause').click();await page.locator('#goHome').click();
    await page.locator('#newGame').click();
    assert(await page.locator('#home').isVisible());
    assert.equal(await page.locator('#start').innerText(),'ادامهٔ نبرد');
    const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#exportSave').click()]);
    assert.equal(download.suggestedFilename(),'ramadan-war-campaign-backup.json');
    await page.locator('#importSaveFile').setInputFiles(await download.path());
    assert.equal(await page.locator('#start').innerText(),'ادامهٔ نبرد');
    assert.deepEqual(errors,[]);
    console.log('RAMADAN_MEMORY_'+v.name.toUpperCase()+'=PASS');
   }finally{await context.close()}
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
