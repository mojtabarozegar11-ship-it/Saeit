'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {chromium}=require('playwright');
for(const f of ['studio_raha/index.html','taniya_studio/index.html']){
 const html=fs.readFileSync('templates/'+f,'utf8');
 const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(x=>x[1]).filter(Boolean);
 assert(scripts.length,'inline JS exists '+f);
 scripts.forEach(s=>new vm.Script(s,{filename:f}));
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  for(const viewport of [{width:1280,height:800},{width:390,height:844}]){
   const ctx=await browser.newContext({viewport,acceptDownloads:true}),page=await ctx.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto('http://127.0.0.1:8771/templates/studio_raha/index.html',{waitUntil:'domcontentloaded'});
   await page.locator('[data-play="0"]').click();
   await page.locator('#runnerTrack').waitFor({state:'visible'});
   assert.match(await page.locator('#runScore').textContent(),/Cleared: 0 \/ 8/);
   await page.locator('#gameStage button').first().click();
   assert.match(await page.locator('#runScore').textContent(),/Cleared: 0 \/ 8/,'tap is not a fake score');
   await page.waitForTimeout(850);
   await page.keyboard.press('Space');
   await page.waitForTimeout(700);
   assert.match(await page.locator('#runScore').textContent(),/Cleared: 1 \/ 8/,'timed jump clears actual obstacle');
   await page.locator('[data-close="gameOverlay"]').first().click();
   assert.equal(await page.locator('#gameOverlay').getAttribute('aria-hidden'),'true');
   assert.deepEqual(errors,[],'Roham page errors');await ctx.close();
  }
  const ctx=await browser.newContext({viewport:{width:390,height:844},acceptDownloads:true}),page=await ctx.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8771/templates/taniya_studio/index.html',{waitUntil:'domcontentloaded'});
  await page.locator('.play[data-game="Cake Maker"]').click();
  await page.locator('#icing').evaluate(el=>{el.value='#0088ff';el.dispatchEvent(new Event('input',{bubbles:true}))});
  await page.locator('[data-top="🌼"]').click();
  await page.locator('[data-action="candle"]').click({clickCount:2});
  assert.match(await page.locator('#cakepreview').textContent(),/🕯️🕯️/);
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('[data-action="cake-download"]').click()]);
  const svg=fs.readFileSync(await download.path(),'utf8');
  assert(svg.includes('fill="#0088ff"'),'custom icing exported');
  assert(svg.includes('🌼'),'chosen topping exported');
  assert.equal((svg.match(/fill="#ffa322"/g)||[]).length,2,'two candles exported');
  await page.locator('#close').click();
  await page.reload({waitUntil:'domcontentloaded'});
  await page.locator('.play[data-game="Cake Maker"]').click();
  assert.equal(await page.locator('#icing').inputValue(),'#0088ff','cake icing restored after reload');
  assert.match(await page.locator('#cakepreview').textContent(),/🌼.*🕯️🕯️/,'topping and candles restored');
  await page.locator('[data-action="cake-reset"]').click();
  assert.equal(await page.evaluate(()=>localStorage.getItem('taniyaCakeDesign')),null,'reset clears saved cake');
  assert(!String(await page.locator('#cakepreview').textContent()).includes('🕯️'),'reset clears candles');
  assert.deepEqual(errors,[],'Taniya page errors');await ctx.close();
  console.log('G-01 R14 browser QA: runner desktop/mobile, keyboard, cake custom export/reset PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
