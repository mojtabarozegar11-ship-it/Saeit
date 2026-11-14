/* Executable conversion rehearsal for existing Ghanadi forms.
 * Synthetic customers, loopback HTTP only. Zero production/site/lead writes.
 */
'use strict';
const {chromium}=require('playwright');
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const {URL,URLSearchParams}=require('node:url');
const ROOT=path.resolve(__dirname,'..');
const OUT=path.join(process.env.RUNNER_TEMP||'/tmp','zm-conversion-isolated');
fs.mkdirSync(OUT,{recursive:true});
const pages=new Map([
 ['/ghanadi/',path.join(ROOT,'public/ghanadi/index.html')],
 ['/ghanadi/cafe-shiraz/',path.join(ROOT,'public/ghanadi/cafe-shiraz/index.html')]
]);
let mode='normal';
const submissions=[];
const server=http.createServer(async(req,res)=>{
 const u=new URL(req.url,'http://localhost');
 const send=(status,body,type='text/html; charset=utf-8')=>{
   res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store'});res.end(body);
 };
 if(req.method==='GET'&&pages.has(u.pathname)){
   send(200,fs.readFileSync(pages.get(u.pathname),'utf8'));return;
 }
 if(u.pathname==='/ask-master/index.php'&&req.method==='GET'){
   if(mode==='fail'){send(503,'Service temporarily unavailable');return;}
   if(mode==='external'){send(200,'<form method="post" action="https://invalid.example/ask-master/index.php"><input name="csrf" value="SYNTHETIC-CSRF"></form>');return;}
   send(200,'<form method="post" action="/ask-master/index.php?service=1"><input name="csrf" value="SYNTHETIC-CSRF"></form>');return;
 }
 if(u.pathname==='/ask-master/index.php'&&req.method==='POST'){
   let body='';for await(const piece of req){body+=piece;if(body.length>12000)break;}
   const form=new URLSearchParams(body);
   submissions.push({csrfValid:form.get('csrf')==='SYNTHETIC-CSRF',
     kind:form.get('kind'),emailValid:/^synthetic\d+@example\.test$/.test(form.get('email')||''),
     questionHasQuantity:(form.get('question')||'').includes('تعداد'),
     questionHasCafe:(form.get('question')||'').includes('نام کافه'),
     requiredFields:['name','email','kind','question','csrf'].every(k=>!!form.get(k)),
     extraPaths:form.has('payment')||form.has('card')});
   send(200,'<h1>SYNTHETIC RECEIVED</h1>');return;
 }
 send(404,'Not found');
});
const reports=[];
function check(ok,label){if(!ok)throw Error('CONVERSION_REHEARSAL_'+label)}
async function withPage(browser,origin,route,width){
 const context=await browser.newContext({viewport:{width,height:850},locale:'fa-IR'});
 await context.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():r.abort());
 const page=await context.newPage();
 const jsErrors=[];page.on('pageerror',e=>jsErrors.push(e.message));
 await page.goto(origin+route,{waitUntil:'domcontentloaded',timeout:12000});
 return {page,context,jsErrors};
}
async function fillCafe(page,i){
 await page.locator('input[name="name"]').fill('Synthetic Buyer');
 await page.locator('input[name="email"]').fill('synthetic'+i+'@example.test');
 await page.locator('input[name="cafe"]').fill('کافه ساختگی');
 await page.locator('input[name="district"]').fill('محله آزمایشی');
 await page.locator('select[name="product"]').selectOption({label:'کوکی'});
 await page.locator('input[name="quantity"]').fill('24');
 await page.locator('input[name="consent"]').check();
}
async function main(){
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
   for(const width of [320,390]){
     mode='normal';
     const {page,context,jsErrors}=await withPage(browser,origin,'/ghanadi/',width);
     const before=submissions.length;
     await page.locator('.add').first().click();
     await page.locator('#openCart').click();
     await page.locator('#checkout').click();
     check(await page.locator('#inquiryPanel').isVisible(),'main_inquiry_visible_'+width);
     check(submissions.length===before,'main_no_post_before_customer_submit_'+width);
     await page.locator('#inquiryName').fill('Synthetic Buyer');
     await page.locator('#inquiryEmail').fill('synthetic1@example.test');
     const pending=page.waitForRequest(r=>r.method()==='POST'&&r.url().includes('/ask-master/index.php'),{timeout:15000});
     await page.locator('#submitInquiry').click();
     await pending;
     check(submissions.length===before+1,'main_post_once_'+width);
     const sent=submissions.at(-1);
     check(sent.csrfValid&&sent.requiredFields&&sent.questionHasQuantity&&sent.emailValid&&!sent.extraPaths,'main_payload_'+width);
     const overflow=await page.evaluate(()=>Math.max(0,document.documentElement.scrollWidth-innerWidth));
     reports.push({case:'ghanadi inquiry',width,ok:true,postsToLoopback:1,externalPosts:0,jsErrors:jsErrors.length,overflow});
     check(jsErrors.length===0,'main_js_'+width);
     await context.close();
   }
   for(const [index,width] of [320,390].entries()){
     mode='normal';
     const {page,context,jsErrors}=await withPage(browser,origin,'/ghanadi/cafe-shiraz/',width);
     const before=submissions.length;
     await fillCafe(page,index+2);
     check(submissions.length===before,'cafe_no_auto_post_'+width);
     const pending=page.waitForRequest(r=>r.method()==='POST'&&r.url().includes('/ask-master/index.php'),{timeout:15000});
     await page.locator('#cafeInquirySubmit').click();await pending;
     check(submissions.length===before+1,'cafe_post_once_'+width);
     const sent=submissions.at(-1);
     check(sent.csrfValid&&sent.requiredFields&&sent.questionHasCafe&&sent.questionHasQuantity&&sent.emailValid&&!sent.extraPaths,'cafe_payload_'+width);
     check(jsErrors.length===0,'cafe_js_'+width);
     reports.push({case:'cafe B2B inquiry',width,ok:true,postsToLoopback:1,externalPosts:0,jsErrors:jsErrors.length});
     await context.close();
   }
   for(const failure of ['fail','external']){
     mode=failure;
     const {page,context,jsErrors}=await withPage(browser,origin,'/ghanadi/cafe-shiraz/',390);
     const before=submissions.length;
     await fillCafe(page,7);
     await page.locator('#cafeInquirySubmit').click();
     await page.locator('#cafeInquiryStatus[role="alert"]').waitFor({timeout:15000});
     check(submissions.length===before,'failure_did_not_post_'+failure);
     check(await page.locator('#cafeInquirySubmit').isEnabled(),'failure_allows_retry_'+failure);
     check(jsErrors.length===0,'failure_js_'+failure);
     reports.push({case:'fail-closed '+failure,width:390,ok:true,postsToLoopback:0,externalPosts:0,jsErrors:jsErrors.length});
     await context.close();
   }
 }finally{
   await browser.close();await new Promise(resolve=>server.close(resolve));
 }
 const summary={pass:reports.filter(x=>x.ok).length,total:reports.length,
   syntheticCustomerOnly:true,siteWrites:0,productionFormsSubmitted:0,
   realOrders:0,realRevenueVerified:false};
 fs.writeFileSync(path.join(OUT,'rehearsal.json'),JSON.stringify({summary,reports},null,2));
 console.log('ZM_CONVERSION_REHEARSAL_SUMMARY '+JSON.stringify(summary));
 if(process.env.GITHUB_STEP_SUMMARY){
  fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
    '\n### Existing lead funnels: synthetic loopback-only browser tests\n'+
    summary.pass+'/'+summary.total+' cases, 0 real form submissions and 0 host writes.\n');
 }
 check(summary.pass===summary.total,'incomplete_cases');
}
main().catch(e=>{console.error('ZM_CONVERSION_REHEARSAL_FATAL',e);process.exitCode=1});
