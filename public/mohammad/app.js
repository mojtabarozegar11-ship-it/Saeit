const menuButton=document.querySelector('.menu-toggle');
const nav=document.querySelector('.nav-links');
menuButton?.addEventListener('click',()=>{const open=nav.classList.toggle('open');menuButton.setAttribute('aria-expanded',String(open));menuButton.setAttribute('aria-label',open?'بستن منو':'باز کردن منو')});
nav?.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{nav.classList.remove('open');menuButton?.setAttribute('aria-expanded','false')}));
const form=document.querySelector('#request-form');
const status=document.querySelector('#form-status');
document.querySelectorAll('[data-service]').forEach(a=>a.addEventListener('click',()=>{const select=form?.elements.namedItem('kind');if(select){select.value=a.dataset.service.includes('آموزش')?'محصول دیجیتال یا آموزش':'مشاوره و بررسی آنلاین'}}));
document.querySelectorAll('[data-product]').forEach(a=>a.addEventListener('click',()=>{const select=form?.elements.namedItem('kind');if(select)select.value='استعلام کالای فروشگاه'}));
form?.addEventListener('submit',event=>{
  event.preventDefault();
  const data=new FormData(form);
  const lines=['درخواست کلینیک ساختمان محمد','------------------------------',`نام: ${data.get('name')}`,`راه تماس: ${data.get('contact')}`,`نوع درخواست: ${data.get('kind')}`,`شهر: ${data.get('city')||'اعلام نشده'}`,'',`شرح درخواست: ${data.get('details')}`,'','این درخواست در وب‌سایت ذخیره یا ارسال نشده است.'];
  const blob=new Blob(['\ufeff'+lines.join('\n')],{type:'text/plain;charset=utf-8'});
  const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='darkhast-clinic-sakhteman.txt';link.click();URL.revokeObjectURL(link.href);
  status.textContent='فایل درخواست ساخته شد. آن را ذخیره و از راه تماس دلخواه برای کلینیک بفرستید.';
  status.setAttribute('role','status');
});
