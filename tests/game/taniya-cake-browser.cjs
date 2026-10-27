const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  try{
    for(const device of [{name:'desktop',width:1280,height:900,mobile:false},{name:'mobile',width:390,height:844,mobile:true}]){
      const context=await browser.newContext({viewport:{width:device.width,height:device.height},isMobile:device.mobile,hasTouch:device.mobile,acceptDownloads:true});
      try{
        const page=await context.newPage(),errors=[];
        page.on('pageerror',error=>errors.push(error.message));
        await page.goto(pathToFileURL(path.resolve('templates/taniya_studio/index.html')).href,{waitUntil:'domcontentloaded'});
        await page.locator('button.play[data-game="Cake Maker"]').click();
        await page.locator('#cakepreview').waitFor({state:'visible',timeout:5000}).catch(async error=>{
          throw new Error('Cake Maker failed to open: '+errors.join(' | ')+' modal='+await page.locator('#modal').getAttribute('class')+' body='+String(await page.locator('#gamebody').innerHTML()).slice(0,300)+' '+error.message);
        });
        assert.match(await page.locator('#cakepreview').textContent(),/🍓/);
        await page.locator('[data-top="🍬"]').click();
        await page.locator('[data-action="candle"]').click();
        await page.locator('[data-action="candle"]').click();
        const preview=await page.locator('#cakepreview').textContent();
        assert.match(preview,/🍬/);
        assert.equal((preview.match(/🕯️/g)||[]).length,2,'topping change must preserve candles');
        await page.locator('#icing').evaluate(el=>{el.value='#11aa22';el.dispatchEvent(new Event('input',{bubbles:true}))});
        const waiting=page.waitForEvent('download',{timeout:10000});
        await page.locator('[data-action="cake-download"]').click();
        const download=await waiting;
        assert.equal(download.suggestedFilename(),'taniya-cake-card.svg');
        const svg=fs.readFileSync(await download.path(),'utf8');
        assert.match(svg,/fill="#11aa22"/);
        assert.match(svg,/🍬/);
        assert.equal((svg.match(/🕯️/g)||[]).length,2);
        await page.locator('[data-action="cake-reset"]').click();
        const reset=await page.locator('#cakepreview').textContent();
        assert.match(reset,/🍓/);
        assert.equal((reset.match(/🕯️/g)||[]).length,0);
        console.log('TANIYA_CAKE_BROWSER_PASS',device.name);
      }finally{await context.close()}
    }
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
