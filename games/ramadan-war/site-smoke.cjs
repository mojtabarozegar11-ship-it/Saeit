const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try {
  for(const v of [{name:'desktop',width:1365,height:900,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
   const context=await browser.newContext({viewport:{width:v.width,height:v.height},isMobile:v.mobile,hasTouch:v.mobile});
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   const response=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});assert.equal(response.status(),200);
   await page.locator('#menu h1').waitFor();
   assert.equal(await page.evaluate(()=>window.RamadanWarDebug.heroes.length),30);
   assert.match(await page.locator('#menu').innerText(),/۳۰/);
   await page.evaluate(()=>window.RamadanWarDebug.selectHero(1));
   assert.equal(await page.locator('#heroName').innerText(),'حاج قاسم سلیمانی');
   await page.evaluate(()=>window.RamadanWarDebug.selectHero(0));
   await page.evaluate(()=>window.RamadanWarDebug.start());
   await page.locator('#hud:not(.hidden)').waitFor();
   let state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.hp,100);assert.equal(state.stage,0);assert.equal(state.mode,'play');
   await page.evaluate(()=>{window.RamadanWarDebug.fire();window.RamadanWarDebug.rocket();window.RamadanWarDebug.drone()});
   state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.shots,1);assert(state.rockets<3);assert.equal(state.drones,0);
   await page.reload({waitUntil:'domcontentloaded'});
   assert.match(await page.locator('#start').innerText(),/ادامه/);
   await page.locator('#start').click();
   state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.stage,0);assert(state.rockets<3);assert.equal(state.drones,0);assert.equal(state.mode,'play');
   assert.equal(errors.length,0,errors.join('\n'));
   await context.close();console.log('RAMADAN_WEB_'+v.name.toUpperCase()+'_PASS heroes=30 controls=fire+rocket+drone');
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
