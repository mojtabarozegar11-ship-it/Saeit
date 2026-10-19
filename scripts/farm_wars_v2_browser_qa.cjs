const {chromium}=require('playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const dir='artifacts/farm-wars-qa';fs.mkdirSync(dir,{recursive:true});
 const errors=[];
 for(const target of [{name:'desktop',width:1440,height:960,isMobile:false},{name:'mobile',width:390,height:844,isMobile:true}]){
  const context=await browser.newContext({viewport:{width:target.width,height:target.height},deviceScaleFactor:1,isMobile:target.isMobile,hasTouch:target.isMobile});
  const page=await context.newPage();
  page.on('pageerror',e=>errors.push(target.name+': '+e.message));
  const response=await page.goto('https://zomorodmelal.ir/farm-wars/?qa_iso_2='+process.env.GITHUB_RUN_ID,{waitUntil:'domcontentloaded',timeout:45000});
  if(!response||response.status()!==200)throw Error(target.name+': live game HTTP not 200');
  await page.waitForFunction(()=>window.FarmWarsV2Test&&document.querySelector('canvas#land')?.width>100,{timeout:15000});
  await page.waitForTimeout(1100);
  const before=await page.evaluate(()=>{
    const canvas=document.querySelector('#land'),state=window.FarmWarsV2Test.getState();
    const ctx=canvas.getContext('2d');const cx=Math.floor(canvas.width/2),cy=Math.floor(canvas.height/2);
    const samples=[];
    for(let k=0;k<7;k++){const pixel=ctx.getImageData(Math.max(0,cx-240+k*80),cy,1,1).data;samples.push(Array.from(pixel).join(','));}
    return {state,canvasSize:[canvas.width,canvas.height],distinctColors:new Set(samples).size,scrollWidth:document.documentElement.scrollWidth,viewportWidth:innerWidth,gameFrameVisible:canvas.getBoundingClientRect().height>450};
  });
  if(before.distinctColors<3)throw Error(target.name+': game canvas lacks meaningful render colors');
  if(!before.gameFrameVisible)throw Error(target.name+': main isometric world not visible');
  if(before.viewportWidth+5<before.scrollWidth)throw Error(target.name+': unwanted horizontal page overflow');
  await page.screenshot({path:dir+'/'+target.name+'-live.png',fullPage:true});
  await page.evaluate(()=>{window.FarmWarsV2Test.select(0,0);});
  await page.locator('[data-act="wheat"]').click();
  const after=await page.evaluate(()=>window.FarmWarsV2Test.getState());
  if(after.map[0].type!=='wheat'||after.gold!==before.state.gold-12)throw Error(target.name+': wheat planting did not update game state');
  await page.screenshot({path:dir+'/'+target.name+'-after-planting.png',fullPage:true});
  console.log(target.name.toUpperCase()+'_BROWSER_QA=PASS pixels='+before.distinctColors+' canvas='+before.canvasSize.join('x')+' goldAfter='+after.gold);
  await context.close();
 }
 await browser.close();
 if(errors.length)throw Error('Browser JavaScript errors: '+errors.join(' | '));
 console.log('FARM_WARS_V2_REAL_BROWSER_QA=PASS');
})().catch(e=>{console.error(e);process.exit(1)});
