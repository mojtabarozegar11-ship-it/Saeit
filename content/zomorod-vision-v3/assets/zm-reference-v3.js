/* Zomorod Mellal VISION 3: homepage-only progressive enhancements, no external APIs. */
(()=>{'use strict';
  const q=(s,root=document)=>root.querySelector(s),qa=(s,root=document)=>[...root.querySelectorAll(s)];
  const toggle=q('.search-toggle'),form=q('.search-form'),box=q('#search-wrap'),feedback=q('#search-feedback');
  const setOpen=(button,region,open)=>{region.hidden=!open;button.setAttribute('aria-expanded',String(open));};
  toggle?.addEventListener('click',()=>{const open=box.hidden;setOpen(toggle,box,open);if(open)q('#site-search')?.focus();});
  const mobile=q('.mobile-menu-btn'),mobileNav=q('#mobile-nav');
  mobile?.addEventListener('click',()=>setOpen(mobile,mobileNav,mobileNav.hidden));
  qa('.mobile-nav a').forEach(a=>a.addEventListener('click',()=>setOpen(mobile,mobileNav,false)));
  const notify=(message)=>{const t=q('#toast');if(!t)return;t.hidden=false;t.textContent=message;t.onclick=()=>{t.hidden=true;};};
  form?.addEventListener('submit',e=>{e.preventDefault();const term=(q('#site-search').value||'').trim().toLocaleLowerCase('fa-IR');if(!term){feedback.textContent='نام حوزه موردنظر را وارد کنید.';return;}const targets=qa('a[href]:not(.skip-link)');const matched=targets.find(a=>(a.textContent+' '+(a.getAttribute('data-search')||'')).toLocaleLowerCase('fa-IR').includes(term));if(matched){feedback.textContent='مورد مرتبط پیدا شد: '+matched.textContent.trim().slice(0,70);matched.scrollIntoView({behavior:'smooth',block:'center'});matched.classList.add('search-found');setTimeout(()=>matched.classList.remove('search-found'),2000);}else{feedback.textContent='در این صفحه موردی یافت نشد. بخش خدمات و دانشنامه را بررسی کنید.';}});
  qa('[data-strip]').forEach(btn=>btn.addEventListener('click',()=>{const el=document.getElementById(btn.dataset.strip);if(!el)return;const direction=btn.dataset.direction==='prev'?-1:1;const amount=Math.max(140,Math.round(el.clientWidth*.73));el.scrollBy({left:direction*amount,behavior:'smooth'});}));
  // Language controls are real, but don't pretend that untranslated internal pages are localized.
  const languages={fa:'زبان فارسی فعال است. محتوای انگلیسی و عربی سایت در صفحات داخلی به‌صورت مستقل ارائه می‌شود.',en:'This homepage is currently provided in Persian. For English-language enquiries, use the contact page.',ar:'هذه الصفحة متاحة حالياً بالفارسية. للاستفسارات بالعربية، يرجى استخدام صفحة التواصل.'};
  qa('.lang-switch button').forEach(b=>b.addEventListener('click',()=>{qa('.lang-switch button').forEach(x=>x.classList.toggle('active',x===b));notify(languages[b.dataset.lang]||languages.fa);if(b.dataset.lang!=='fa'){q('.contact-mini')?.focus();}}));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(!box.hidden)setOpen(toggle,box,false);if(!mobileNav.hidden)setOpen(mobile,mobileNav,false);const t=q('#toast');if(t)t.hidden=true;}});
})();