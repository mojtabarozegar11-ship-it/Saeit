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
        assert.match(await page.locator('#cakepreview').getAttribute('aria-label'),/berries, 0 candles/);
        assert.equal(await page.locator('[data-top="🍓"]').getAttribute('aria-pressed'),'true');
        assert.equal(await page.locator('[data-top="🍬"]').getAttribute('aria-pressed'),'false');
        await page.locator('[data-top="🍬"]').click();
        assert.equal(await page.locator('[data-top="🍬"]').getAttribute('aria-pressed'),'true');
        assert.equal(await page.locator('[data-top="🍓"]').getAttribute('aria-pressed'),'false');
        await page.locator('[data-action="candle"]').click();
        await page.locator('[data-action="candle"]').click();
        const preview=await page.locator('#cakepreview').textContent();
        assert.match(preview,/🍬/);
        assert.equal((preview.match(/🕯️/g)||[]).length,2,'topping change must preserve candles');
        assert.match(await page.locator('#cakepreview').getAttribute('aria-label'),/sweets, 2 candles/);
        assert.match(await page.locator('#gamebody .game-message').textContent(),/candle/);
        await page.locator('#icing').evaluate(el=>{el.value='#11aa22';el.dispatchEvent(new Event('input',{bubbles:true}))});
        assert.match(await page.locator('#cakepreview').getAttribute('aria-label'),/frosting #11aa22/);
        assert.match(await page.locator('#gamebody .game-message').textContent(),/Frosting color updated/);
        const waiting=page.waitForEvent('download',{timeout:10000});
        await page.locator('[data-action="cake-download"]').click();
        const download=await waiting;
        assert.equal(download.suggestedFilename(),'taniya-cake-card.svg');
        const svg=fs.readFileSync(await download.path(),'utf8');
        assert.match(svg,/fill="#11aa22"/);
        assert.match(svg,/🍬/);
        assert.equal((svg.match(/🕯️/g)||[]).length,2);
        for(let i=0;i<10;i++)await page.locator('[data-action="candle"]').click();
        assert.equal(await page.locator('[data-action="candle"]').isDisabled(),true,
          'adding candles must stop at twelve');
        assert.match(await page.locator('#cakepreview').getAttribute('aria-label'),/12 candles/);
        await page.locator('[data-action="cake-reset"]').click();
        assert.equal(await page.locator('[data-action="candle"]').isEnabled(),true,
          'reset must allow candles again');
        assert.equal(await page.locator('[data-top="🍓"]').getAttribute('aria-pressed'),'true');
        const reset=await page.locator('#cakepreview').textContent();
        assert.match(reset,/🍓/);
        assert.equal((reset.match(/🕯️/g)||[]).length,0);
        assert.match(await page.locator('#cakepreview').getAttribute('aria-label'),/berries, 0 candles/);
        console.log('TANIYA_CAKE_BROWSER_PASS',device.name);
      }finally{await context.close()}
    }
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
