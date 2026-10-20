/* Owner-only, genuine PICM text-to-image UI.
   Uses the already deployed private Django JSON queue and protected image endpoint.
   The CPU engine creates technical 256x256 samples, NOT professional/8K images. */
(()=>{
"use strict";
const form=document.getElementById("renderform");
const mode=document.getElementById("mode");
const photo=document.getElementById("photo");
const prompt=document.getElementById("prompt");
const label=document.querySelector('label[for="prompt"]');
const group=document.getElementById("promptgroup");
const button=document.getElementById("submit");
const info=document.getElementById("status");
const preview=document.getElementById("preview");
const notice=document.getElementById("capability-notice");
const textOptions=document.getElementById("text-image-options");
const photoLabel=document.querySelector('label[for="photo"]');
const photoHelp=document.getElementById("photohelp");
const style=document.getElementById("picm-ai-style");
const steps=document.getElementById("picm-ai-steps");
const csrf=form?.querySelector("[name=csrfmiddlewaretoken]")?.value;
if(!form||!mode||!photo||!prompt||!textOptions||!button||!preview||!csrf)return;
let active=false, current=null, objectUrl=null, ending=false;
const key="picm-private-text-image-job";
const isText=()=>mode.value==="text_image";
const idOk=id=>typeof id==="string"&&/^[a-f0-9]{32}$/.test(id);
const show=message=>{if(isText())info.textContent=message};
function keep(id){try{sessionStorage.setItem(key,id)}catch(_e){}}
function recall(){try{const value=sessionStorage.getItem(key);return idOk(value)?value:null}catch(_e){return null}}
function forget(){try{sessionStorage.removeItem(key)}catch(_e){}}
function clearOutput(){if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl=null}}
function sync(){
  const selected=isText();
  textOptions.hidden=!selected;
  photo.required=!selected;
  photo.hidden=selected;
  if(photoLabel)photoLabel.hidden=selected;
  if(photoHelp)photoHelp.hidden=selected;
  if(!selected)return;
  group.hidden=false;
  prompt.required=true;
  prompt.minLength=4;
  prompt.maxLength=580;
  if(label)label.textContent="توصیف تصویر برای موتور هوش مصنوعی";
  prompt.placeholder="مثلاً: یک مزرعه سرسبز در طلوع آفتاب، نور طبیعی، نمای نزدیک از خوشه‌های گندم";
  notice.textContent="ساخت واقعی تصویر با موتور CPU خصوصی VPS. خروجی آزمایشی ۲۵۶×۲۵۶ پیکسل است؛ کیفیت تجاری، 8K یا ساخت فیلم واقعی نیست. حداکثر دو درخواست در ۲۴ ساعت. ممکن است چند دقیقه منتظر بمانید.";
  button.textContent=active?"در حال پیگیری سفارش…":"ساخت عکس با هوش مصنوعی (آزمایشی)";
  if(current){show("پیگیری سفارش خصوصی "+current+"؛ تا پایان پردازش این صفحه را باز نگه دارید.");}
  else {show("شرح عکس و سبک را انتخاب کنید. در این حالت آپلود عکس لازم نیست.");}
}
document.querySelectorAll("[data-mode]").forEach(el=>el.addEventListener("click",sync));
function delay(ms){return new Promise(resolve=>setTimeout(resolve,ms))}
function authenticatedUrl(raw,id){
  const exact="/picm/image/"+id+"/";
  return raw===exact?exact:null;
}
async function finish(id,url){
  const location=authenticatedUrl(url,id);
  if(!location)throw Error("آدرس خروجی خصوصی نامعتبر است.");
  const response=await fetch(location,{credentials:"same-origin",cache:"no-store"});
  if(!response.ok)throw Error("دریافت فایل تصویر ناموفق بود ("+response.status+").");
  const blob=await response.blob();
  if(blob.type!=="image/png"||blob.size<1024||blob.size>2000000)
    throw Error("محتوای خروجی با قرارداد PNG سازگار نیست.");
  const head=new Uint8Array(await blob.slice(0,8).arrayBuffer());
  if(head.join(",")!=="137,80,78,71,13,10,26,10")
    throw Error("امضای فایل PNG معتبر نیست.");
  clearOutput();
  objectUrl=URL.createObjectURL(blob);
  if(!isText())return;
  const image=document.createElement("img");
  image.src=objectUrl;
  image.alt="تصویر واقعی ساخته‌شده توسط موتور آزمایشی PICM";
  const link=document.createElement("a");
  link.href=objectUrl;
  link.download="picm-ai-"+id+".png";
  link.textContent="دریافت فایل تصویر PNG";
  link.style.cssText="display:block;color:#d4dcff;text-decoration:underline;padding:12px;font-weight:800";
  preview.replaceChildren(image,link);
  show("عکس واقعی ۲۵۶×۲۵۶ پیکسل ساخته شد و آماده دانلود است. این خروجی آزمایشی است.");
}
async function poll(id){
  for(let attempt=0;attempt<95&&!ending;attempt++){
    const response=await fetch("/picm/api/status/"+id+"/",{
      method:"GET",credentials:"same-origin",cache:"no-store"
    });
    if(!response.ok)throw Error(response.status===401||response.status===403
      ?"نشست ورود پایان یافته است؛ دوباره وارد PICM شوید."
      :"پیگیری سفارش ناموفق بود ("+response.status+").");
    const data=await response.json();
    if(data.id!==id)throw Error("شناسه سفارش در پاسخ مطابقت ندارد.");
    if(data.state==="done"){
      await finish(id,data.image_url);
      return;
    }
    if(data.state==="failed"){
      forget();
      throw Error("موتور این سفارش را تکمیل نکرد. منابع یا صف VPS را بررسی کنید.");
    }
    if(!["queued","running"].includes(data.state))
      throw Error("وضعیت نامعتبر سفارش: "+String(data.state).slice(0,40));
    show((data.state==="queued"?"سفارش در صف پردازش است.":"موتور CPU در حال ساخت تصویر است.")
      +" شماره پیگیری: "+id+"؛ ممکن است چند دقیقه زمان ببرد.");
    await delay(9000);
  }
  if(!ending)throw Error("زمان پیگیری طولانی شد. شماره سفارش ذخیره است؛ صفحه را تازه کنید.");
}
async function watch(id){
  if(active)return;
  active=true;current=id;button.disabled=true;sync();
  try{await poll(id)}
  catch(error){show("پیگیری تصویر: "+error.message+" شناسه: "+id);}
  finally{active=false;button.disabled=false;sync();}
}
form.addEventListener("submit",async event=>{
  if(!isText())return;
  event.preventDefault();
  event.stopImmediatePropagation();
  if(active)return;
  const description=prompt.value.trim();
  const count=Number(steps.value);
  if(description.length<4||description.length>580||
     !["cinematic","natural","illustration","product"].includes(style.value)||
     ![1,2,3].includes(count)){
    show("متن (۴ تا ۵۸۰ نویسه)، سبک و تعداد مراحل معتبر انتخاب کنید.");
    return;
  }
  active=true;button.disabled=true;sync();
  try{
    const response=await fetch("/picm/api/submit/",{
      method:"POST",credentials:"same-origin",cache:"no-store",
      headers:{"Content-Type":"application/json","X-CSRFToken":csrf},
      body:JSON.stringify({prompt:description,style:style.value,steps:count})
    });
    const result=await response.json().catch(()=>({}));
    if(!response.ok){
      const reasons={
        daily_limit_reached:"سقف دو تصویر در ۲۴ ساعت تکمیل شده است.",
        queue_full:"صف تولید موقتاً پر است.",
        studio_capacity_reached:"ظرفیت ذخیره سفارش‌های آزمایشی تکمیل شده است.",
        forbidden:"فقط مالک PICM مجاز است.",
        authentication_required:"لطفاً دوباره وارد PICM شوید."
      };
      throw Error(reasons[result.error]||"ثبت سفارش ناموفق بود ("+response.status+").");
    }
    if(!idOk(result.id)||result.state!=="queued")
      throw Error("پاسخ صف تصویر غیرمنتظره است.");
    keep(result.id);
    current=result.id;
    active=false;button.disabled=false;
    await watch(result.id);
    return;
  }catch(error){show("ساخت عکس: "+error.message)}
  finally{active=false;button.disabled=false;sync();}
},true);
const remembered=recall();
if(remembered){
  current=remembered;
  document.getElementById("picm-text-resume")?.removeAttribute("hidden");
}
document.getElementById("picm-text-resume")?.addEventListener("click",()=>{
  const id=recall();
  if(id&&!active)watch(id);
});
window.addEventListener("pagehide",()=>{ending=true;clearOutput()});
sync();
})();