/* Zomorod Mellal: three actual continuous RTL rows, native site-wide search,
 * accessible navigation and reduced-motion support. No remote dependencies. */
(()=>{'use strict';
 const $=(selector,root=document)=>root.querySelector(selector);
 const $$=(selector,root=document)=>Array.from(root.querySelectorAll(selector));
 const searchButton=$('.search-toggle'),searchBox=$('#search-wrap'),searchInput=$('#site-search');
 const mobileButton=$('.mobile-menu-btn'),mobileNav=$('#mobile-nav');
 function toggle(button,region,open){
   if(!button||!region)return;
   region.hidden=!open;
   button.setAttribute('aria-expanded',String(open));
 }
 searchButton?.addEventListener('click',()=>{
   const open=searchBox.hidden;
   toggle(searchButton,searchBox,open);
   if(open)searchInput?.focus();
 });
 mobileButton?.addEventListener('click',()=>toggle(mobileButton,mobileNav,mobileNav.hidden));
 $$('.mobile-nav a').forEach(a=>a.addEventListener('click',()=>toggle(mobileButton,mobileNav,false)));
 document.addEventListener('keydown',e=>{
   if(e.key!=='Escape')return;
   if(searchBox&&!searchBox.hidden){toggle(searchButton,searchBox,false);searchButton?.focus();}
   if(mobileNav&&!mobileNav.hidden){toggle(mobileButton,mobileNav,false);mobileButton?.focus();}
 });
 // The form is a genuine GET request to the existing site's /search/?q= backend.
 // JavaScript is deliberately not required to submit or display search results.
 const motionPreference=window.matchMedia('(prefers-reduced-motion: reduce)');
 const strips=$$('[data-auto-strip]');
 const rotators=[];
 for(const strip of strips){
   const originals=Array.from(strip.children).filter(x=>x.matches('a[href]'));
   if(originals.length<2)continue;
   const originalCount=originals.length;
   const periodOnce=()=>{
     const gap=parseFloat(getComputedStyle(strip).columnGap)||0;
     return originals.reduce((sum,el)=>sum+el.getBoundingClientRect().width+gap,0);
   };
   const addCopies=()=>{
     for(const original of originals){
       const duplicate=original.cloneNode(true);
       duplicate.setAttribute('aria-hidden','true');
       // Duplicates are removed from keyboard/tab order but remain mouse-clickable.
       duplicate.tabIndex=-1;
       duplicate.classList.add('carousel-copy');
       for(const image of $$('img',duplicate)){image.alt='';image.loading='lazy';}
       strip.appendChild(duplicate);
     }
   };
   const period=periodOnce();
   if(!(period>50))continue;
   let rounds=0;
   // All viewports must see an exact repeating pattern without an empty tail.
   do{addCopies();rounds++;}
   while(strip.scrollWidth<period+strip.clientWidth+30&&rounds<12);
   const speed=Math.max(12,Math.min(48,Number(strip.dataset.speed)||25));
   const control=$('[data-rotator-toggle="'+strip.id+'"]');
   const state={strip,period,speed,control,paused:motionPreference.matches,
                hovered:false,focused:false,visible:false,delayUntil:0};
   strip.setAttribute('aria-live','off');
   const update=()=>{
     if(!control)return;
     const running=!state.paused;
     control.setAttribute('aria-pressed',String(running));
     control.textContent=running?'⏸':'▶';
     control.setAttribute('aria-label',(running?'توقف':'شروع')+' حرکت ردیف '+
       (strip.id==='services-strip'?'خدمات':strip.id==='products-strip'?'محصولات':'حوزه‌های توسعه'));
   };
   update();
   control?.addEventListener('click',()=>{state.paused=!state.paused;state.delayUntil=0;update();});
   strip.addEventListener('mouseenter',()=>{state.hovered=true;});
   strip.addEventListener('mouseleave',()=>{state.hovered=false;});
   strip.addEventListener('focusin',()=>{state.focused=true;});
   strip.addEventListener('focusout',()=>{state.focused=strip.contains(document.activeElement);});
   strip.addEventListener('pointerdown',()=>{state.delayUntil=performance.now()+7000;},{passive:true});
   strip.addEventListener('wheel',()=>{state.delayUntil=performance.now()+7000;},{passive:true});
   const manualButtons=$$('[data-strip="'+strip.id+'"]');
   for(const button of manualButtons){
     button.disabled=false;
     button.removeAttribute('aria-disabled');
     button.setAttribute('aria-controls',strip.id);
     button.addEventListener('click',()=>{
       state.delayUntil=performance.now()+6500;
       const amount=Math.max(135,Math.round(strip.clientWidth*.65));
       const next=button.dataset.direction==='next';
       // RTL negative scrollLeft; prewrap the previous direction at the origin.
       if(!next&&strip.scrollLeft>-2)strip.scrollLeft=-state.period;
       if(next&&strip.scrollLeft<=-state.period+2)strip.scrollLeft=0;
       strip.scrollBy({left:next?-amount:amount,behavior:'smooth'});
     });
   }
   rotators.push(state);
 }
 if('IntersectionObserver' in window){
   const observer=new IntersectionObserver(entries=>{
     for(const entry of entries){
       const state=rotators.find(x=>x.strip===entry.target);
       if(state)state.visible=entry.isIntersecting;
     }
   },{threshold:0.02,rootMargin:'100px 0px'});
   rotators.forEach(x=>observer.observe(x.strip));
 }else rotators.forEach(x=>x.visible=true);
 let previous=0;
 const tick=now=>{
   if(!previous){previous=now;requestAnimationFrame(tick);return;}
   const elapsed=Math.min(now-previous,100);
   if(now-previous<25){requestAnimationFrame(tick);return;}
   previous=now;
   for(const state of rotators){
     if(state.paused||state.hovered||state.focused||!state.visible||
        document.hidden||now<state.delayUntil)continue;
     const s=state.strip;
     s.scrollLeft-=state.speed*elapsed/1000;
     if(s.scrollLeft<=-state.period)s.scrollLeft+=state.period;
   }
   requestAnimationFrame(tick);
 };
 if(rotators.length)requestAnimationFrame(tick);
 document.documentElement.dataset.rotatingRows=String(rotators.length);
})();