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
 const strips=Array.from(document.querySelectorAll('[data-auto-strip], [data-field-carousel]'));
 const rotators=[];
 // Touchscreens cannot safely use sticky mouse hover or persistent tap focus as pause signals.
 const trueHover=window.matchMedia('(hover: hover) and (pointer: fine)');
 let keyboardFocus=false;
 document.addEventListener('keydown',()=>{keyboardFocus=true;});
 document.addEventListener('pointerdown',()=>{keyboardFocus=false;},{passive:true});
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
       // aria-hidden alone does not remove nested interactive controls from tab order.
       for(const nested of Array.from(duplicate.querySelectorAll('a[href],button,input,select,textarea,[tabindex]'))){
         nested.tabIndex=-1;
       }
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
                hovered:false,focused:false,visible:false,delayUntil:0,position:strip.scrollLeft};
   strip.setAttribute('aria-live','off');
   const update=()=>{
     if(!control)return;
     const running=!state.paused;
     control.setAttribute('aria-pressed',String(running));
     control.textContent=running?'⏸':'▶';
     control.setAttribute('aria-label',(running?'توقف':'شروع')+' حرکت ردیف '+
       (strip.id==='services-strip'?'خدمات':strip.id==='products-strip'?'محصولات':strip.id==='fields-carousel'?'تصاویر حوزه‌های اصلی':'حوزه‌های توسعه'));
   };
   update();
   control?.addEventListener('click',()=>{
     // Never re-enable autoplay while the OS requests reduced motion.
     state.paused=motionPreference.matches?true:!state.paused;
     state.delayUntil=0;update();
   });
   const onMotionChange=event=>{
     if(event.matches){
       state.paused=true;state.delayUntil=0;
       // Cancel any in-flight smooth manual scroll immediately.
       strip.scrollTo({left:strip.scrollLeft,behavior:'instant'});
       state.position=strip.scrollLeft;
       update();
     }
   };
   if(typeof motionPreference.addEventListener==='function')motionPreference.addEventListener('change',onMotionChange);
   else if(typeof motionPreference.addListener==='function')motionPreference.addListener(onMotionChange);
   strip.addEventListener('mouseenter',()=>{state.hovered=trueHover.matches;});
   strip.addEventListener('mouseleave',()=>{state.hovered=false;});
   // Pause for every focus source (keyboard, assistive technology or script), not only keyboard heuristics.
   strip.addEventListener('focusin',()=>{state.focused=true;});
   // relatedTarget is the next focus destination; activeElement may still be stale during focusout.
   strip.addEventListener('focusout',event=>{state.focused=Boolean(event.relatedTarget&&strip.contains(event.relatedTarget));});
   strip.addEventListener('pointerdown',()=>{state.delayUntil=performance.now()+7000;},{passive:true});
   strip.addEventListener('wheel',()=>{state.delayUntil=performance.now()+7000;},{passive:true});
   // Keyboard-accessible manual navigation, including the photo rail without arrow buttons.
   // Arrow keys act only while the rail itself is focused; child links keep normal behavior.
   strip.addEventListener('keydown',event=>{
     if(event.target!==strip||!['ArrowLeft','ArrowRight'].includes(event.key))return;
     event.preventDefault();
     state.delayUntil=performance.now()+6500;
     const amount=Math.max(135,Math.round(strip.clientWidth*.65));
     const next=event.key==='ArrowLeft'; // RTL: visual forward is left.
     if(!next&&strip.scrollLeft>-2)strip.scrollLeft=-state.period;
     if(next&&strip.scrollLeft<=-state.period+2)strip.scrollLeft=0;
     strip.scrollBy({left:next?-amount:amount,
       behavior:motionPreference.matches?'instant':'smooth'});
     state.position=strip.scrollLeft;
   });
   const manualButtons=Array.from(document.querySelectorAll('[data-strip="'+strip.id+'"]'));
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
       strip.scrollBy({left:next?-amount:amount,behavior:motionPreference.matches?'instant':'smooth'});
       state.position=strip.scrollLeft;
     });
   }
   // Recalculate the repeating span after viewport/font/layout changes.
   // A stale span can make the rail jump or expose an empty seam on mobile rotation.
   const refreshPeriod=()=>{
     const measured=periodOnce();
     if(!(measured>50))return;
     const oldPeriod=state.period;
     if(Math.abs(measured-oldPeriod)<1)return;
     const phase=oldPeriod>0?((Math.abs(strip.scrollLeft)%oldPeriod)/oldPeriod):0;
     state.period=measured;
     strip.scrollLeft=-phase*measured;
     state.position=strip.scrollLeft;
     state.delayUntil=performance.now()+400;
   };
   if('ResizeObserver' in window){
     const resizeObserver=new ResizeObserver(refreshPeriod);
     resizeObserver.observe(strip);
     originals.forEach(item=>resizeObserver.observe(item));
   }else window.addEventListener('resize',refreshPeriod,{passive:true});
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
 // An explicit timer also runs in headless WebKit, which can suspend
 // requestAnimationFrame despite the tab being foreground and visible.
 let previous=performance.now(),tickCount=0;
 const tick=()=>{
   const now=performance.now();
   const elapsed=Math.min(Math.max(0,now-previous),100);
   if(elapsed<15)return;
   previous=now;tickCount++;
   for(const state of rotators){
     if(state.paused||state.hovered||state.focused||!state.visible||
        document.hidden||now<state.delayUntil)continue;
     const s=state.strip;
     // Maintain subpixel position independently: WebKit can round scrollLeft
     // to whole pixels, which would otherwise discard every small 30fps step.
     let logical=state.position;
     if(Math.abs(logical-s.scrollLeft)>3)logical=s.scrollLeft;
     logical-=state.speed*elapsed/1000;
     if(logical<=-state.period)logical+=state.period;
     state.position=logical;
     s.scrollLeft=logical;
   }
 };
 if(rotators.length)window.setInterval(tick,40);
 // Preserve the existing 3-rail release contract; expose the new photo rail independently.
 document.documentElement.dataset.rotatingRows=String(rotators.filter(x=>x.strip.hasAttribute('data-auto-strip')).length);
 document.documentElement.dataset.fieldCarouselReady=rotators.some(x=>x.strip.id==='fields-carousel')?'1':'0';
 window.__zmRotatorDiagnostics=()=>rotators.map(x=>({id:x.strip.id,paused:x.paused,hovered:x.hovered,focused:x.focused,visible:x.visible,documentHidden:document.hidden,tickCount,subpixelPosition:x.position,scrollLeft:x.strip.scrollLeft}));
})();