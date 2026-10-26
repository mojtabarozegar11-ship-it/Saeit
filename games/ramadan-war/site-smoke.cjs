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
   await page.waitForFunction(()=>{const s=window.RamadanWarDebug.getState();return s&&s.soldierModel&&s.weaponModel},null,{timeout:20000}).catch(e=>{throw new Error('3D model assets did not load\n'+errors.join('\n')+'\n'+e.message)});
   assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('playing')),true);
   await page.waitForFunction(()=>document.querySelector('#missionBackdrop').dataset.scene==='./scene-sniper-desert-v2.webp');
   assert.match(await page.locator('#missionBackdrop').evaluate(el=>getComputedStyle(el).backgroundImage),/scene-sniper-desert-v2\.webp/);
   assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('three-world-ready')),true);
   assert.equal(await page.locator('#missionBackdrop').evaluate(el=>getComputedStyle(el).display),'block');assert.equal(await page.locator('#fullscreen').count(),1);
   assert.equal(await page.locator('#weaponArt').evaluate(el=>getComputedStyle(el).display),'none');
   await page.evaluate(()=>{for(let i=0;i<30;i++)window.RamadanWarDebug.tick(.04)});
   const controls=await page.evaluate(()=>({stick:document.querySelector('#stick').getBoundingClientRect().x,fire:document.querySelector('#fire').getBoundingClientRect().x}));assert(controls.stick<controls.fire,'movement pad should be on the left of fire controls');
   await page.locator('#scope').click();assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('scope-mode')),true);
   assert.equal(await page.locator('#view').evaluate(el=>el.getContext('webgl2')||el.getContext('webgl')?true:false),true);
   await page.locator('#scope').click();assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('scope-mode')),false);
   await page.waitForFunction(()=>document.querySelector('#view').getContext('webgl2')||document.querySelector('#view').getContext('webgl'),null,{timeout:10000});
   let state=await page.evaluate(()=>window.RamadanWarDebug.getState());
   assert.equal(state.hp,100);assert.equal(state.lives,100);assert.equal(state.stage,0);assert.equal(state.mode,'game');
   assert.equal(state.rockets,12);assert.equal(state.drones,3);assert.equal(state.ammo,8);
   await page.keyboard.down('Space');await page.evaluate(()=>window.dispatchEvent(new Event('blur')));
   await page.locator('#pausePanel:not(.hidden)').waitFor();assert.equal(await page.evaluate(()=>window.RamadanWarDebug.getState().mode),'pausePanel');
   const shotsAtPause=await page.evaluate(()=>window.RamadanWarDebug.getState().shots);
   await page.locator('#resume').click();await page.evaluate(()=>{for(let i=0;i<15;i++)window.RamadanWarDebug.tick(.04)});
   assert.equal(await page.evaluate(()=>window.RamadanWarDebug.getState().shots),shotsAtPause,'lost focus must release held fire');await page.keyboard.up('Space');
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));delete document.hidden});
   await page.locator('#pausePanel:not(.hidden)').waitFor();assert.equal(await page.evaluate(()=>window.RamadanWarDebug.getState().mode),'pausePanel');await page.locator('#resume').click();assert.equal(state.renderer,'webgl-threejs');assert(state.enemies>0,'mission enemy spawn '+JSON.stringify(state));
   await page.evaluate(()=>window.RamadanWarDebug.spawnTestEnemy());
   await page.evaluate(()=>{window.RamadanWarDebug.fire();window.RamadanWarDebug.rocket();window.RamadanWarDebug.drone()});
   await page.evaluate(()=>{window.RamadanWarDebug.spawnTestPickup('ammo');window.RamadanWarDebug.tick(.04)});state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.shots,1);assert.equal(state.rockets,11);assert.equal(state.drones,2);assert.equal(state.ammo,8,'ammo pickup restores the magazine');
   await page.locator('#pause').click();await page.locator('#pausePanel:not(.hidden)').waitFor();await page.reload({waitUntil:'domcontentloaded'});
   assert.match(await page.locator('#start').innerText(),/ادامه/);
   await page.locator('#start').click();
   state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.stage,0);assert.equal(state.rockets,11);assert.equal(state.drones,2);assert.equal(state.mode,'game');

   // Exercise the actual objective interactions on the local release candidate.
   if(['127.0.0.1','localhost'].includes(new URL(process.env.GAME_URL).hostname)){
    const checked=await page.evaluate(()=>{
      const g=window.RamadanWarDebug;g.start();const a=[];
      a.push(g.getState().objectiveKind==='activate' && g.interact()===false);
      a.push(g.qaMove(8.5,3.5) && g.interact());
      a.push(g.qaMove(11.5,11.5) && g.interact());
      a.push(g.getState().objective.done===2);
      a.push(g.qaMission(2));a.push(g.getState().objectiveKind==='recover');
      for(const [x,y] of [[4.5,2.5],[12.5,4.5],[8.5,12.5]]){a.push(g.qaMove(x,y));g.tick(.04)}
      a.push(g.getState().objective.done===3);
      a.push(g.qaMission(1));a.push(g.qaMove(8.5,7.5));for(let i=0;i<30;i++)g.tick(.04);
      a.push(g.getState().objective.hold>0.5);
      a.push(g.qaMission(4));a.push(g.getState().objectiveKind==='extract');
      a.push(g.qaMission(5));for(let i=0;i<24;i++)g.tick(.04);
      a.push(g.getState().objectiveKind==='boss');
      return a;
    });
    assert(checked.every(Boolean),'campaign objective interaction regression '+JSON.stringify(checked));
    assert.equal(await page.locator('#missionObjective').isVisible(),true);
    console.log('CAMPAIGN_OBJECTIVES_PASS activation=2 intel=3 defend=timer extract=check boss=spawn');
   }
   assert.equal(errors.length,0,errors.join('\n'));
   await context.close();console.log('RAMADAN_WEB_'+v.name.toUpperCase()+'_PASS native_campaign=6 heroes=30 lives=100 weapons=rocket+drone save=resume pickups=collectible-ammo');
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
