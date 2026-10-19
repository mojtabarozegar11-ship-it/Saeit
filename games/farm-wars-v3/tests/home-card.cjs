const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--use-gl=angle','--use-angle=swiftshader']});
 for(const w of [{name:'desktop',width:1440,height:900,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
  const context=await browser.newContext({viewport:{width:w.width,height:w.height},isMobile:w.mobile,hasTouch:w.mobile});
  const page=await context.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  let r=await page.goto('https://zomorodmelal.ir/?farmv4_card_qa='+Date.now(),{waitUntil:'domcontentloaded',timeout:55000});
  assert.equal(r.status(),200);
  await page.locator('#orbit-25').waitFor({state:'attached',timeout:18000});
  const target=page.locator('#orbit-25 .topic-card[href="/farm-wars/"]');
  assert.equal(await target.count(),1,'One and only one farm game card must be in IT row');
  assert.match(await target.textContent(),/بازی سه‌بعدی فرمانروای مزرعه‌ها/);
  assert.equal(await page.locator('#orbit-25 .topic-card').count(),22,'Existing 21 IT cards must remain and game adds exactly one');
  assert.equal(await page.locator('#orbit-25 .topic-card[href="/topics/zm-r25/game-development/"]').count(),1,'Existing game development card must be kept');
  await target.scrollIntoViewIfNeeded({timeout:15000});
  const img=target.locator('img');
  await page.waitForFunction(()=>{
   const im=document.querySelector('#orbit-25 .topic-card[href="/farm-wars/"] img');
   return im?.complete&&im.naturalWidth>=500;
  },{timeout:16000});
  assert.equal(await img.getAttribute('src'),'/farm-wars/cover.webp');
  await target.click({timeout:15000});
  await page.waitForURL('**/farm-wars/**',{timeout:30000});
  await page.waitForFunction(()=>window.FarmDominionDebug?.getRender().renderReady,{timeout:35000});
  const game=await page.evaluate(()=>window.FarmDominionDebug.getRender());
  assert.equal(game.assets,27,'Real 3D assets must load after clicking IT card');
  assert(game.drawCalls>25);
  assert.equal(errors.length,0,'No JS errors on homepage or game: '+errors.join(';'));
  console.log('FARM_GAME_IT_ROW_NAVIGATION_'+w.name.toUpperCase()+'=PASS cards=22 models=27');
  await context.close();
 }
 await browser.close();
 console.log('FARM_GAME_HOMEPAGE_CARD_BROWSER_QA=PASS');
})().catch(e=>{console.error(e);process.exit(1)});
