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
const photoControls=document.getElementById("photo-options");
const durationSelect=document.getElementById("video-duration");
const ratioSelect=document.getElementById("video-ratio");
const cancel=document.getElementById("video-cancel");
const notice=document.getElementById("capability-notice");
if(!form||!controls||!button||!photo)return;
let busy=false,aborted=false,recording=null,raf=0,downloadUrl=null;
const message=s=>{info.textContent=s};
const compatible=()=>Boolean(window.MediaRecorder&&HTMLCanvasElement.prototype.captureStream);
const videoMode=()=>mode.value==="image_video";
const imageMode=()=>mode.value==="image_edit";
function format(){
 if(!compatible())throw Error("مرورگر شما امکان ضبط ویدیو از عکس را ندارد.");
 const mime=["video/webm;codecs=vp8","video/webm","video/mp4"].find(v=>MediaRecorder.isTypeSupported(v));
 if(!mime)throw Error("مرورگر از فرمت ضبط پشتیبانی نمی‌کند؛ Chrome یا Samsung Internet را امتحان کنید.");
 return mime;
}
function sync(){
 controls.hidden=!videoMode();
 photoControls.hidden=!imageMode();
 const promptLabel=document.querySelector('label[for="prompt"]');
 if(imageMode()){
  prompt.required=false;
  promptLabel.textContent="یادداشت اختیاری؛ در ویرایش دستی تفسیر نمی‌شود";
 }else if(videoMode()){
  // Photo alone is sufficient; overlay caption is always optional.
  prompt.required=false;
  prompt.minLength=0;
  promptLabel.textContent="متن اختیاری روی ویدیو";
 }
 if(videoMode()){
  notice.textContent="ویدیوی متحرک رایگان: عکس شما فقط در همین مرورگر با حرکت سینمایی و متن دلخواه ضبط می‌شود. این روش، ساخت صحنه‌های تازه با مدل مولد هوش مصنوعی نیست و صدا تولید نمی‌کند.";
  button.textContent="ساخت ویدیوی رایگان";
  message(compatible()?"مدت و کادر ویدیو را انتخاب کنید و دکمه ساخت را بزنید.":"این مرورگر قابلیت ضبط ویدیوی محلی را ندارد.");
 }else if(imageMode()){
  notice.textContent="ویرایش رایگان عکس با روشنایی، کنتراست و تنظیم رنگ در مرورگر انجام می‌شود. این پردازش مولد هوش مصنوعی نیست و سوژهٔ جدید ایجاد نمی‌کند.";
  button.textContent="بهبود رایگان عکس و دریافت خروجی";
 }else{
  notice.textContent="افزایش جزئیات واقعی تا 8K هنوز موتور GPU ندارد. عکس مرجع فقط به‌صورت خصوصی ثبت می‌شود؛ خروجی آماده نمی‌شود.";
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
 const streamTrack=stream.getVideoTracks()[0];
 if(!streamTrack || streamTrack.readyState!=="live"){
  stream.getTracks().forEach(t=>t.stop());
  throw Error("مرورگر هیچ مسیر ضبط زنده‌ای از تصویر ایجاد نکرد.");
 }
 let local;
 try{local=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:1400000})}
 catch(e){stream.getTracks().forEach(t=>t.stop());throw Error("رمزگذار ویدیوی دستگاه آماده نیست.");}
 recording=local;
 preview.replaceChildren(canvas);
 cancel.hidden=false;
 const parts=[];
 let stopReceived=false;
 let encodingError="";
 const finished=new Promise(resolve=>{
  local.ondataavailable=e=>{if(e.data&&e.data.size>0)parts.push(e.data)};
  local.onstop=()=>{stopReceived=true;resolve()};
  local.onerror=e=>{encodingError=e.error?.name||"video_encoder_error";resolve()};
 });
 let startedRecording=false,heartbeat=null;
 try{
  local.start(1500);
  startedRecording=true;
  // Some Android WebViews do not reliably emit periodic dataavailable.
  // Force explicit chunks while the encoder is recording, without polling any server.
  heartbeat=setInterval(()=>{
   try{if(local.state==="recording")local.requestData()}catch(e){}
  },4500);
  const started=performance.now();
  await new Promise(resolve=>{
   const step=now=>{
    const t=Math.min(secs,(now-started)/1000);
    frame(ctx,image,t,secs,w,h,prompt.value);
    try{if(typeof streamTrack.requestFrame==="function")streamTrack.requestFrame()}catch(e){}
    message("در حال ضبط فایل ویدیو: "+Math.floor(t)+" از "+secs+" ثانیه. پس از پایان، فایل و دکمهٔ دانلود نمایش داده می‌شود.");
    if(aborted||t>=secs){resolve();return}
    raf=requestAnimationFrame(step);
   };
   raf=requestAnimationFrame(step);
  });
 }finally{
  cancelAnimationFrame(raf);
  if(heartbeat!==null)clearInterval(heartbeat);
  if(startedRecording&&local.state!=="inactive"){
   try{local.requestData()}catch(e){}
   try{local.stop()}catch(e){encodingError=e.name||"stop_failed"}
  }
  // Never hang forever on mobile when the final onstop event is missing.
  // The timeout is ONLY for collecting an encoder that has already stopped;
  // existing valid video chunks are still retained.
  if(startedRecording)await Promise.race([
   finished,
   new Promise(resolve=>setTimeout(resolve,7000))
  ]);
  stream.getTracks().forEach(t=>t.stop());
  recording=null;
  cancel.hidden=true;
 }
 if(aborted){message("ضبط ویدیو لغو شد.");return}
 if(!parts.length)throw Error("مرورگر عکس را متحرک کرد ولی فایل ضبط را تحویل نداد. کد خطا: "+(encodingError||"no_video_chunks")+". لطفاً از مرورگر Chrome اصلی باز کنید، نه مرورگر داخل برنامه‌ها.");
 const extension=mime.startsWith("video/mp4")?"mp4":"webm";
 const resultBlob=new Blob(parts,{type:extension==="mp4"?"video/mp4":"video/webm"});
 if(resultBlob.size<1024)throw Error("خروجی ضبط بسیار کوچک است ("+resultBlob.size+" بایت). کد: "+(encodingError||"empty_encoder")+". برای امتحان از Chrome استفاده کنید.");
 const header=new Uint8Array(await resultBlob.slice(0,16).arrayBuffer());
 const isMp4=header.length>=12&&String.fromCharCode(...header.slice(4,8))==="ftyp";
 const isWebM=header.length>=4&&header[0]===0x1a&&header[1]===0x45&&header[2]===0xdf&&header[3]===0xa3;
 if(!(extension==="mp4"?isMp4:isWebM))throw Error("مرورگر خروجی نامعتبر ضبط کرده است ("+extension+"). از Chrome اصلی استفاده کنید.");
 if(downloadUrl)URL.revokeObjectURL(downloadUrl);
 downloadUrl=URL.createObjectURL(resultBlob);
 const video=document.createElement("video");video.src=downloadUrl;
 video.controls=true;video.playsInline=true;video.style.width="100%";
 const link=document.createElement("a");link.href=downloadUrl;
 link.download="picm-free-motion-"+secs+"s."+extension;
 link.textContent="دریافت ویدیوی "+secs+" ثانیه‌ای ("+extension.toUpperCase()+")";
 link.style.cssText="display:block;color:#ced6ff;padding:12px;font-weight:bold;text-decoration:underline";
 preview.replaceChildren(video,link);
 const sizeMB=(resultBlob.size/1048576).toFixed(2);
 message("فایل ویدیویی واقعی ضبط شد: "+sizeMB+" MB، فرمت "+extension.toUpperCase()+"؛ روی «دریافت ویدیو» زیر پیش‌نمایش بزنید.");
 if(!stopReceived)message("فایل ویدیویی ضبط شد ("+sizeMB+" MB)، اما مرورگر پایان ضبط را کامل اعلام نکرد. دکمهٔ دانلود را امتحان کنید.");
}
async function enhanceFreeImage(){
 const input=photo.files&&photo.files[0];
 if(!input||!["image/jpeg","image/png"].includes(input.type)||input.size>6*1024*1024){
  throw Error("یک تصویر PNG/JPEG تا ۶ مگابایت انتخاب کنید.");
 }
 const img=await decode(input);
 const scale=Math.min(1,2048/Math.max(img.naturalWidth,img.naturalHeight));
 const canvas=document.createElement("canvas");
 canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));
 canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
 const ctx=canvas.getContext("2d",{alpha:false});
 if(!ctx)throw Error("امکان ویرایش روی مرورگر وجود ندارد.");
 const bright=Number(document.getElementById("photo-brightness").value);
 const contrast=Number(document.getElementById("photo-contrast").value);
 const saturation=Number(document.getElementById("photo-saturation").value);
 if(![bright,contrast,saturation].every(Number.isFinite))throw Error("مقادیر تنظیم عکس نامعتبر هستند.");
 ctx.filter="brightness("+bright+"%) contrast("+contrast+"%) saturate("+saturation+"%)";
 ctx.drawImage(img,0,0,canvas.width,canvas.height);
 const result=await new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error("خروجی عکس ساخته نشد.")),"image/jpeg",.94));
 if(downloadUrl)URL.revokeObjectURL(downloadUrl);
 downloadUrl=URL.createObjectURL(result);
 const image=document.createElement("img");image.src=downloadUrl;image.alt="عکس ویرایش‌شده";
 image.style.width="100%";image.style.maxHeight="460px";image.style.objectFit="contain";
 const link=document.createElement("a");link.href=downloadUrl;link.download="picm-free-enhanced.jpg";
 link.textContent="دریافت عکس اصلاح‌شده (JPEG)";
 link.style.cssText="display:block;color:#ced6ff;padding:12px;font-weight:bold;text-decoration:underline";
 preview.replaceChildren(image,link);
 message("ویرایش رایگان تصویر انجام شد. خروجی: "+canvas.width+" × "+canvas.height+" پیکسل؛ بدون تماس با سرور.");
}
cancel.addEventListener("click",()=>{aborted=true;message("در حال لغو ضبط...")});
form.addEventListener("submit",async e=>{
 if(!videoMode()&&!imageMode())return;
 e.preventDefault();
 e.stopImmediatePropagation();
 if(busy)return;
 busy=true;aborted=false;button.disabled=true;
 document.querySelectorAll("[data-mode]").forEach(el=>{el.disabled=true});
 try{
  if(videoMode())await makeVideo();
  else await enhanceFreeImage();
 }
 catch(err){message("ساخت فایل انجام نشد: "+err.message)}
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
