// G-01 R15: real Chromium recovery of in-memory campaign from corrupted browser storage.
// Offline CI only. No wallet, login, payment, public deployment or game reward mutation.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader']});
 try{
  for(const v of [{name:'desktop',width:1200,height:800,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
   const context=await browser.newContext({viewport:{width:v.width,height:v.height},isMobile:v.mobile,hasTouch:v.mobile,acceptDownloads:true});
   try{
    const page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const response=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});
    assert.equal(response.status(),200);
    await page.waitForFunction(()=>window.RamadanWarDebug?.getState);
    await page.locator('#newGame').click();
    await page.waitForFunction(()=>window.RamadanWarDebug.getState()?.mode==='game');
    const before=await page.evaluate(()=>window.RamadanWarDebug.getState());
    await page.locator('#pause').click();
    await page.locator('#goHome').click();
    await page.evaluate(()=>localStorage.setItem('rwNativeCampaign','{broken'));
    await page.locator('#start').click();
    await page.waitForFunction(()=>window.RamadanWarDebug.getState()?.mode==='game');
    const after=await page.evaluate(()=>window.RamadanWarDebug.getState());
    assert.equal(after.stage,before.stage,'campaign stage preserved');
    assert.equal(after.lives,before.lives,'lives preserved');
    assert.equal(after.hero,before.hero,'hero preserved');
    await page.locator('#pause').click();
    const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#exportPauseSave').click()]);
    assert.equal(download.suggestedFilename(),'ramadan-war-campaign-backup.json');
    assert.deepEqual(errors,[]);
    console.log('RAMADAN_CORRUPT_DISK_MEMORY_'+v.name.toUpperCase()+'=PASS');
    await page.close();
    const clean=await context.newPage();
    await clean.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});
    await clean.waitForFunction(()=>window.RamadanWarDebug?.getState);
    await clean.evaluate(()=>localStorage.setItem('rwNativeCampaign','{broken'));
    await clean.locator('#start').click();
    assert(await clean.locator('#home').isVisible(),'invalid disk save must not start a fresh campaign');
    await clean.close();
   }finally{await context.close()}
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
