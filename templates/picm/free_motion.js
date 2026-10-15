/* PICM free photo-motion recorder. Runs ONLY in the user's browser.
   A cinematic pan/zoom video is not generative AI video. No external requests. */
(()=>{
"use strict";
const form=document.getElementById("renderform");
const photo=document.getElementById("photo");
const prompt=document.getElementById("prompt");
const mode=document.getElementById("mode");
const button=document.getElementById("submit");
const preview=document.getElementById("preview");
const info=document.getElementById("status");
const controls=document.getElementById("video-options");
const durationSelect=document.getElementById("video-duration");
const ratioSelect=document.getElementById("video-ratio");
const cancel=document.getElementById("video-cancel");
const notice=document.getElementById("capability-notice");
if(!form||!controls||!button||!photo)return;
let busy=false,aborted=false,recording=null,raf=0,downloadUrl=null;
const message=s=>{info.textContent=s};
const compatible=()=>Boolean(window.MediaRecorder&&HTMLCanvasElement.prototype.captureStream);
const videoMode=()=>mode.value==="image_video";
function format(){
 if(!compatible())throw Error("مرورگر شما امکان ضبط ویدیو از عکس را ندارد.");
 const mime=["video/webm;codecs=vp8","video/webm","video/mp4"].find(v=>MediaRecorder.isTypeSupported(v));
 if(!mime)throw Error("مرورگر از فرمت ضبط پشتیبانی نمی‌کند؛ Chrome یا Samsung Internet را امتحان کنید.");
 return mime;
}
function sync(){
 controls.hidden=!videoMode();
 if(videoMode()){
  notice.textContent="ویدیوی متحرک رایگان: عکس شما فقط در همین مرورگر با حرکت سینمایی و متن دلخواه ضبط می‌شود. این روش، ساخت صحنه‌های تازه با مدل مولد هوش مصنوعی نیست و صدا تولید نمی‌کند.";
  button.textContent="ساخت ویدیوی رایگان";
  message(compatible()?"مدت و کادر ویدیو را انتخاب کنید و دکمه ساخت را بزنید.":"این مرورگر قابلیت ضبط ویدیوی محلی را ندارد.");
 }else{
  notice.textContent="ویرایش مولد عکس و افزایش جزئیات واقعی تا 8K هنوز به GPU متصل نیستند. عکس مرجع به‌صورت خصوصی ثبت می‌شود؛ خروجی تولید نمی‌شود.";
  button.textContent="ثبت خصوصی عکس مرجع";
 }
}
document.querySelectorAll("[data-mode]").forEach(el=>el.addEventListener("click",()=>{if(!busy)sync()}));
function decode(blob){
 return new Promise((resolve,reject)=>{
  const url=URL.createObjectURL(blob);
  const img=new Image();
  img.onload=()=>{
   URL.revokeObjectURL(url);
   if(img.naturalWidth<128||img.naturalHeight<128||
      img.naturalWidth>8192||img.naturalHeight>8192||
      img.naturalWidth*img.naturalHeight>24000000){
    reject(Error("ابعاد تصویر برای پردازش محلی مناسب نیست."));return;
   }
   resolve(img);
  };
  img.onerror=()=>{URL.revokeObjectURL(url);reject(Error("عکس قابل بازکردن نیست."))};
  img.src=url;
 });
}
function frame(ctx,image,elapsed,seconds,w,h,overlay){
 const t=Math.min(elapsed/seconds,1);
 const scale=Math.max(w/image.naturalWidth,h/image.naturalHeight)*(1.07+0.13*t);
 const iw=scale*image.naturalWidth,ih=scale*image.naturalHeight;
 const dx=Math.min(0,Math.max(w-iw,(w-iw)/2+Math.sin(t*Math.PI*2)*(iw-w)*.14));
 const dy=Math.min(0,Math.max(h-ih,(h-ih)/2+Math.cos(t*Math.PI*2)*(ih-h)*.14));
 ctx.fillStyle="#0b1020";ctx.fillRect(0,0,w,h);ctx.drawImage(image,dx,dy,iw,ih);
 if(overlay.trim()){
  const fs=Math.floor(w*.040);
  ctx.save();ctx.direction="rtl";ctx.textAlign="center";ctx.textBaseline="middle";
  ctx.font="bold "+fs+"px sans-serif";
  let line=overlay.trim().slice(0,135);
  while(line.length>7&&ctx.measureText(line).width>w*.88)line=line.slice(0,-2);
  if(line.length<overlay.trim().length)line=line.trim()+"…";
  const y=h-fs*2.5;
  ctx.fillStyle="rgba(3,8,22,.67)";ctx.fillRect(0,y-fs*1.3,w,fs*2.6);
  ctx.fillStyle="#fff";ctx.fillText(line,w/2,y,w*.88);ctx.restore();
 }
}
async function makeVideo(){
 const input=photo.files&&photo.files[0];
 if(!input||!["image/jpeg","image/png"].includes(input.type)||input.size>6*1024*1024){
  throw Error("یک تصویر PNG/JPEG تا ۶ مگابایت انتخاب کنید.");
 }
 const secs=Number(durationSelect.value);
 if(![10,30,60].includes(secs))throw Error("مدت زمان انتخابی نامعتبر است.");
 const mime=format(),image=await decode(input);
 const tall=ratioSelect.value==="vertical";
 const w=tall?360:640,h=tall?640:360;
 const canvas=document.createElement("canvas");canvas.width=w;canvas.height=h;
 canvas.style.cssText="width:100%;height:auto;max-height:460px;object-fit:contain";
 const ctx=canvas.getContext("2d",{alpha:false});
 if(!ctx)throw Error("امکان اجرای بوم تصویر وجود ندارد.");
 frame(ctx,image,0,secs,w,h,prompt.value);
 const stream=canvas.captureStream(20);
 let local;
 try{local=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:1400000})}
 catch(e){stream.getTracks().forEach(t=>t.stop());throw Error("رمزگذار ویدیوی دستگاه آماده نیست.");}
 recording=local;
 preview.replaceChildren(canvas);
 cancel.hidden=false;
 const parts=[];
 const finished=new Promise((resolve,reject)=>{
  local.ondataavailable=e=>{if(e.data&&e.data.size)parts.push(e.data)};
  local.onstop=resolve;
  local.onerror=()=>reject(Error("ضبط ویدیو متوقف شد."));
 });
 try{
  local.start(1000);
  const started=performance.now();
  await new Promise(resolve=>{
   const step=now=>{
    const t=Math.min(secs,(now-started)/1000);
    frame(ctx,image,t,secs,w,h,prompt.value);
    message("ضبط ویدیوی رایگان: "+Math.floor(t)+" از "+secs+" ثانیه. صفحه را باز نگه دارید.");
    if(aborted||t>=secs){resolve();return}
    raf=requestAnimationFrame(step);
   };
   raf=requestAnimationFrame(step);
  });
 }finally{
  cancelAnimationFrame(raf);
  if(local.state!=="inactive")local.stop();
  await finished.catch(()=>{});
  stream.getTracks().forEach(t=>t.stop());
  recording=null;
  cancel.hidden=true;
 }
 if(aborted){message("ضبط ویدیو لغو شد.");return}
 if(!parts.length)throw Error("فایل ویدیو در مرورگر تولید نشد.");
 const extension=mime.startsWith("video/mp4")?"mp4":"webm";
 if(downloadUrl)URL.revokeObjectURL(downloadUrl);
 downloadUrl=URL.createObjectURL(new Blob(parts,{type:extension==="mp4"?"video/mp4":"video/webm"}));
 const video=document.createElement("video");video.src=downloadUrl;
 video.controls=true;video.playsInline=true;video.style.width="100%";
 const link=document.createElement("a");link.href=downloadUrl;
 link.download="picm-free-motion-"+secs+"s."+extension;
 link.textContent="دریافت ویدیوی "+secs+" ثانیه‌ای ("+extension.toUpperCase()+")";
 link.style.cssText="display:block;color:#ced6ff;padding:12px;font-weight:bold;text-decoration:underline";
 preview.replaceChildren(video,link);
 message("ویدیوی متحرک "+secs+" ثانیه‌ای آماده شد. برای ذخیره، روی لینک دریافت بزنید.");
}
cancel.addEventListener("click",()=>{aborted=true;message("در حال لغو ضبط...")});
form.addEventListener("submit",async e=>{
 if(!videoMode())return;
 e.preventDefault();
 e.stopImmediatePropagation();
 if(busy)return;
 busy=true;aborted=false;button.disabled=true;
 document.querySelectorAll("[data-mode]").forEach(el=>{el.disabled=true});
 try{await makeVideo()}
 catch(err){message("ساخت ویدیو انجام نشد: "+err.message)}
 finally{
  busy=false;button.disabled=false;
  document.querySelectorAll("[data-mode]").forEach(el=>{el.disabled=false});
 }
},true);
window.addEventListener("pagehide",()=>{
 aborted=true;
 if(recording&&recording.state==="recording"){try{recording.stop()}catch(e){}}
 if(downloadUrl)URL.revokeObjectURL(downloadUrl);
});
sync();
})();
