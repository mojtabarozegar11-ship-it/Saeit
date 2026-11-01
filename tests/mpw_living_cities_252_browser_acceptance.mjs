import assert from "node:assert/strict";
import {chromium} from "playwright";

const ROOT = "https://mojplaywin.com";
const browser = await chromium.launch({
  headless: true,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl", "--no-sandbox"],
});
const issues=[];
try{
  const page=await browser.newPage({viewport:{width:1392,height:910},acceptDownloads:true});
  page.on("pageerror",error=>issues.push("desktop:"+error.message));
  let landing=await page.goto(ROOT+"/living-cities/",{waitUntil:"domcontentloaded",timeout:40000});
  assert.equal(landing?.status(),200,"global landing HTTP response");
  assert.match(await page.locator("h1").innerText(),/LIVING CITIES/);
  assert.equal(await page.locator('a[href="/living-cities/play/"]').count(),1);

  const response=await page.goto(ROOT+"/living-cities/play/",{waitUntil:"domcontentloaded",timeout:40000});
  assert.equal(response?.status(),200,"real playable route");
  await page.waitForSelector("#lcLanguage",{timeout:15000});
  await page.waitForSelector('[data-global-tour]',{timeout:15000});
  assert.equal(await page.locator("#lcLanguage option").count(),20,"actual language options");
  assert.equal(await page.locator("html").getAttribute("lang"),"en");
  await page.locator('[data-global-tour]').click();
  await page.waitForSelector("#lcGlobalHub:not([hidden])");
  assert.equal(await page.locator(".lc-region").count(),20,"actual world chapters");
  assert.equal(await page.locator(".lc-mission").count(),10,"actual region missions");
  await page.waitForSelector(".lc-weekly",{timeout:15000});
  assert.match(await page.locator(".lc-weekly").innerText(),/Weekly expedition|weekly expedition/i);
  const assets=await page.evaluate(async()=>{
    const mod=await import("/living-cities/static/living_cities/weekly-expeditions.mjs");
    const glossary=await import("/living-cities/static/living_cities/gameplay-i18n.mjs");
    return {weeks:mod.YEARLY_CONTRACTS.length,languageLabels:glossary.UI_GAMEPLAY_KEYS.length};
  });
  assert.equal(assets.weeks,52,"must be 52 genuinely tracked weekly contracts");
  assert.equal(assets.languageLabels,34,"must retain fully localized gameplay controls");
  assert.match(await page.locator(".lc-tour-hero").innerText(),/200/);
  await page.locator("#lcLanguage").selectOption("ar");
  assert.equal(await page.locator("html").getAttribute("dir"),"rtl");
  assert.match(await page.locator("#lcGlobalHub").innerText(),/جولة العالم/);
  assert.match(await page.locator(".lc-weekly").innerText(),/رحلة استكشاف أسبوعية/);
  await page.locator("#lcLanguage").selectOption("fa");
  assert.match(await page.locator("#lcGlobalHub").innerText(),/سفر جهانی/);
  assert.match(await page.locator(".lc-weekly").innerText(),/ماموریت هفتگی/);
  await page.locator("#lcLanguage").selectOption("en");
  assert.equal(await page.locator("html").getAttribute("dir"),"ltr");
  await page.locator('[data-lc-region="legacy"]').click();
  assert.equal(await page.locator(".lc-mission").count(),10,"last chapter has 10 challenges");
  await page.locator('[data-lc-region="aurora"]').click();

  // All real in-game economy actions still work and persist locally.
  await page.locator('[data-tycoon-tab="businesses"]').click();
  await page.waitForSelector("#tycoonHub:not([hidden])");
  await page.waitForSelector('[data-tycoon-action="smart-upgrade"]:not([disabled])');
  const before=await page.evaluate(()=>JSON.parse(localStorage.getItem("living-cities-tycoon-v1")||"null"));
  await page.locator('[data-tycoon-action="smart-upgrade"]:not([disabled])').click();
  await page.waitForTimeout(500);
  const after=await page.evaluate(()=>JSON.parse(localStorage.getItem("living-cities-tycoon-v1")||"null"));
  assert.ok(after?.state?.businessLevels?.bakery > (before?.state?.businessLevels?.bakery||1),
    "smart upgrade changes actual persistent economy save");
  await page.locator('[data-global-tour]').click();
  const dl=page.waitForEvent("download");
  await page.locator('[data-lc-action="export"]').click();
  const downloaded=await dl;
  assert.equal(downloaded.suggestedFilename(),"living-cities-global-save.json");
  await page.reload({waitUntil:"domcontentloaded"});
  await page.waitForSelector('[data-global-tour]');
  const restored=await page.evaluate(()=>JSON.parse(localStorage.getItem("living-cities-tycoon-v1")||"null"));
  assert.ok(restored?.state?.businessLevels?.bakery>=after.state.businessLevels.bakery,
    "legacy local save is preserved across reload");
  console.log("MPW_DESKTOP_252_QUESTS_LANGUAGE_REAL_ACTION_SAVE=PASS");

  const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:2,
    isMobile:true,hasTouch:true});
  mobile.on("pageerror",error=>issues.push("mobile:"+error.message));
  const m=await mobile.goto(ROOT+"/living-cities/play/",{waitUntil:"domcontentloaded",timeout:40000});
  assert.equal(m?.status(),200);
  await mobile.waitForSelector("#lcLanguage");
  await mobile.locator("#lcLanguage").selectOption("es");
  assert.equal(await mobile.locator("html").getAttribute("lang"),"es");
  await mobile.locator('[data-global-tour]').click();
  await mobile.waitForSelector("#lcGlobalHub:not([hidden])");
  assert.match(await mobile.locator("#lcGlobalHub").innerText(),/Gira mundial/);
  assert.match(await mobile.locator(".lc-weekly").innerText(),/Expedición semanal/);
  assert.equal(await mobile.locator(".lc-region").count(),20);
  await mobile.locator('[data-lc-region="harbor"]').click();
  assert.equal(await mobile.locator(".lc-mission").count(),10);
  console.log("MPW_MOBILE_252_QUESTS_20_LANGUAGES_TOUCH=PASS");
  await mobile.close();

  assert.deepEqual(issues,[],"no uncaught JavaScript exceptions while playing");
  console.log("MPW_252_QUEST_PUBLIC_BROWSER_ACCEPTANCE=PASS");
}finally{await browser.close();}
