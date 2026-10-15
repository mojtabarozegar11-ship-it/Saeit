/* PICM private story-shot staging. No false claims of rendered video. */
(()=>{
"use strict";
const form=document.getElementById("renderform");
const mode=document.getElementById("mode");
const prompt=document.getElementById("prompt");
const file=document.getElementById("photo");
const options=document.getElementById("story-options");
const preview=document.getElementById("preview");
const button=document.getElementById("submit");
const status=document.getElementById("status");
const notice=document.getElementById("capability-notice");
const duration=document.getElementById("story-duration");
const ratio=document.getElementById("story-ratio");
const csrf=form?.querySelector("[name=csrfmiddlewaretoken]")?.value;
if(!form||!options||!csrf)return;
let active=false;
let videoPoll=null;
let checkingVideo=false;
const isStory=()=>mode.value==="story_video";
function renderMode(){
 options.hidden=!isStory();
 if(!isStory())return;
 prompt.required=true;
 prompt.minLength=4;
 prompt.maxLength=1500;
 document.querySelector("label[for='prompt']").textContent="داستانی که باید اتفاق بیفتد";
 prompt.placeholder="مثلاً: شخص از خواب بیدار شود، صبحانه بخورد، لباس بپوشد، از خانه خارج شود و به محل کار برود.";
 button.textContent="آماده‌سازی صحنه‌های داستان";
 notice.textContent="این بخش عکس و داستان را خصوصی ثبت و برای تولید کلیپ‌های واقعی به صحنه تقسیم می‌کند. تولید واقعی تصویر متحرکِ روایی، اتصال کلیپ‌ها و فایل نهایی MP4 هنوز موتور GPU و تدوینگر متصل ندارند. فیلم نهایی در این مرحله ساخته نمی‌شود.";
 status.textContent="یک عکس و داستان وارد کنید؛ صحنه‌بندی قابل مشاهده خواهد شد. تولید فیلم هنوز فعال نیست.";
}
document.querySelectorAll("[data-mode]").forEach(btn=>btn.addEventListener("click",()=>{if(!active)renderMode()}));

function watchPrivateMovie(ident, body){
 if(videoPoll!==null){clearInterval(videoPoll);videoPoll=null;}
 if(!/^[a-f0-9]{32}$/.test(ident))return;
 const line=document.createElement("p");
 line.textContent="وضعیت فیلم: در صف انتظار GPU واقعی.";
 body.appendChild(line);
 const check=async()=>{
  if(checkingVideo)return;
  checkingVideo=true;
  try{
   const response=await fetch("/picm/video/status/"+ident+"/",{
    credentials:"same-origin",cache:"no-store"
   });
   if(response.status===404){
    line.textContent="موتور ویدیو هنوز در این نسخه فعال نشده است؛ فعلاً فقط صحنه‌بندی ثبت شده.";
    if(videoPoll!==null){clearInterval(videoPoll);videoPoll=null;}
    return;
   }
   if(!response.ok)throw Error("status-"+response.status);
   const result=await response.json();
   if(result.state==="done"&&/^\/picm\/video\/download\/[a-f0-9]{32}\/$/.test(result.video_url||"")){
    line.textContent="فیلم واقعی آماده است: ";
    const a=document.createElement("a");
    a.href=result.video_url;
    a.textContent="دریافت فایل خصوصی MP4";
    a.rel="nofollow";
    line.appendChild(a);
    status.textContent="فیلم آمادهٔ دانلود در حساب خصوصی است.";
    if(videoPoll!==null){clearInterval(videoPoll);videoPoll=null;}
   }else if(result.state==="uploading"){
    line.textContent="در حال انتقال و بررسی یکپارچگی فیلم تولیدشده…";
   }else if(result.state==="gpu_claimed"){
    line.textContent="پردازش فیلم روی موتور GPU آغاز شده؛ هنوز خروجی نهایی تأیید نشده است.";
   }else if(result.state==="staged_awaiting_gpu"){
    line.textContent="در انتظار فعال‌شدن GPU واقعی؛ صحنه‌بندی به‌معنای تولید فیلم نیست.";
   }else if(result.state==="expired"){
    line.textContent="مهلت دریافت این فیلم تمام شده است.";
    if(videoPoll!==null){clearInterval(videoPoll);videoPoll=null;}
   }else{
    line.textContent="وضعیت پردازش هنوز قابل تأیید نیست.";
   }
  }catch(_error){
   line.textContent="ارتباط دریافت وضعیت موقتاً قطع است؛ صحنه‌بندی ذخیره شده اما فیلم تأیید نشده.";
  }finally{checkingVideo=false;}
 };
 check();
 videoPoll=setInterval(check,20000);
}

function showPlan(result){
 const plan=result.storyboard;
 if(!plan||!Array.isArray(plan.scenes))throw Error("سرور صحنه‌بندی را برنگرداند.");
 const body=document.createElement("div");
 body.style.cssText="text-align:right;width:100%;line-height:2";
 const heading=document.createElement("strong");
 heading.textContent="صحنه‌بندی "+plan.duration+" ثانیه‌ای • "+plan.scenes.length+" کلیپ • "+plan.ratio;
 body.appendChild(heading);
 const list=document.createElement("ol");
 list.style.cssText="padding-inline-start:25px;text-align:right";
 for(const scene of plan.scenes){
  const li=document.createElement("li");
  li.textContent=scene.start+"–"+scene.end+" ثانیه: "+scene.action;
  li.style.marginTop="7px";
  list.appendChild(li);
 }
 body.appendChild(list);
 const p=document.createElement("p");
 p.textContent="وضعیت: طرح خصوصی ثبت شد؛ در انتظار GPU واقعی برای ساخت صحنه‌ها و ترکیب MP4. این پیش‌نمایش، خود ویدیو نیست.";
 p.style.color="#f4ddb1";
 body.appendChild(p);
 preview.replaceChildren(body);
 watchPrivateMovie(result.id,body);
 status.textContent="داستان و عکس خصوصی ثبت شد. "+plan.scenes.length+" صحنه آمادهٔ پردازش هستند؛ تا اتصال موتور واقعی فایل ویدیو تولید نمی‌شود.";
}
form.addEventListener("submit",async event=>{
 if(!isStory())return;
 event.preventDefault();event.stopImmediatePropagation();
 if(active)return;
 if(!file.files?.length){status.textContent="ابتدا عکس را انتخاب کنید.";return}
 if(!prompt.value.trim()||prompt.value.trim().length<4){status.textContent="داستان را در کادر بنویسید.";return}
 active=true;button.disabled=true;
 status.textContent="در حال آماده‌سازی و ثبت خصوصی صحنه‌ها…";
 try{
  const data=new FormData();
  data.append("photo",file.files[0]);
  data.append("mode","story_video");
  data.append("prompt",prompt.value);
  data.append("duration",duration.value);
  data.append("ratio",ratio.value);
  const res=await fetch("/picm/api/reference/",{
   method:"POST",credentials:"same-origin",cache:"no-store",
   headers:{"X-CSRFToken":csrf},body:data
  });
  const result=await res.json();
  if(!res.ok)throw Error(result.error||"خطای ثبت خصوصی: "+res.status);
  showPlan(result);
 }catch(err){status.textContent="آماده‌سازی داستان انجام نشد: "+err.message}
 finally{active=false;button.disabled=false}
},true);
renderMode();
})();