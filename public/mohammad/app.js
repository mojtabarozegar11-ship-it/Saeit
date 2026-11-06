const menuButton=document.querySelector('.menu-toggle');
const nav=document.querySelector('.nav-links');
menuButton?.addEventListener('click',()=>{const open=nav.classList.toggle('open');menuButton.setAttribute('aria-expanded',String(open));menuButton.setAttribute('aria-label',open?'بستن منو':'باز کردن منو')});
nav?.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{nav.classList.remove('open');menuButton?.setAttribute('aria-expanded','false')}));
const form=document.querySelector('#request-form');
const status=document.querySelector('#form-status');
document.querySelectorAll('[data-service]').forEach(a=>a.addEventListener('click',()=>{const select=form?.elements.namedItem('kind');if(select){select.value=a.dataset.service.includes('آموزش')?'محصول دیجیتال یا آموزش':'مشاوره و بررسی آنلاین'}}));
document.querySelectorAll('[data-product]').forEach(a=>a.addEventListener('click',()=>{const select=form?.elements.namedItem('kind');if(select)select.value='استعلام کالای فروشگاه'}));
// The original form downloaded a text file locally and never registered a lead.
// The official same-origin intake owns validation, CSRF and server-side storage.
if(form){
  const nameInput=form.elements.namedItem('name');
  if(nameInput)nameInput.maxLength=120;
  const emailLabel=document.createElement('label');
  emailLabel.textContent='ایمیل معتبر برای دریافت پاسخ ';
  const emailInput=document.createElement('input');
  emailInput.name='email';
  emailInput.type='email';
  emailInput.autocomplete='email';
  emailInput.placeholder='name@example.com';
  emailInput.required=true;
  emailInput.maxLength=250;
  emailLabel.appendChild(emailInput);
  form.querySelector('.form-submit')?.before(emailLabel);
  form.querySelector('.form-submit').textContent='ثبت درخواست در سامانهٔ رسمی';
  const explanation=document.querySelector('#contact .contact-copy > p');
  if(explanation)explanation.textContent='فرم را تکمیل کنید؛ درخواست شما با تأیید خودتان به سامانهٔ رسمی خدمات زمرد ملل ارسال می‌شود.';
  if(status)status.textContent='ثبت درخواست فقط پس از تأیید فرم و دریافت توکن امنیتی سامانه انجام می‌شود. پرداختی در این مرحله دریافت نمی‌شود.';
}
form?.addEventListener('submit',async event=>{
  event.preventDefault();
  const data=new FormData(form);
  const details=[
    'درخواست کلینیک ساختمان محمد',
    `نوع درخواست: ${data.get('kind')}`,
    `شهر: ${data.get('city')||'اعلام نشده'}`,
    `راه تماس تکمیلی: ${data.get('contact')}`,
    `شرح درخواست: ${data.get('details')}`,
  ].join('\n');
  if(details.length>2500){
    status.textContent='توضیحات طولانی است؛ لطفاً درخواست را کوتاه‌تر کنید (حداکثر ۲۵۰۰ نویسه).';
    status.setAttribute('role','alert');
    return;
  }
  const button=form.querySelector('.form-submit');
  button.disabled=true;
  status.textContent='در حال اتصال امن به فرم رسمی ثبت درخواست…';
  status.setAttribute('role','status');
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),12000);
  try{
    const response=await fetch('/ask-master/index.php?service=1',{
      credentials:'same-origin',cache:'no-store',signal:controller.signal,
    });
    if(!response.ok)throw new Error('official_form_unavailable');
    const official=new DOMParser().parseFromString(await response.text(),'text/html')
      .querySelector('form[method="post"][action="/ask-master/index.php"]');
    const csrf=official?.querySelector('input[name="csrf"]')?.value;
    if(!csrf)throw new Error('csrf_missing');
    const submission=document.createElement('form');
    submission.method='post';
    submission.action='/ask-master/index.php';
    submission.acceptCharset='utf-8';
    const fields={csrf,kind:'service_question',name:String(data.get('name')||''),
      email:String(data.get('email')||''),order:'',question:details,website:''};
    Object.entries(fields).forEach(([name,value])=>{
      const input=document.createElement('input');
      input.type='hidden';input.name=name;input.value=value;
      submission.appendChild(input);
    });
    document.body.appendChild(submission);
    submission.submit();
  }catch(error){
    status.textContent='ارتباط با سامانهٔ رسمی برقرار نشد؛ اطلاعات فرم حفظ شده است. دوباره تلاش کنید یا ';
    const fallback=document.createElement('a');
    fallback.href='/ask-master/index.php?service=1';
    fallback.textContent='فرم رسمی درخواست خدمات را باز کنید.';
    status.appendChild(fallback);
    status.setAttribute('role','alert');
    button.disabled=false;
  }finally{
    clearTimeout(timeout);
  }
});
