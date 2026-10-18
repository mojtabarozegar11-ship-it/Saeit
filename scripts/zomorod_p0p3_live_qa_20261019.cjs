const {chromium}=require('playwright');
const AxeBuilder=require('@axe-core/playwright').default;
const ROOT='https://zomorodmelal.ir';
const paths=['/about/','/research/','/knowledge/','/agriculture/','/search/','/topics/','/store/','/tala/','/business/','/en/market/','/en/auctions/','/company/','/'];
const patches=new Set(['/about/','/research/','/knowledge/','/agriculture/','/search/','/topics/','/store/','/tala/','/en/market/','/en/auctions/']);
const axePaths=new Set(['/about/','/research/','/agriculture/','/search/','/topics/','/business/','/tala/']);
const baseline={'/about/':9,'/research/':9,'/agriculture/':3,'/search/':1,'/topics/':1,'/business/':2,'/tala/':1};
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 let count=0,improved=0;
 for(const width of [390,1440]){
  const ctx=await browser.newContext({viewport:{width,height:900}});
  for(const path of paths){
    const page=await ctx.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const response=await page.goto(ROOT+path+'?__p0p3_batch='+width,{waitUntil:'domcontentloaded',timeout:50000});
    await page.waitForTimeout(350);
    const x=await page.evaluate(()=>{
      const a=s=>[...document.querySelectorAll(s)];
      const visible=e=>{const b=e.getBoundingClientRect();return b.width>0&&b.height>0};
      const links=a('a[href]');return {
        title:document.title,desc:document.querySelector('meta[name="description"]')?.content||'',
        canonical:document.querySelector('link[rel="canonical"]')?.href||'',
        h1:a('h1').filter(e=>e.textContent.trim()&&visible(e)).length,
        widths:innerWidth,overflow:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth,
        patch:!!document.getElementById('zm-priority-p0p3-20261019'),
        rootCards:a('.topic-card').length,rootRows:a('.orbit-shelf').length,
        companyCards:a('.zm-history-card').length,smallLinks:links.filter(e=>visible(e)&&e.getBoundingClientRect().height<24).length,
        skipTarget:document.getElementById('main')?.getAttribute('tabindex'),
        skipNav:!!document.querySelector('.zm-p0p3-skip-nav'),
        formLabels:a('.sign input:not([type=hidden])').filter(e=>!e.labels?.length&&!e.getAttribute('aria-label')).length,
        tel:a('a[href^="tel:"]').map(e=>getComputedStyle(e).textDecorationLine).slice(0,2),
        goldApi:a('a[href*="gold-api.com"]').map(e=>getComputedStyle(e).textDecorationLine).slice(0,3)
      };
    });
    let issues=[];
    if(axePaths.has(path)&&width===390){
       const a=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']).analyze();
       issues=a.violations.map(v=>({id:v.id,count:v.nodes.length,impact:v.impact}));
       const n=issues.filter(x=>x.id==='color-contrast').reduce((n,v)=>n+v.count,0);
       if(n>baseline[path])throw Error('Contrast regressed '+path+' from '+baseline[path]+' to '+n);
       if(n<baseline[path])improved++;
       if(issues.some(v=>v.id==='label'||v.id==='skip-link'||v.id==='link-in-text-block'||v.impact==='critical'))throw Error('Priority accessibility failure '+path+' '+JSON.stringify(issues));
    }
    if(response.status()!==200||errors.length||x.overflow>3)throw Error('HTTP JS or overflow '+path+' '+width+' '+JSON.stringify({http:response.status(),errors,overflow:x.overflow}));
    if(patches.has(path)&&!x.patch)throw Error('Missing site fix marker '+path);
    if(path==='/'){
       if(x.rootRows!==29||x.rootCards!==605)throw Error('Homepage cards changed');
    }
    if(path==='/company/'&&x.companyCards!==162)throw Error('Company cards changed');
    if((path==='/about/'||path==='/knowledge/')&&x.h1!==1)throw Error('SEO H1 not corrected '+path);
    if((path==='/agriculture/'||path==='/search/')&&(x.skipTarget!=='-1'||!x.skipNav))throw Error('Skip landmark not corrected '+path);
    if(path==='/business/'&&x.formLabels>0)throw Error('Business setup labels remain missing');
    if((path==='/store/'||path==='/tala/')&&!x.canonical)throw Error('Canonical missing '+path);
    if(path==='/search/'&&!x.desc)throw Error('Search description missing');
    console.log('P0P3_LIVE_PAGE='+JSON.stringify({path,width,http:response.status(),h1:x.h1,overflow:x.overflow,patch:x.patch,cardCount:x.rootCards||x.companyCards,issues}));
    count++;
    await page.close();
  }
  await ctx.close();
 }
 await browser.close();
 if(improved<2)throw Error('Expected multiple improvements in audited contrast');
 console.log('P0P3_COMPLETED_PAGES='+count+' CONTRAST_IMPROVED_PAGES='+improved);
})().catch(e=>{console.error('P0P3_LIVE_QA_FAILED',e.stack||e);process.exit(1)});
