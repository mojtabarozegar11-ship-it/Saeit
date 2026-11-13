/* Zomorod Mellal VISION 3 — homepage interaction corrections, 2026-11-13.
   Scoped to the page, no third-party scripts, no requests or user-data submission. */
(()=>{'use strict';
 const $=(selector,root=document)=>root.querySelector(selector);
 const $$=(selector,root=document)=>Array.from(root.querySelectorAll(selector));
 const searchButton=$('.search-toggle');
 const searchBox=$('#search-wrap');
 const searchForm=$('.search-form');
 const searchInput=$('#site-search');
 const feedback=$('#search-feedback');
 const mobileButton=$('.mobile-menu-btn');
 const mobileNav=$('#mobile-nav');
 const toast=$('#toast');
 const toggle=(button,region,open)=>{
   if(!button||!region)return;
   region.hidden=!open;
   button.setAttribute('aria-expanded',String(open));
 };
 searchButton?.addEventListener('click',()=>{
   const open=searchBox.hidden;
   toggle(searchButton,searchBox,open);
   if(open)searchInput?.focus();
 });
 mobileButton?.addEventListener('click',()=>toggle(mobileButton,mobileNav,mobileNav.hidden));
 $$('.mobile-nav a').forEach(a=>a.addEventListener('click',()=>toggle(mobileButton,mobileNav,false)));
 const normalize=s=>String(s||'').normalize('NFKC').replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\u200f]/g,' ').replace(/\s+/g,' ').trim().toLocaleLowerCase('fa-IR');
 // A genuine in-page finder: do not promise a full-site search index.
 searchForm?.addEventListener('submit',event=>{
   event.preventDefault();
   const term=normalize(searchInput?.value);
   if(!feedback)return;
   if(!term){feedback.textContent='موضوع موردنظر را وارد کنید.';searchInput?.focus();return;}
   const candidates=$$('main a[href],.metric-rail a[href],.side-dock a[href]');
   const matching=candidates.find(a=>normalize(a.textContent+' '+(a.getAttribute('data-search')||'')+' '+(a.getAttribute('aria-label')||'')+' '+(a.getAttribute('title')||'')).includes(term));
   if(!matching){
     feedback.textContent='در همین صفحه نتیجه‌ای پیدا نشد. برای موضوعات بیشتر به دانشنامه یا بخش خدمات مراجعه کنید.';
     return;
   }
   const label=matching.textContent.trim().replace(/\s+/g,' ').slice(0,75)||matching.getAttribute('aria-label')||matching.getAttribute('title')||'بخش مرتبط';
   feedback.textContent='بخش مرتبط پیدا شد: '+label;
   const scroller=matching.closest('.card-strip');
   if(scroller)scroller.scrollTo({left:matching.offsetLeft*-1,behavior:'smooth'});
   matching.scrollIntoView({block:'center',behavior:'smooth',inline:'nearest'});
   matching.classList.add('search-found');
   const previousTabIndex=matching.getAttribute('tabindex');
   if(previousTabIndex===null)matching.setAttribute('tabindex','-1');
   matching.focus({preventScroll:true});
   window.setTimeout(()=>{
     matching.classList.remove('search-found');
     if(previousTabIndex===null)matching.removeAttribute('tabindex');
   },2400);
 });
 // Chromium/Firefox/WebKit standard RTL scrollLeft is 0 at the right edge and
 // becomes negative as the user moves visually left. Positive "next" clamped.
 const sliders=new Map();
 $$('[data-strip]').forEach(button=>{
   const strip=document.getElementById(button.dataset.strip);
   if(!strip)return;
   sliders.set(button.dataset.strip,strip);
   button.setAttribute('aria-controls',strip.id);
   button.addEventListener('click',()=>{
     if(button.disabled)return;
     const amount=Math.max(130,Math.round(strip.clientWidth*.68));
     const delta=button.dataset.direction==='next'?-amount:amount;
     strip.scrollBy({left:delta,behavior:'smooth'});
     window.setTimeout(()=>updateButtons(strip),280);
   });
 });
 const updateButtons=strip=>{
   const overflow=strip.scrollWidth>strip.clientWidth+2;
   const max=Math.max(0,strip.scrollWidth-strip.clientWidth);
   const rtl=getComputedStyle(strip).direction==='rtl';
   // RTL negative model is used by current target browsers.
   const position=rtl?-strip.scrollLeft:strip.scrollLeft;
   $$('[data-strip="'+strip.id+'"]').forEach(button=>{
     const next=button.dataset.direction==='next';
     button.disabled=!overflow||(next?position>=max-2:position<=2);
     button.setAttribute('aria-disabled',String(button.disabled));
   });
 };
 for(const strip of sliders.values()){
   strip.addEventListener('scroll',()=>updateButtons(strip),{passive:true});
   updateButtons(strip);
 }
 window.addEventListener('resize',()=>{for(const strip of sliders.values())updateButtons(strip)},{passive:true});
 // EN / AR provide contact-language guidance. They do not switch the document
 // language or select a nonexistent translation.
 const notices={
   fa:'زبان این صفحه فارسی است.',
   en:'This page is in Persian. For English enquiries, please use the Contact page.',
   ar:'هذه الصفحة بالفارسية. للاستفسارات بالعربية يرجى استخدام صفحة التواصل.'
 };
 const notify=message=>{
   if(!toast)return;
   toast.hidden=false;
   toast.setAttribute('role','status');
   toast.textContent=message;
   toast.setAttribute('tabindex','-1');
   toast.focus({preventScroll:true});
 };
 $$('.lang-switch button').forEach(button=>{
   button.setAttribute('aria-pressed',String(button.dataset.lang==='fa'));
   button.addEventListener('click',()=>{
     $$('.lang-switch button').forEach(other=>{
       const selected=other.dataset.lang==='fa';
       other.classList.toggle('active',selected);
       other.setAttribute('aria-pressed',String(selected));
     });
     notify(notices[button.dataset.lang]||notices.fa);
   });
 });
 toast?.addEventListener('click',()=>{toast.hidden=true;});
 document.addEventListener('keydown',e=>{
   if(e.key!=='Escape')return;
   if(searchBox&&!searchBox.hidden){toggle(searchButton,searchBox,false);searchButton?.focus();}
   if(mobileNav&&!mobileNav.hidden){toggle(mobileButton,mobileNav,false);mobileButton?.focus();}
   if(toast)toast.hidden=true;
 });
})();
