// G-01 R58: synthetic hidden-document acceptance on desktop and mobile.
// No deployment, payment, external network or production data.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-webgl','--enable-unsafe-swiftshader']});
 try{
  for(const v of [{name:'desktop',width:1280,height:800,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
   const ctx=await browser.newContext({viewport:{width:v.width,height:v.height},isMobile:v.mobile,hasTouch:v.mobile});
   try{
    const page=await ctx.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const res=await page.goto(process.env.GAME_URL,{waitUntil:'domcontentloaded',timeout:45000});
    assert.equal(res.status(),200);
    await page.waitForFunction(()=>window.RamadanWarDebug?.start);
    await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}));
    await page.evaluate(()=>window.RamadanWarDebug.start());
    assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('playing')),false,'hidden start must be blocked');
    await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,get:()=>false}));
    await page.evaluate(()=>window.RamadanWarDebug.start());
    await page.waitForFunction(()=>document.querySelector('#game').classList.contains('playing'));
    await page.evaluate(()=>document.querySelector('#pause').click());
    await page.locator('#pausePanel').waitFor({state:'visible'});
    await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}));
    await page.evaluate(()=>document.querySelector('#resume').click());
    assert.equal(await page.locator('#game').evaluate(el=>el.classList.contains('playing')),false,'hidden resume must be blocked');
    await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,get:()=>false}));
    assert.deepEqual(errors,[]);
    console.log('R58_BACKGROUND_ENTRY',v.name,'PASS');
   }finally{await ctx.close()}
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
