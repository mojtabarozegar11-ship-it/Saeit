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
     html=html.replace(anchor,'window.__g01AirInput=()=>({afterburner,boostHeld,paused,run,stickX:stick.x,stickY:stick.y});'+anchor);
     route.fulfill({status:200,contentType:'text/html',body:html});
    });
    assert.equal((await air.goto(base+'/games/air-supremacy/index.html',{waitUntil:'domcontentloaded',timeout:45000})).status(),200);
    await air.waitForFunction(()=>window.__g01AirInput);
    await air.locator('#launch').click();
    await air.evaluate(()=>document.querySelector('#boostBtn').dispatchEvent(new PointerEvent('pointerdown',{pointerType:'touch',button:0,bubbles:true,cancelable:true})));
    await air.waitForFunction(()=>window.__g01AirInput().afterburner,{timeout:5000});
    await air.locator('#pauseBtn').click();
    const paused=await air.evaluate(()=>window.__g01AirInput());
    assert(paused.paused&&!paused.afterburner&&!paused.boostHeld,'afterburner must stop immediately on pause');
    await air.locator('#resumeBtn').click();
    await air.waitForTimeout(100);
    assert.equal((await air.evaluate(()=>window.__g01AirInput())).afterburner,false,'boost must not relatch on resume');
    assert.deepEqual(airErrors,[]);
    console.log('AIR_THRUST_PAUSE_'+(mobile?'MOBILE':'DESKTOP')+'=PASS');
    await air.close();
    const crown=await context.newPage(),crownErrors=[];
    crown.on('pageerror',e=>crownErrors.push(e.message));
    await crown.route('**/games/crown-defender/index.html',route=>{
     let html=fs.readFileSync(path.join(root,'games/crown-defender/index.html'),'utf8');
     const anchor='window.__mpwCrownDefenderTest={';
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
    assert.deepEqual(crownErrors,[]);
    console.log('CROWN_HANGAR_INPUT_'+(mobile?'MOBILE':'DESKTOP')+'=PASS');
    await crown.close();
   }finally{await context.close()}
  }
 }finally{await browser.close()}
}
run().catch(e=>{console.error(e);process.exit(1)});
