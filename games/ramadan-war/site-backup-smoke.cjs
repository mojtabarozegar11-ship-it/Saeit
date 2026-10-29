// End-to-end campaign backup regression in real desktop/mobile Chromium.
// Local HTTP only. No wallet, external site, or production write.
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const assert=require('node:assert/strict');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader']});
 try{
  for(const config of [{name:'desktop',width:1200,height:800,mobile:false},
                       {name:'mobile',width:390,height:844,mobile:true}]){
   const context=await browser.newContext({viewport:{width:config.width,height:config.height},
     isMobile:config.mobile,hasTouch:config.mobile,acceptDownloads:true});
   try{
    const page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const response=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});
    assert.equal(response.status(),200);
    await page.waitForFunction(()=>window.RamadanWarDebug?.start,null,{timeout:20000});
    assert(await page.locator('#exportSave').isVisible());
    assert(await page.locator('#importSave').isVisible());
    assert.equal(await page.locator('#soundHome').getAttribute('aria-pressed'),'true');
    await page.locator('#soundHome').click();
    assert.equal(await page.locator('#soundHome').getAttribute('aria-pressed'),'false');
    await page.reload({waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>window.RamadanWarDebug?.start);
    assert.equal(await page.locator('#soundHome').getAttribute('aria-pressed'),'false',
      'muted setting persists across browser reload');
    await page.locator('#soundHome').click();
    assert.equal(await page.locator('#soundHome').getAttribute('aria-pressed'),'true');
    await page.evaluate(()=>window.RamadanWarDebug.start());
    await page.locator('#pause').click();
    assert.equal(await page.locator('#soundPause').getAttribute('aria-pressed'),'true');
    await page.locator('#soundPause').click();
    assert.equal(await page.locator('#soundPause').getAttribute('aria-pressed'),'false');
    await page.locator('#soundPause').click();
    await page.locator('#goHome').click();
    const before=await page.evaluate(()=>localStorage.getItem('rwNativeCampaign'));
    assert(before&&JSON.parse(before).hero===0);
    const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#exportSave').click()]);
    const bytes=await fs.readFile(await download.path());
    const backup=JSON.parse(bytes.toString('utf8'));
    assert.equal(backup.format,'ramadan-war-campaign-v1');
    assert.equal(backup.version,1);
    page.once('dialog',dialog=>dialog.dismiss());
    await page.locator('#newGame').click();
    assert.equal(await page.evaluate(()=>localStorage.getItem('rwNativeCampaign')),before,
      'cancelling new game must preserve campaign');
    // A changed durable snapshot must not be overwritten by stale autosave.
    // The live in-memory campaign must remain playable and manually exportable.
    const stranded=JSON.parse(before);
    stranded.enemies=Array.from({length:7},()=>({x:3.5,y:3.5,type:0,hp:39,max:39,life:1.5}));
    const strandedRaw=JSON.stringify(stranded);
    await page.evaluate(raw=>localStorage.setItem('rwNativeCampaign',raw),strandedRaw);
    await page.locator('#start').click();
    await page.waitForFunction(()=>window.RamadanWarDebug.getState()?.mode==='game');
    await page.waitForTimeout(5200);
    const diskAfter=JSON.parse(await page.evaluate(()=>localStorage.getItem('rwNativeCampaign')));
    assert.deepEqual(diskAfter.enemies,stranded.enemies,'stale tab must not overwrite changed disk save');
    const live=await page.evaluate(()=>window.RamadanWarDebug.getState());
    assert(live.hp>0&&live.mode==='game','in-memory campaign remains playable');
    await page.locator('#pause').click();
    const [memoryDownload]=await Promise.all([page.waitForEvent('download'),page.locator('#exportPauseSave').click()]);
    const memoryBytes=await fs.readFile(await memoryDownload.path());
    const memoryBackup=JSON.parse(memoryBytes.toString('utf8'));
    assert.equal(memoryBackup.format,'ramadan-war-campaign-v1');
    assert.notDeepEqual(memoryBackup.campaign.enemies,stranded.enemies,'backup exports live memory, not stale disk');
    page.once('dialog',dialog=>dialog.accept());
    await page.reload({waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>window.RamadanWarDebug?.start);
    page.once('dialog',dialog=>dialog.accept());
    await page.locator('#importSaveFile').setInputFiles({name:'campaign.json',
      mimeType:'application/json',buffer:memoryBytes});
    await page.waitForFunction(()=>{try{return JSON.parse(localStorage.getItem('rwNativeCampaign')).hero===0}catch{return false}},null,{timeout:10000});
    assert.equal(await page.locator('#start').innerText(),'ادامهٔ نبرد');
    assert.deepEqual(errors,[]);
    console.log('RAMADAN_CAMPAIGN_BACKUP_'+config.name.toUpperCase()+'=PASS');
   }finally{await context.close()}
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
