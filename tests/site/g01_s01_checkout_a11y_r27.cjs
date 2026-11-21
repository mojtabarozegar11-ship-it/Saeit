'use strict';
// G-01 -> S-01: GET-only, no clicks, form submissions, cookies, payment or customer data.
const CANDIDATE=/(checkout|cart|invoice|pay(?:ment)?|buy|order|purchase|download|پرداخت|خرید|فاکتور|سبد)/i;
function classifyControl(c){
 const signature=[c.text,c.ariaLabel,c.title,c.id,c.href].filter(Boolean).join(' ');
 if(!CANDIDATE.test(signature))return null;
 const issues=[],accessibleName=String(c.ariaLabel||c.text||c.title||'').trim();
 if(!accessibleName)issues.push('MISSING_ACCESSIBLE_NAME');
 if(c.tag==='A'&&(!c.href||c.href==='#'||/^javascript:/i.test(c.href)))issues.push('NON_NAVIGABLE_CHECKOUT_LINK');
 if(c.disabled&&c.ariaDisabled==='false')issues.push('CONFLICTING_DISABLED_STATE');
 if(c.ariaHidden==='true')issues.push('CHECKOUT_CONTROL_HIDDEN_FROM_ASSISTIVE_TECH');
 return {issues,kind:c.tag==='A'?'link':'action',disabled:!!c.disabled};
}
async function auditPage(page){
 const controls=await page.locator('a,button,input[type="submit"],[role="button"]').evaluateAll(elements=>elements.filter(el=>{
  const style=getComputedStyle(el),rect=el.getBoundingClientRect();
  return style.visibility!=='hidden'&&style.display!=='none'&&rect.width>0&&rect.height>0;
 }).map(el=>({tag:el.tagName.toUpperCase(),text:(el.innerText||el.value||'').trim().slice(0,100),ariaLabel:el.getAttribute('aria-label')||'',title:el.getAttribute('title')||'',id:el.id||'',href:el.getAttribute('href')||'',disabled:!!el.disabled,ariaDisabled:el.getAttribute('aria-disabled'),ariaHidden:el.getAttribute('aria-hidden')})));
 const selected=controls.map(classifyControl).filter(Boolean);
 return {controls:controls.length,checkoutCandidates:selected.length,issues:selected.flatMap(c=>c.issues).reduce((a,k)=>(a[k]=(a[k]||0)+1,a),{})};
}
if(require.main===module){
 (async()=>{
  const target=process.env.G01_S01_AUDIT_URL||'https://mojplaywin.com/';
  const u=new URL(target);
  if(!['https://mojplaywin.com','https://www.mojplaywin.com','http://127.0.0.1:8766'].includes(u.origin))throw Error('Unapproved read-only audit origin');
  const {chromium}=require('playwright'),browser=await chromium.launch({headless:true});
  try{
   const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
   const response=await page.goto(target,{waitUntil:'domcontentloaded',timeout:25000});
   if(!response||response.status()>=400)throw Error('GET returned non-success status');
   const report=await auditPage(page);
   console.log(JSON.stringify({audit:'G01-S01-R27-READ_ONLY',status:response.status(),...report}));
  }finally{await browser.close()}
 })().catch(e=>{console.error('AUDIT_BLOCKED:',e.message);process.exitCode=2});
}
module.exports={classifyControl,auditPage};
