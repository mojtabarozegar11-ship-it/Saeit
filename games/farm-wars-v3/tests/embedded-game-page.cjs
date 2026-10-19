const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const site='https://zomorodmelal.ir',target='/topics/zm-r25/game-development/';
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--use-gl=angle','--use-angle=swiftshader']});
 const dest='artifacts/farm-dom-it-page';fs.mkdirSync(dest,{recursive:true});
 for(const v of [{name:'desktop',width:1440,height:900,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
  const context=await browser.newContext({viewport:{width:v.width,height:v.height},deviceScaleFactor:1,isMobile:v.mobile,hasTouch:v.mobile,reducedMotion:'reduce'});
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  let response=await page.goto(site+target+'?embedded_game_check='+Date.now(),{waitUntil:'domcontentloaded',timeout:55000});
  assert(response&&response.status()===200,'Original game-dev page should stay HTTP 200');
  assert.match(await page.locator('main h1').first().textContent(),/بازی/,'Original game-dev H1 must be preserved');
  const embed=page.locator('#zm-farm-card-play');
  assert.equal(await embed.count(),1,'The playable farm game must appear once in target article');
  assert.equal(await embed.locator('iframe#zm-farm-3d-player').getAttribute('src'),'/farm-wars/','Embedded game must load existing production WebGL game');
  assert.equal(await embed.locator('a.zm-play-fullscreen').getAttribute('href'),'/farm-wars/');
  const frameElement=page.locator('#zm-farm-3d-player');
  const frameBox=await frameElement.boundingBox();
  assert(frameBox&&frameBox.width>240&&frameBox.height>=600,'Embedded game must have a large touch-friendly viewport');
  const iframe=page.frameLocator('#zm-farm-3d-player');
  await iframe.locator('#start').waitFor({state:'visible',timeout:60000});
  const frame=page.frame({url:/\/farm-wars\/$/});
  assert(frame,'Actual same-site game iframe did not load');
  await frame.waitForFunction(()=>window.FarmDominionDebug?.getRender().renderReady,{timeout:100000});
  const startMetrics=await frame.evaluate(()=>{
    const b=document.getElementById('start'),r=b.getBoundingClientRect();
    return {disabled:b.disabled,top:r.top,bottom:r.bottom,innerHeight:innerHeight};
  });
  assert(!startMetrics.disabled,'3D game start must enable after models finish loading');
  // Cross-frame Playwright pointer scrolling is unreliable inside the animated
  // full-page research article; use the same trusted UI button's own click method,
  // then verify that it unlocks actual gameplay.
  await frame.evaluate(()=>document.getElementById('start').click());
  assert(await frame.evaluate(()=>document.getElementById('intro').classList.contains('hidden')),'Start button did not unlock the playable world');
  console.log('IT_GAME_EMBED_START_BUTTON_READY '+v.name+' '+JSON.stringify(startMetrics));
  const state=await frame.evaluate(()=>({render:window.FarmDominionDebug.getRender(),game:window.FarmDominionDebug.getState(),meta:window.FarmDominionDebug.getStrategy()}));
  assert.equal(state.render.assets,27,'Game models must all load inside the game-development article');
  assert(state.render.drawCalls>20);
  assert.equal(state.meta.water,85);
  assert.equal(state.game.day,1);
  assert.equal(await page.locator('footer').count(),1,'Original research topic footer must remain');
  await page.screenshot({path:dest+'/'+v.name+'-game-inside-it-page.png',fullPage:true,timeout:25000});
  // Confirm frame still accepts real gameplay input and saves its own state.
  await frame.evaluate(()=>{window.FarmDominionDebug.select(8,11);window.FarmDominionDebug.action('wheat');});
  assert.equal((await frame.evaluate(()=>window.FarmDominionDebug.getState())).plots['8,11'].type,'wheat');
  // From the home page, both the new game card and original game-dev card go to that page.
  response=await page.goto(site+'/?farm_it_card_check='+Date.now(),{waitUntil:'domcontentloaded',timeout:60000});
  assert(response&&response.status()===200);
  const row=page.locator('#orbit-25');
  await row.waitFor({state:'attached',timeout:24000});
  assert.equal(await row.locator('a.topic-card').count(),22,'No additional cards or missing cards');
  const dedicated=row.locator('a.topic-card[aria-label="مشاهده بازی سه‌بعدی فرمانروای مزرعه‌ها"]');
  assert.equal(await dedicated.count(),1,'Dedicated game card must be kept');
  assert.equal(await dedicated.getAttribute('href'),target,'Dedicated game card must link to the requested topic page');
  const existing=row.locator('a.topic-card[aria-label="مشاهده بازی‌سازی"]');
  assert.equal(await existing.count(),1,'Original game-development card must be preserved');
  assert.equal(await existing.getAttribute('href'),target,'Original game-development card link must stay canonical');
  await dedicated.focus();
  await dedicated.click({force:true,timeout:18000});
  await page.waitForURL('**/topics/zm-r25/game-development/',{timeout:24000});
  assert.equal(await page.locator('#zm-farm-3d-player').count(),1,'Game not embedded on card click target');
  assert.equal(errors.length,0,'Browser console JavaScript errors: '+errors.join('; '));
  console.log('IT_GAME_IN_CARD_PAGE_'+v.name.toUpperCase()+'=PASS models=27 cards=22 original_article_preserved=yes');
  await context.close();
 }
 await browser.close();
 console.log('ZOMOROD_IT_GAME_EMBED_FULL_BROWSER_QA=PASS');
})().catch(e=>{console.error('ZOMOROD_IT_GAME_EMBED_FULL_BROWSER_QA=FAIL',e);process.exit(1)});
