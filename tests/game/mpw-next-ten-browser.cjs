'use strict';
const {chromium}=require('playwright-core'),assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const base='http://127.0.0.1:8765/',tmp=process.env.RUNNER_TEMP||'/tmp';
const games=['hex-bloom','prism-relay','kitchen-rush','type-defender','codebreaker-vault'];
const tools=['file-fingerprint','meeting-time-planner','subtitle-shifter','text-diff-lab','passphrase-forge'];
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
 for(const mobile of [false,true]){
  const context=await browser.newContext(mobile?{viewport:{width:393,height:840},isMobile:true,hasTouch:true,deviceScaleFactor:1}:{viewport:{width:1280,height:900}});
  for(const slug of games){
   const page=await context.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   const response=await page.goto(base+slug+'/index.html',{waitUntil:'domcontentloaded',timeout:22000});assert.equal(response.status(),200);
   assert.equal(await page.locator('html').getAttribute('lang'),'en');
   await page.waitForFunction("window.__MPW_NEXT_GAME_QA__?.snapshot().frame>2",{timeout:15000});
   await page.locator('#start').click();
   await page.waitForTimeout(180);
   let v=await page.evaluate(()=>window.__MPW_NEXT_GAME_QA__.snapshot());assert.equal(v.slug,slug);assert.equal(v.playing,true,slug);
   if(slug==='type-defender'){await page.locator('#typeInput').fill('SOLAR');await page.locator('#typeInput').press('Enter')}
   else if(slug==='codebreaker-vault'){await page.locator('#codeInput').fill('1234');await page.locator('#codeInput').press('Enter');assert.match(await page.locator('#instructions').innerText(),/Exact position|security|vault|Correct digit|Vault locked/i)}
   else{await page.locator('#stage').click({position:{x:210,y:180}});await page.locator('#action').click();}
   await page.screenshot({path:tmp+'/mpw-next-'+(mobile?'mobile-':'desktop-')+slug+'.png'});
   if(await page.evaluate(()=>window.__MPW_NEXT_GAME_QA__.snapshot().playing)){
    await page.locator('#pause').click();
    v=await page.evaluate(()=>window.__MPW_NEXT_GAME_QA__.snapshot());assert.equal(v.paused,true);
   }
   assert.deepEqual(errors,[],slug+' JS errors');assert.ok(fs.statSync(tmp+'/mpw-next-'+(mobile?'mobile-':'desktop-')+slug+'.png').size>8000);
   console.log('ROUND2_GAME_BROWSER_PASS',mobile?'mobile':'desktop',slug);
   await page.close();
  }
  await context.close();
 }
 const context=await browser.newContext({viewport:{width:1270,height:900}}),page=await context.newPage(),errs=[];page.on('pageerror',e=>errs.push(e.message));
 async function visit(slug){const response=await page.goto(base+slug+'/index.html',{waitUntil:'domcontentloaded'});assert.equal(response.status(),200);await page.waitForFunction("window.__MPW_NEXT_TOOL_QA__?.ready===true");assert.equal(await page.evaluate(()=>window.__MPW_NEXT_TOOL_QA__.name),slug)}
 await visit('file-fingerprint');
 const content=Buffer.from('hello from MojPlayWin');
 await page.locator('#file').setInputFiles({name:'sample.txt',mimeType:'text/plain',buffer:content});
 await page.locator('#expected').fill(crypto.createHash('sha256').update(content).digest('hex'));
 await page.locator('#calculate').click();await page.waitForFunction("document.querySelector('#result').textContent.includes('MATCH — integrity confirmed')");
 console.log('ROUND2_SHA256_HASH_MATCH_PASS');
 await visit('meeting-time-planner');await page.locator('#compare').click();assert.equal(await page.locator('tbody tr').count(),11);assert.match(await page.locator('#result').innerText(),/America\/New_York/);console.log('ROUND2_TIMEZONES_11_PASS');
 await visit('subtitle-shifter');await page.locator('#demo').click();assert.match(await page.locator('#result').innerText(),/00:00:02,500/);await page.locator('#format').selectOption('vtt');await page.locator('#convert').click();assert.match(await page.locator('#result').innerText(),/WEBVTT/);console.log('ROUND2_SUBTITLES_SHIFT_SRT_VTT_PASS');
 await visit('text-diff-lab');await page.locator('#example').click();assert.match(await page.locator('#result').innerText(),/\+ Playable build/);assert.match(await page.locator('#result').innerText(),/- Prototype/);console.log('ROUND2_TEXT_DIFF_PASS');
 await visit('passphrase-forge');await page.locator('#generate').click();let phrase=await page.locator('#result').innerText();assert.equal(phrase.split('-').length,6);await page.locator('#mode').selectOption('password');await page.locator('#length').fill('18');await page.locator('#generate').click();assert.equal((await page.locator('#result').innerText()).length,18);console.log('ROUND2_SECURE_PHRASE_PASSWORD_PASS');
 assert.deepEqual(errs,[]);
 const response=await page.goto(base+'index.html');assert.equal(response.status(),200);assert.equal(await page.locator('.card').count(),10);assert.match(await page.locator('body').innerText(),/Five more worlds/);
 console.log('ROUND2_10_CARDS_AND_11_PAGE_HUB_PASS');
 await context.close();
 }finally{await browser.close()}
 console.log('ROUND2_5_GAMES_5_TOOLS_CHROME_PASS');
})().catch(e=>{console.error('ROUND2_QA_FAILED',e.stack||e);process.exit(1)});
