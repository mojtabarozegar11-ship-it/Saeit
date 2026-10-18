/* Tala international indicative spot board. Prices are USD per troy ounce, never Iran market prices. */
(function(root){
'use strict';
const OZ_GRAMS=31.1034768;
function interpret(raw,symbol,nowMs=Date.now()){
  if(!raw||raw.symbol!==symbol||raw.currency!=='USD')throw new Error('نماد یا ارز نامعتبر است.');
  const price=Number(raw.price);
  if(!Number.isFinite(price)||price<=0||price>10000000)throw new Error('نرخ نامعتبر است.');
  const t=Date.parse(raw.updatedAt);
  if(!Number.isFinite(t)||t>nowMs+120000)throw new Error('زمان منبع نامعتبر است.');
  const age=Math.max(0,nowMs-t);
  return {symbol,price,t,stale:age>3600000,usdPerGram:price/OZ_GRAMS};
}
function money(n){return new Intl.NumberFormat('fa-IR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n);}
root.TalaLiveSpot={interpret,money,OZ_GRAMS};
if(typeof document==='undefined')return;
const specs=[['XAU','xau'],['XAG','xag'],['XPT','xpt'],['XPD','xpd']];
async function fetchSpot([symbol,id]){
  const output=document.getElementById('spot-'+id);
  const detail=document.getElementById('spot-'+id+'-meta');
  if(!output||!detail)return false;
  try{
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    let response;
    try{response=await fetch('https://api.gold-api.com/price/'+symbol,{cache:'no-store',signal:controller.signal,headers:{'Accept':'application/json'}})}
    finally{clearTimeout(timer)}
    if(!response.ok)throw new Error('پاسخ '+response.status);
    const quote=interpret(await response.json(),symbol);
    output.textContent='$'+money(quote.price)+' / oz';
    const stamp=new Intl.DateTimeFormat('fa-IR',{dateStyle:'short',timeStyle:'short',timeZone:'Asia/Tehran'}).format(new Date(quote.t));
    detail.textContent=(quote.stale?'آخرین قیمت · قدیمی':'قیمت منبع به‌روز')+' · '+stamp+' · $'+money(quote.usdPerGram)+' / گرم';
    return !quote.stale;
  }catch(e){
    output.textContent='نرخ قابل تأیید نیست';
    detail.textContent='دریافت ناموفق؛ عدد تخمینی نمایش داده نمی‌شود';
    return false;
  }
}
let busy=false;
async function refresh(){
 if(busy||document.hidden)return;
 busy=true;
 const status=document.getElementById('tala-world-spot-status');
 if(status)status.textContent='در حال بررسی تاریخ و قیمت منبع…';
 try{
   const result=await Promise.all(specs.map(fetchSpot));
   const count=result.filter(Boolean).length;
   if(status)status.textContent=count?'نرخ‌های به‌روز: '+new Intl.NumberFormat('fa-IR').format(count)+' مورد از ۴ · دلار به ازای اونس تروا':'نرخ تازه‌ای از منبع تأیید نشد؛ تاریخ هر دارایی را بررسی کنید';
 }finally{busy=false}
}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
window.setInterval(refresh,180000);
refresh();
})(typeof window==='undefined'?globalThis:window);
