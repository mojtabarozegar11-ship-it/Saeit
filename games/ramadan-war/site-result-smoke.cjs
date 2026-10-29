// Browser proof: a cleared mission must not claim a successful save when storage fails.
// QA-only instrumentation is injected into localhost's response, never shipped to players.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const source=fs.readFileSync(path.join(__dirname,'game.js'),'utf8');
 const marker='window.RamadanWarDebug=Object.freeze(debugApi);';
 assert.equal(source.split(marker).length,2,'test-only hook anchor changed');
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader']});
 try{
  for(const device of [{name:'desktop',width:1200,height:800,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
   for(const blocked of [false,true]){
    const context=await browser.newContext({viewport:{width:device.width,height:device.height},isMobile:device.mobile,hasTouch:device.mobile,acceptDownloads:true});
    try{
     if(blocked)await context.addInitScript(()=>{Storage.prototype.setItem=function(){throw new DOMException('Storage unavailable','QuotaExceededError')}});
     const page=await context.newPage(),errors=[];
     page.on('pageerror',e=>errors.push(e.message));
     await page.route('**/game.js',route=>route.fulfill({status:200,contentType:'text/javascript',body:source.replace(marker,'window.__qaCompleteMission=()=>{world.missionKills=4;world.kills=4;world.objective.done=2;world.enemies=[];world.missionPassed=true};window.__qaShowResult=showResult;'+marker)}));
     const response=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});
     assert.equal(response.status(),200);
     await page.waitForFunction(()=>typeof window.__qaShowResult==='function');
     await page.locator('#newGame').click();
     await page.evaluate(()=>{window.__qaCompleteMission();window.__qaShowResult('منطقه پاکسازی شد','پیشرفت ذخیره شد','success')});
     assert.equal(await page.locator('#resultExport').isVisible(),true,'completed campaign must offer a portable backup');
     const status=await page.locator('#resultSaveStatus').innerText();
     const detail=await page.locator('#resultText').innerText();
     if(blocked){assert(status.includes('هشدار'),status);assert(detail.includes('تأیید نشد'),detail)}
     else{assert(status.includes('تأیید شد'),status);assert(!detail.includes('تأیید نشد'),detail)}
     const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#resultExport').click()]);
     assert.equal(download.suggestedFilename(),'ramadan-war-campaign-backup.json');
     const backup=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
     assert.equal(backup.format,'ramadan-war-campaign-v1');
     assert.equal(backup.campaign.missionPassed,true);
     await page.evaluate(()=>window.__qaShowResult('پایان','بازی تمام شد','over'));
     assert.equal(await page.locator('#resultExport').isVisible(),false,'defeat must not offer a stale completed-stage export');
     assert.deepEqual(errors,[],'no uncaught browser exceptions');
     console.log('RAMADAN_RESULT_'+device.name.toUpperCase()+'_'+(blocked?'STORAGE_BLOCKED':'STORAGE_OK')+'=PASS');
    }finally{await context.close()}
   }
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
