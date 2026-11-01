import {chromium} from "playwright";
import assert from "node:assert/strict";

const URL="https://mojplaywin.com/living-cities/play/";
const LOCALES=["en","zh","hi","es","ar","fr","pt","ru","bn","id","ur","de","ja","tr","vi","ko","fa","ta","te","mr"];
const RTL=new Set(["ar","ur","fa"]);
const browser=await chromium.launch({headless:true,args:["--use-gl=angle","--use-angle=swiftshader","--enable-webgl","--no-sandbox"]});
const errors=[];
try {
 const page=await browser.newPage({viewport:{width:1260,height:840},locale:"de-DE"});
 page.on("pageerror",e=>errors.push("desktop:"+e.message));
 const res=await page.goto(URL,{waitUntil:"domcontentloaded",timeout:42000});
 assert.equal(res?.status(),200);
 await page.waitForSelector("#lcLanguage",{timeout:16000});
 assert.equal(await page.locator("#lcLanguage option").count(),20);
 assert.equal(await page.locator("html").getAttribute("lang"),"en","English must be default even if browser locale is German");
 const t=await page.evaluate(()=>import("/living-cities/static/living_cities/gameplay-i18n.mjs").then(x=>Object.keys(x)));
 assert.ok(t.includes("UI_GAMEPLAY_LANGUAGES"));
 await page.locator('[data-global-tour]').click();
 await page.waitForSelector("#lcGlobalHub:not([hidden])");
 for(const lang of LOCALES){
   await page.locator("#lcLanguage").selectOption(lang);
   assert.equal(await page.locator("html").getAttribute("lang"),lang);
   assert.equal(await page.locator("html").getAttribute("dir"),RTL.has(lang)?"rtl":"ltr");
   const expected=await page.evaluate(async language=>{
     const m=await import("/living-cities/static/living_cities/gameplay-i18n.mjs");
     return {intro:m.gameplayText("worldIntro",language),
       rank:m.gameplayText("rank",language),
       local:m.gameplayText("localOnly",language),
       safety:m.gameplayText("worldSafety",language),
       business:m.gameplayText("businesses",language)};
   },lang);
   assert.ok((await page.locator(".lc-tour-lead").innerText()).includes(expected.intro),
     lang+" gameplay world narrative not translated");
   assert.ok((await page.locator(".lc-tour-lead").innerText()).includes(expected.rank),
     lang+" campaign title not translated");
   assert.ok((await page.locator("#tycoonAuthority").innerText()).includes(expected.local),
     lang+" in-game business account authority not localized");
   assert.ok((await page.locator("#tycoonBody .tycoon-kicker").innerText()).includes(expected.business),
     lang+" tycoon management controls not localized");
 }
 assert.equal(await page.locator(".lc-region").count(),20);
 assert.equal(await page.locator(".lc-mission").count(),10);
 assert.deepEqual(errors,[]);
 console.log("MPW_ALL_TWENTY_DEEP_GAMEPLAY_LOCALIZATIONS_PASSED=PASS");
 await page.close();

 const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:2,hasTouch:true,isMobile:true});
 mobile.on("pageerror",e=>errors.push("mobile:"+e.message));
 const r=await mobile.goto(URL,{waitUntil:"domcontentloaded",timeout:42000});
 assert.equal(r?.status(),200);
 await mobile.waitForSelector("#lcLanguage",{timeout:14000});
 await mobile.locator("#lcLanguage").selectOption("fa");
 await mobile.locator('[data-global-tour]').click();
 await mobile.waitForSelector("#lcGlobalHub:not([hidden])");
 assert.equal(await mobile.locator("html").getAttribute("dir"),"rtl");
 const text=await mobile.locator(".lc-tour-lead").innerText();
 assert.ok(text.includes("با شهرسازی، کسب‌وکار"),"Persian narrative not visible");
 assert.ok(!await mobile.locator("#lcGlobalHub").isHidden());
 assert.deepEqual(errors,[]);
 console.log("MPW_RTL_PERSIAN_MOBILE_WORLD_CAMPAIGN_PASS=PASS");
}finally {await browser.close();}
