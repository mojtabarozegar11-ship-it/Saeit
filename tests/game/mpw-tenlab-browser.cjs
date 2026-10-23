'use strict';
const {chromium}=require('playwright-core'),assert=require('node:assert/strict'),fs=require('node:fs');
const origin='http://127.0.0.1:8765/',out=process.env.RUNNER_TEMP||'/tmp';
const games=['windward-regatta','lexicon-sprint','grid-dominion','metro-vault','cargo-switchyard'];
const tools=['invoice-craft','csv-workbench','image-slimmer','schema-builder','contrast-studio'];
(async()=>{
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
try{
 for(const mobile of [false,true]){
  const context=await browser.newContext(mobile?{viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1}:{viewport:{width:1230,height:860}});
  for(const slug of games){
   const page=await context.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   const res=await page.goto(origin+slug+'/index.html',{waitUntil:'domcontentloaded',timeout:25000});
   assert.equal(res.status(),200,slug);
   assert.equal(await page.locator('html').getAttribute('lang'),'en');
   await page.waitForFunction('window.__MPW_TEN_GAME_QA__ && window.__MPW_TEN_GAME_QA__.snapshot().frame>2',{timeout:15000});
   await page.locator('#start').click();
   await page.waitForTimeout(180);
   let state=await page.evaluate(()=>window.__MPW_TEN_GAME_QA__.snapshot());
   assert.equal(state.active,true,slug+' did not start');
   assert.equal(state.slug,slug);
   if(mobile){
      await page.locator('#action').dispatchEvent('pointerdown');
      await page.locator('#action').dispatchEvent('pointerup');
   }else{
      await page.keyboard.press('Space');
      await page.keyboard.press('ArrowRight');
      await page.locator('#stage').click({position:{x:200,y:180}});
   }
   await page.waitForTimeout(200);
   await page.screenshot({path:out+'/tenlab-'+(mobile?'mobile-':'desktop-')+slug+'.png'});
   await page.locator('#pause').click();
   state=await page.evaluate(()=>window.__MPW_TEN_GAME_QA__.snapshot());
   if(state.active)assert.equal(state.paused,true);
   assert.deepEqual(errors,[],slug+' browser JS error');
   assert.ok(fs.statSync(out+'/tenlab-'+(mobile?'mobile-':'desktop-')+slug+'.png').size>8000,'blank game screen');
   console.log('TENLAB_GAME_PLAYABLE',mobile?'MOBILE':'DESKTOP',slug,JSON.stringify(state));
   await page.close();
  }
  await context.close();
 }
 const ctx=await browser.newContext({viewport:{width:1160,height:900}});
 const p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
 async function visit(s){const res=await p.goto(origin+s+'/index.html',{waitUntil:'domcontentloaded'});assert.equal(res.status(),200);await p.waitForFunction('window.__MPW_TEN_TOOL_QA__?.ready===true');assert.equal(await p.evaluate(()=>window.__MPW_TEN_TOOL_QA__.name),s)}
 await visit('invoice-craft');await p.locator('#client').fill('Example Buyer');await p.locator('#calculate').click();assert.match(await p.locator('#result').innerText(),/TOTAL/);assert.match(await p.locator('#result').innerText(),/Example Buyer/);
 console.log('TENLAB_INVOICE_CALCULATED');
 await visit('csv-workbench');await p.locator('#sample').click();assert.match(await p.locator('#stats').innerText(),/duplicates removed/);assert.match(await p.locator('#result').innerText(),/Taylor/);console.log('TENLAB_CSV_DEDUPED');
 await visit('image-slimmer');const sample=await p.evaluate(()=>{const c=document.createElement('canvas');c.width=128;c.height=96;const k=c.getContext('2d');k.fillStyle='#21a3c9';k.fillRect(0,0,128,96);k.fillStyle='orange';k.fillRect(30,15,45,51);return c.toDataURL('image/png').split(',')[1]});await p.locator('#upload').setInputFiles({name:'qa.png',mimeType:'image/png',buffer:Buffer.from(sample,'base64')});await p.locator('#optimize').click();await p.waitForFunction("document.querySelector('#stats').textContent.includes('optimized')",{timeout:15000});assert.match(await p.locator('#stats').innerText(),/optimized/);console.log('TENLAB_IMAGE_COMPRESSED');
 await visit('schema-builder');await p.locator('#f_name').fill('Test Article');await p.locator('#f_author').fill('Site Editor');await p.locator('#f_url').fill('https://example.com/article');await p.locator('#f_datePublished').fill('2026-10-23');await p.locator('#build').click();assert.equal(JSON.parse(await p.locator('#result').innerText())['@type'],'Article');console.log('TENLAB_SCHEMA_JSONLD_VALID');
 await visit('contrast-studio');assert.match(await p.locator('#scores').innerText(),/PASS/);await p.locator('#foreground').fill('#777777');await p.locator('#background').fill('#777777');await p.locator('#measure').click();assert.match(await p.locator('#scores').innerText(),/FAIL/);await p.locator('#light').click();assert.match(await p.locator('#scores').innerText(),/PASS/);console.log('TENLAB_WCAG_CONTRAST_PASS_FAIL_AND_SUGGEST_PASS');
 assert.deepEqual(errors,[]);await p.screenshot({path:out+'/tenlab-contrast-studio.png'});
 const home=await p.goto(origin+'index.html');assert.equal(home.status(),200);assert.equal(await p.locator('.card').count(),10);assert.ok((await p.locator('body').innerText()).includes('Five new worlds.'));
 console.log('TENLAB_HUB_TEN_CARDS_OK');
 await ctx.close();
}finally{await browser.close()}
console.log('TENLAB_REAL_BROWSER_5_GAMES_5_TOOLS=PASS');
})().catch(e=>{console.error('TENLAB_BROWSER_FAILED',e.stack||e);process.exit(1)});
