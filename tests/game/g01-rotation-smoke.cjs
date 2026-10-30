// G-01 independent desktop/mobile pause/resume regression; no wallet or production writes.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const base=process.env.G01_TEST_BASE||'http://127.0.0.1:8766';
async function run(){
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader']});
 try{
  for(const mobile of [false,true]){
   const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1280,height:800},isMobile:mobile,hasTouch:mobile});
   try{
    // Instrument only the test response. No debug mutators are committed to the games.
    const air=await context.newPage(),airErrors=[];
    air.on('pageerror',e=>airErrors.push(e.message));
    await air.route('**/games/air-supremacy/index.html',route=>{
     let html=fs.readFileSync(path.join(root,'games/air-supremacy/index.html'),'utf8');
     const anchor='refreshHangar();spawnScenery();last=performance.now();requestAnimationFrame(loop);';
     assert(html.includes(anchor));
     html=html.replace(anchor,'window.__g01AirInput=()=>({afterburner,boostHeld,paused,run,stickX:stick.x,stickY:stick.y,pointerId,keyCount:key.size});'+anchor);
     route.fulfill({status:200,contentType:'text/html',body:html});
    });
    assert.equal((await air.goto(base+'/games/air-supremacy/index.html',{waitUntil:'domcontentloaded',timeout:45000})).status(),200);
    await air.waitForFunction(()=>window.__g01AirInput);
    await air.locator('#launch').click();
    // Desktop boost uses keyboard; touch controls are intentionally hidden there.
    // Mobile uses a real active pointer so pointer capture can be tested.
    if(mobile){
     const boostBox=await air.locator('#boostBtn').boundingBox();assert(boostBox,'mobile boost button visible');
     await air.mouse.move(boostBox.x+boostBox.width/2,boostBox.y+boostBox.height/2);
     await air.mouse.down();
     await air.waitForFunction(()=>window.__g01AirInput().afterburner,{timeout:5000});
     await air.mouse.move(10,10);await air.mouse.up();
     await air.waitForFunction(()=>!window.__g01AirInput().boostHeld,{timeout:5000});
     await air.mouse.move(boostBox.x+boostBox.width/2,boostBox.y+boostBox.height/2);
     await air.mouse.down();
     await air.waitForFunction(()=>window.__g01AirInput().boostHeld,{timeout:5000});
    }else{
     await air.keyboard.down('e');
     await air.waitForFunction(()=>window.__g01AirInput().afterburner,{timeout:5000});
    }
    if(mobile){
     // Second independent touch must pause while the boost pointer remains captured.
     const pauseBox=await air.locator('#pauseBtn').boundingBox();assert(pauseBox);
     await air.touchscreen.tap(pauseBox.x+pauseBox.width/2,pauseBox.y+pauseBox.height/2);
    }else await air.locator('#pauseBtn').click();
    const paused=await air.evaluate(()=>window.__g01AirInput());
    assert(paused.paused&&!paused.afterburner&&!paused.boostHeld,'afterburner must stop immediately on pause');
    await air.locator('#resumeBtn').click();
    await air.waitForTimeout(100);
    assert.equal((await air.evaluate(()=>window.__g01AirInput())).afterburner,false,'boost must not relatch on resume');
    // Focused UI controls must not fire weapons or register gameplay keys.
    await air.evaluate(()=>document.querySelector('#pauseBtn').dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,code:'KeyM'})));
    assert.equal((await air.evaluate(()=>window.__g01AirInput())).keyCount,0,'focused UI keyboard event must not control the aircraft');
    if(mobile){
      const stickBox=await air.locator('#stickArea').boundingBox();assert(stickBox);
      await air.mouse.move(stickBox.x+stickBox.width*.23,stickBox.y+stickBox.height*.8);
      await air.mouse.down();
      await air.waitForFunction(()=>window.__g01AirInput().pointerId!==null,{timeout:5000});
      const pid=(await air.evaluate(()=>window.__g01AirInput())).pointerId;
      const pauseBox=await air.locator('#pauseBtn').boundingBox();assert(pauseBox);
      await air.touchscreen.tap(pauseBox.x+pauseBox.width/2,pauseBox.y+pauseBox.height/2);
      assert.equal((await air.evaluate(()=>window.__g01AirInput())).pointerId,null,'pause clears joystick ownership');
      assert.equal(await air.evaluate(pid=>document.querySelector('#stickArea').hasPointerCapture(pid),pid),false,'pause releases joystick capture');
      await air.mouse.up();
      await air.locator('#resumeBtn').click();
    }
    assert.deepEqual(airErrors,[]);
    console.log('AIR_THRUST_PAUSE_'+(mobile?'MOBILE':'DESKTOP')+'=PASS');
    await air.close();
    const crown=await context.newPage(),crownErrors=[];
    crown.on('pageerror',e=>crownErrors.push(e.message));
    await crown.route('**/games/crown-defender/index.html',route=>{
     let html=fs.readFileSync(path.join(root,'games/crown-defender/index.html'),'utf8');
     const anchor='const crownQa={getState:';
     assert(html.includes(anchor));
     html=html.replace(anchor,'window.__g01CrownInput=()=>({keyCount:keys.size,heldCount:Object.values(held).filter(Boolean).length,state});'+anchor);
     route.fulfill({status:200,contentType:'text/html',body:html});
    });
    assert.equal((await crown.goto(base+'/games/crown-defender/index.html',{waitUntil:'domcontentloaded',timeout:45000})).status(),200);
    await crown.waitForFunction(()=>window.__mpwCrownDefenderTest);
    await crown.evaluate(()=>window.__mpwCrownDefenderTest.start());
    await crown.keyboard.down('ArrowRight');
    await crown.waitForFunction(()=>window.__g01CrownInput().keyCount>0);
    await crown.evaluate(()=>window.__mpwCrownDefenderTest.openShop());
    const hangar=await crown.evaluate(()=>window.__g01CrownInput());
    assert(hangar.state==='paused'&&hangar.keyCount===0&&hangar.heldCount===0,'hangar must release held combat inputs');
    await crown.evaluate(()=>window.__mpwCrownDefenderTest.gameOver(false));
    assert.equal((await crown.evaluate(()=>window.__g01CrownInput())).keyCount,0);
    await crown.keyboard.up('ArrowRight');
    await crown.evaluate(()=>window.__mpwCrownDefenderTest.start());
    await crown.evaluate(()=>{
      document.querySelector('#mode').dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,code:'ArrowRight'}));
      document.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,code:'KeyE',ctrlKey:true}));
    });
    assert.equal((await crown.evaluate(()=>window.__g01CrownInput())).keyCount,0,'focused controls and modifier shortcuts must not become combat input');
    assert.deepEqual(crownErrors,[]);
    console.log('CROWN_HANGAR_INPUT_'+(mobile?'MOBILE':'DESKTOP')+'=PASS');
    await crown.close();
   }finally{await context.close()}
  }
 }finally{await browser.close()}
}
run().catch(e=>{console.error(e);process.exit(1)});
