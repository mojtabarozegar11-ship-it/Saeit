// Player-facing regression for mobile reload, pause backup, survival waves and boss status.
// Runs only against a local preview in CI. Never opens payment or production URLs.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader']});
 try{
  for(const c of [{name:'desktop',width:1200,height:800,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
   const context=await browser.newContext({viewport:{width:c.width,height:c.height},isMobile:c.mobile,hasTouch:c.mobile,acceptDownloads:true});
   try{
    const page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const response=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});
    assert.equal(response.status(),200);
    await page.waitForFunction(()=>window.RamadanWarDebug?.start);
    await page.evaluate(()=>window.RamadanWarDebug.start());
    assert(await page.locator('#reload').isDisabled(),'full magazine must not permit reload');
    await page.evaluate(()=>window.RamadanWarDebug.fire());
    assert.equal(await page.locator('#reload').isDisabled(),false,'partial magazine should permit touch reload');
    await page.locator('#reload').click();
    assert(await page.locator('#reload').isDisabled(),'reload cannot be stacked during animation');
    await page.waitForTimeout(1800);
    const reloadState=await page.evaluate(()=>({ammo:window.RamadanWarDebug.getState()?.ammo,label:document.querySelector('#ammoText').textContent,mode:window.RamadanWarDebug.getState()?.mode}));
    console.log('RAMADAN_RELOAD_DIAGNOSTIC',c.name,reloadState);
    assert.equal(reloadState.ammo,8,'manual reload must restore full magazine');
    assert.equal(reloadState.label,'۸ / ۸','HUD must refresh on reload completion');
    await page.locator('#pause').click();
    const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#exportPauseSave').click()]);
    const backup=JSON.parse((await fs.readFile(await download.path())).toString('utf8'));
    assert.equal(backup.format,'ramadan-war-campaign-v1');
    assert.equal(backup.version,1);
    await page.locator('#resume').click();
    assert(await page.locator('#reload').isDisabled());
    assert(await page.evaluate(()=>window.RamadanWarDebug.qaMission(5)));
    await page.evaluate(()=>{for(let i=0;i<48;i++)window.RamadanWarDebug.tick(.04)});
    await page.waitForFunction(()=>document.querySelector('#objectiveDetail').textContent.includes('زره فرمانده'),null,{timeout:5000});
    await page.locator('#pause').click();
    await page.locator('#goHome').click();
    await page.evaluate(()=>{localStorage.setItem('rwWin','1');localStorage.setItem('rwSurvivalBest','8')});
    await page.reload({waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>window.RamadanWarDebug?.start);
    assert(await page.locator('#survival').isVisible(),'unlocked survival must be available immediately on reload');
    assert((await page.locator('#survivalRecord').innerText()).includes('۸'));
    await page.locator('#survival').click();
    assert.equal(await page.locator('#stageText').innerText(),'۱','first survival wave should not display as mission 7');
    assert((await page.locator('#missionName').innerText()).includes('موج ۱'));
    assert.equal(await page.evaluate(()=>localStorage.getItem('rwSurvivalBest')),'8');
    await page.emulateMedia({reducedMotion:'reduce'});
    assert.equal(await page.locator('#objectiveArrow').evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
    assert.deepEqual(errors,[]);
    console.log('RAMADAN_CONTROLS_'+c.name.toUpperCase()+'=PASS');
   }finally{await context.close()}
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
