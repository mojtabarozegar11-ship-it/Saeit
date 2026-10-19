const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const url = process.env.TEST_URL || 'http://127.0.0.1:8080/';
(async () => {
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--disable-dev-shm-usage']});
 const dir='artifacts/farm-dominion-3d';fs.mkdirSync(dir,{recursive:true});
 const errors=[];
 for (const view of [{name:'desktop',width:1440,height:900,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
  const context=await browser.newContext({viewport:{width:view.width,height:view.height},deviceScaleFactor:1,isMobile:view.mobile,hasTouch:view.mobile});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(view.name+': '+e.message));
  const response=await page.goto(url+'?qa_'+view.name+'='+Date.now(),{waitUntil:'domcontentloaded',timeout:60000});
  assert.equal(response.status(),200,'Site must serve 3D game');
  await page.waitForFunction(()=>window.FarmDominionDebug&&window.FarmDominionDebug.getRender().renderReady,{timeout:110000});
  await page.locator('#start').click();
  await page.waitForTimeout(2600);
  const result=await page.evaluate(()=>{
    const test=window.FarmDominionDebug,can=document.getElementById('world');
    const gl=can.getContext('webgl2')||can.getContext('webgl');
    const a=test.getRender(),s=test.getState();
    return {ready:a.renderReady,modelCount:a.assets,drawCalls:a.drawCalls,sceneChildren:a.sceneChildren,canvas:[can.width,can.height],webgl:!!gl,state:s,viewport:innerWidth,bodyScroll:document.documentElement.scrollWidth,htmlBackdrop:document.getElementById('intro').classList.contains('hidden')};
  });
  assert(result.ready,'3D game not ready');
  assert(result.htmlBackdrop,'Entry overlay did not close');
  assert(result.webgl,'WebGL renderer not available');
  assert(result.canvas[0]>150&&result.canvas[1]>300,'3D canvas not sized');
  assert(result.sceneChildren>=10,'3D world missing');
  assert(result.drawCalls>25,'Game appears to have missing rendered objects');
  assert(result.modelCount>=22,'3D art assets missing: '+result.modelCount);
  assert(result.viewport+3>=result.bodyScroll,'Horizontal overflow on '+view.name);
  await page.screenshot({path:dir+'/'+view.name+'-real-3d.png',fullPage:true});
  // Check planting and harvesting mutate authoritative saved game state.
  await page.evaluate(()=>{
    window.FarmDominionDebug.select(8,11);
    window.FarmDominionDebug.action('wheat');
  });
  const planted=await page.evaluate(()=>window.FarmDominionDebug.getState());
  assert.equal(planted.plots['8,11'].type,'wheat','Wheat did not appear');
  assert.equal(planted.gold,result.state.gold-16,'Wheat purchase cost incorrect');
  await page.evaluate(()=>{
    window.FarmDominionDebug.select(6,9);
    window.FarmDominionDebug.action('harvest');
  });
  const harvested=await page.evaluate(()=>window.FarmDominionDebug.getState());
  assert(harvested.food>planted.food,'Harvest did not produce food');
  await page.screenshot({path:dir+'/'+view.name+'-after-farming.png',fullPage:true});
  const oldEnemy=harvested.enemies[0];
  await page.evaluate(()=>{
    window.FarmDominionDebug.select(15,2);
    window.FarmDominionDebug.action('attack');
  });
  await page.waitForTimeout(1000);
  assert((await page.evaluate(()=>window.FarmDominionDebug.getState())).enemies[0]<oldEnemy,'War attack did not damage enemy castle');
  await page.screenshot({path:dir+'/'+view.name+'-active-battle.png',fullPage:true});
  console.log(view.name.toUpperCase()+'_REAL_3D_QA=PASS modelCount='+result.modelCount+' drawCalls='+result.drawCalls+' resolution='+result.canvas.join('x')+' oldEnemy='+oldEnemy);
  await context.close();
 }
 await browser.close();
 if(errors.length)throw Error('Browser JS errors: '+errors.join(' / '));
 console.log('FARM_DOMINION_WEBGL_GAMEPLAY_QA=PASS');
})().catch(e=>{console.error('FARM_DOMINION_WEBGL_GAMEPLAY_QA=FAIL',e);process.exit(1);});