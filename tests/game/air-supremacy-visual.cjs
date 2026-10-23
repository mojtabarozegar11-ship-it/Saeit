'use strict';
/** Actual interactive WebGL/Canvas smoke against the static game, no server/payment mocks. */
const { chromium, devices } = require('playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const OUT = process.env.RUNNER_TEMP || '/tmp';
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--enable-webgl']});
  const errors=[];
  for(const profile of [
    {kind:'desktop',opts:{viewport:{width:1280,height:720},deviceScaleFactor:1,hasTouch:false}},
    {kind:'mobile',opts:{viewport:{width:390,height:844},deviceScaleFactor:1,hasTouch:true,isMobile:true}},
  ]){
    const context=await browser.newContext({...profile.opts});
    const page=await context.newPage();
    const thisErrors=[];
    page.on('pageerror',e=>thisErrors.push(String(e)));
    page.on('console',msg=>{if(msg.type()==='error')thisErrors.push(msg.text())});
    const url='http://127.0.0.1:8765/air-supremacy/index.html';
    await page.goto(url,{waitUntil:'domcontentloaded',timeout:20000});
    await page.waitForFunction('!!window.__AIR_SUPREMACY_QA__',{timeout:25000});
    const start=await page.evaluate(()=>window.__AIR_SUPREMACY_QA__.snapshot());
    assert.equal(start.running,false);
    await page.screenshot({path:OUT+'/air-redesign-'+profile.kind+'-menu.png'});
    await page.locator('#launch').click();
    await page.waitForTimeout(1250);
    const running=await page.evaluate(()=>window.__AIR_SUPREMACY_QA__.snapshot());
    assert.equal(running.running,true);
    assert.equal(running.playerHp,100);
    assert.equal(running.mission,1);
    assert.equal(await page.locator('#speedHud').isVisible(),true);
    if(profile.kind==='mobile'){
      assert.equal(await page.locator('#boostBtn').isVisible(),true);
      await page.locator('#boostBtn').dispatchEvent('pointerdown');
      await page.waitForTimeout(150);
      const speed=await page.locator('#speedReading').innerText();
      assert.ok(Number(speed)>600,'mobile afterburner must drive displayed speed, got '+speed);
      await page.locator('#boostBtn').dispatchEvent('pointerup');
    }else{
      await page.keyboard.down('e');
      await page.waitForTimeout(160);
      const speed=await page.locator('#speedReading').innerText();
      assert.ok(Number(speed)>600,'desktop afterburner must drive displayed speed');
      await page.keyboard.up('e');
      await page.keyboard.press('Space');
    }
    await page.screenshot({path:OUT+'/air-redesign-'+profile.kind+'-gameplay.png'});
    await page.locator('#pauseBtn').click();
    assert.equal(await page.locator('#pauseOverlay').isVisible(),true);
    await page.locator('#resumeBtn').click();
    assert.equal(await page.locator('#pauseOverlay').isVisible(),false);
    const data=await page.evaluate(()=>{
      const c=document.querySelector('#field');
      const q=window.__AIR_SUPREMACY_QA__.snapshot();
      return {webgl:q.webgl,fps:q.fps,width:c.width,height:c.height,mission:q.mission,gameTitle:document.title};
    });
    assert.ok(data.width>200&&data.height>200);
    assert.equal(data.webgl,true,'A supported Chrome browser must render native 3D WebGL, not the 2D fallback');
    assert.equal(data.mission,1);
    assert.ok(thisErrors.length===0,'Browser errors: '+thisErrors.join('; ').slice(0,800));
    assert.ok(fs.statSync(OUT+'/air-redesign-'+profile.kind+'-gameplay.png').size>12000,
      'screenshot must contain a rendered battlefield');
    errors.push(...thisErrors);
    console.log('AIR_RED_SIGNOFF',JSON.stringify({profile:profile.kind,...data,shotBytes:fs.statSync(OUT+'/air-redesign-'+profile.kind+'-gameplay.png').size,jsErrors:thisErrors.length}));
    await context.close();
  }
  await browser.close();
  assert.deepEqual(errors,[]);
  console.log('AIR_SUPREMACY_INTERACTIVE_RENDER_QA=PASS');
})().catch(e=>{console.error('AIR_INTERACTIVE_TEST_FAILED',e.stack||e);process.exit(1)});
