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
   // Real pointer capture and animation frames: dragging up must advance,
   // dragging right must strafe, including on the mobile viewport.
   if (['127.0.0.1','localhost'].includes(new URL(process.env.GAME_URL).hostname)) {
     const stick = await page.locator('#stick').boundingBox();
     assert(stick && stick.width > 30, 'joystick must be rendered');
     const cx = stick.x + stick.width / 2, cy = stick.y + stick.height / 2;
     const drag = async (dx, dy) => {
       await page.mouse.move(cx, cy);
       await page.mouse.down();
       await page.mouse.move(cx + dx, cy + dy, {steps: 4});
       await page.waitForTimeout(260);
       await page.mouse.up();
       return page.evaluate(() => window.RamadanWarDebug.qaPosition());
     };
     const before = await page.evaluate(() => window.RamadanWarDebug.qaPosition());
     assert(before, 'local-only position inspection must be available');
     const afterUp = await drag(0, -stick.height * .3);
     assert(afterUp.x > before.x + .05, 'upward joystick drag must move forward');
     assert(Math.abs(afterUp.y - before.y) < .12, 'upward drag must not strafe');
     const afterRight = await drag(stick.width * .3, 0);
     assert(afterRight.y > afterUp.y + .05, 'rightward joystick drag must strafe right');
     assert(Math.abs(afterRight.x - afterUp.x) < .12, 'rightward drag must not advance');
     console.log('RAMADAN_REAL_JOYSTICK_PASS', v.name);
     // Exercise the real Chromium keyboard event path and engine ticks. The
     // diagonal distance must not exceed straight-line distance by sqrt(2).
     const speedCheck = await page.evaluate(() => {
       const g = window.RamadanWarDebug;
       const press = (code, kind) => window.dispatchEvent(new KeyboardEvent(kind, {code, bubbles:true}));
       const run = codes => {
         g.qaMove(2.5, 7.5);
         const origin = g.qaPosition();
         codes.forEach(code => press(code, 'keydown'));
         for(let i=0;i<3;i++)g.tick(.04);
         codes.forEach(code => press(code, 'keyup'));
         const end = g.qaPosition();
         return Math.hypot(end.x-origin.x, end.y-origin.y);
       };
       return {straight:run(['KeyW']), diagonal:run(['KeyW','KeyD'])};
     });
     assert(speedCheck.straight > .1, 'keyboard forward motion must work');
     assert(speedCheck.diagonal > .1, 'keyboard diagonal motion must work');
     assert(speedCheck.diagonal <= speedCheck.straight * 1.06,
       'W+D must not gain a diagonal speed advantage: '+JSON.stringify(speedCheck));
     console.log('RAMADAN_REAL_DIAGONAL_SPEED_PASS', v.name);

   }
   await page.locator('#scope').click();assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('scope-mode')),true);
   assert.equal(await page.locator('#view').evaluate(el=>el.getContext('webgl2')||el.getContext('webgl')?true:false),true);
   await page.locator('#scope').click();assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('scope-mode')),false);
   await page.waitForFunction(()=>document.querySelector('#view').getContext('webgl2')||document.querySelector('#view').getContext('webgl'),null,{timeout:10000});
   let state=await page.evaluate(()=>window.RamadanWarDebug.getState());
   assert.equal(state.hp,100);assert.equal(state.lives,100);assert.equal(state.stage,0);assert.equal(state.mode,'game');
   assert.equal(state.rockets,12);assert.equal(state.drones,3);assert.equal(state.ammo,8);assert.equal(state.renderer,'webgl-threejs');assert(state.enemies>0,'mission enemy spawn '+JSON.stringify(state));
   // Real Chromium event dispatch: browser shortcuts and composition must not
   // consume rockets/drones or suppress native key handling on either viewport.
   const shortcutCheck=await page.evaluate(()=>{
     const before=window.RamadanWarDebug.getState(),results=[];
     for(const opts of [
       {code:'KeyQ',ctrlKey:true},{code:'KeyE',altKey:true},
       {code:'KeyF',metaKey:true},{code:'KeyQ',isComposing:true}
     ]){
       const event=new KeyboardEvent('keydown',{bubbles:true,cancelable:true,...opts});
       results.push(document.dispatchEvent(event));
     }
     const after=window.RamadanWarDebug.getState();
     return {results,rocketsBefore:before.rockets,rocketsAfter:after.rockets,
       dronesBefore:before.drones,dronesAfter:after.drones,shotsBefore:before.shots,shotsAfter:after.shots};
   });
   assert(shortcutCheck.results.every(Boolean),'modified/composing shortcuts must not be preventDefault-ed');
   assert.equal(shortcutCheck.rocketsAfter,shortcutCheck.rocketsBefore,'Ctrl+Q or IME must not spend rockets');
   assert.equal(shortcutCheck.dronesAfter,shortcutCheck.dronesBefore,'Alt+E must not spend drones');
   assert.equal(shortcutCheck.shotsAfter,shortcutCheck.shotsBefore,'browser shortcuts must not fire weapons');
   console.log('RAMADAN_REAL_MODIFIER_IME_PASS',v.name);
   await page.evaluate(()=>window.RamadanWarDebug.spawnTestEnemy());
   await page.evaluate(()=>{window.RamadanWarDebug.fire();window.RamadanWarDebug.rocket();window.RamadanWarDebug.drone()});
   await page.evaluate(()=>{window.RamadanWarDebug.spawnTestPickup('ammo');window.RamadanWarDebug.tick(.04)});state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.shots,1);assert.equal(state.rockets,11);assert.equal(state.drones,2);assert.equal(state.ammo,8,'ammo pickup restores the magazine');
   await page.locator('#pause').click();await page.locator('#pausePanel:not(.hidden)').waitFor();await page.reload({waitUntil:'domcontentloaded'});
   assert.match(await page.locator('#start').innerText(),/ادامه/);
   await page.locator('#start').click();
   state=await page.evaluate(()=>window.RamadanWarDebug.getState());assert.equal(state.stage,0);assert.equal(state.rockets,11);assert.equal(state.drones,2);assert.equal(state.mode,'game');
   // A real pointer click exercises the published control path, unlike debug.fire().
   assert((await page.locator('#pause').getAttribute('aria-label'))?.length>=3,'pause needs a screen-reader name');
   await page.evaluate(()=>{for(let i=0;i<40;i++)window.RamadanWarDebug.tick(.04)});
   const shotsBefore=await page.evaluate(()=>window.RamadanWarDebug.getState().shots);
   await page.locator('#fire').click();
   await page.waitForFunction(n=>window.RamadanWarDebug.getState().shots>n,shotsBefore,{timeout:5000});
   console.log('RAMADAN_REAL_POINTER_FIRE_PASS',v.name);

   // Browser-level ownership regression: an unrelated finger's pointerup must
   // not stop a genuine held fire pointer. Run only against the local candidate.
   if(['127.0.0.1','localhost'].includes(new URL(process.env.GAME_URL).hostname)){
     const fireBox=await page.locator('#fire').boundingBox();
     assert(fireBox&&fireBox.width>10,'fire control must be rendered');
     await page.evaluate(()=>{window.__ramadanFireOwner=null;document.querySelector('#fire').addEventListener('pointerdown',e=>{if(e.isTrusted)window.__ramadanFireOwner=e.pointerId},{once:true})});
     await page.mouse.move(fireBox.x+fireBox.width/2,fireBox.y+fireBox.height/2);
     try{
       await page.mouse.down();
       assert.equal(await page.evaluate(()=>document.querySelector('#fire').hasPointerCapture(window.__ramadanFireOwner)),true,'real owner must hold pointer capture');
       await page.evaluate(()=>{
         const button=document.querySelector('#fire');
         button.dispatchEvent(new PointerEvent('pointerdown',{pointerId:777,pointerType:'touch',bubbles:true}));
         button.dispatchEvent(new PointerEvent('pointerup',{pointerId:777,pointerType:'touch',bubbles:true}));
       });
       assert.equal(await page.evaluate(()=>document.querySelector('#fire').hasPointerCapture(window.__ramadanFireOwner)),true,'unrelated pointer release must preserve owner capture');
       console.log('RAMADAN_FIRE_POINTER_OWNERSHIP_PASS',v.name);
     }finally{await page.mouse.up()}
   }



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
