const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const launch={headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']};if(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH)launch.executablePath=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;const browser=await chromium.launch(launch);
 try{
  for(const v of [{name:'desktop',width:1365,height:900,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
   const context=await browser.newContext({viewport:{width:v.width,height:v.height},isMobile:v.mobile,hasTouch:v.mobile});
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push('page: '+e.message));page.on('console',m=>{if(m.type()==='error')errors.push('console: '+m.text())});page.on('requestfailed',r=>errors.push('request: '+r.url()+' '+(r.failure()?.errorText||'')));
   const response=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});assert.equal(response.status(),200);
   await page.locator('#home h1').waitFor();
   await page.waitForFunction(()=>window.RamadanWarDebug&&Array.isArray(window.RamadanWarDebug.heroes),null,{timeout:10000}).catch(e=>{throw new Error(e.message+'\n'+errors.join('\n'))});
   assert.equal(await page.evaluate(()=>window.RamadanWarDebug.heroes.length),30);
   assert.equal(await page.evaluate(()=>window.RamadanWarDebug.skills.length),6);
   await page.evaluate(()=>window.RamadanWarDebug.selectHero(1));
   assert.equal(await page.locator('#heroName').innerText(),'حاج قاسم — قاسم سلیمانی');
   await page.evaluate(()=>window.RamadanWarDebug.selectHero(0));
   await page.evaluate(()=>window.RamadanWarDebug.start());
   await page.locator('#hud:not(.hidden)').waitFor();
   await page.waitForFunction(()=>document.querySelector('#weaponArt').complete&&document.querySelector('#weaponArt').naturalWidth>0);
   assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('playing')),true);
   await page.waitForFunction(()=>document.querySelector('#missionBackdrop').dataset.scene==='./scene-desert.webp');
   assert.match(await page.locator('#missionBackdrop').evaluate(el=>getComputedStyle(el).backgroundImage),/scene-desert\.webp/);
   await page.evaluate(()=>{for(let i=0;i<30;i++)window.RamadanWarDebug.tick(.04)});
   const controls=await page.evaluate(()=>({stick:document.querySelector('#stick').getBoundingClientRect().x,fire:document.querySelector('#fire').getBoundingClientRect().x}));assert(controls.stick<controls.fire,'movement pad should be on the left of fire controls');
   await page.locator('#scope').click();assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('scope-mode')),true);
   assert.equal(await page.locator('#missionBackdrop').evaluate(el=>getComputedStyle(el).backgroundSize),'auto 267%');
   await page.locator('#scope').click();assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('scope-mode')),false);
   await page.waitForFunction(()=>document.querySelector('#view').getContext('webgl2')||document.querySelector('#view').getContext('webgl'),null,{timeout:10000});
   let state=await page.evaluate(()=>window.RamadanWarDebug.getState());
   assert.equal(state.hp,100);assert.equal(state.lives,100);assert.equal(state.stage,0);assert.equal(state.mode,'game');
   assert.equal(state.rockets,12);assert.equal(state.drones,3);assert.equal(state.renderer,'webgl-threejs');assert(state.enemies>0,'mission enemy spawn '+JSON.stringify(state));
   await page.evaluate(()=>window.RamadanWarDebug.spawnTestEnemy());
   await page.evaluate(()=>{window.RamadanWarDebug.fire();window.RamadanWarDebug.rocket();window.RamadanWarDebug.drone()});
   state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.shots,1);assert.equal(state.rockets,11);assert.equal(state.drones,2);
   await page.reload({waitUntil:'domcontentloaded'});
   assert.match(await page.locator('#start').innerText(),/ادامه/);
   await page.locator('#start').click();
   state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.stage,0);assert.equal(state.rockets,11);assert.equal(state.drones,2);assert.equal(state.mode,'game');
   assert.equal(errors.length,0,errors.join('\n'));
   await context.close();console.log('RAMADAN_WEB_'+v.name.toUpperCase()+'_PASS native_campaign=6 heroes=30 lives=100 weapons=rocket+drone save=resume');
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
