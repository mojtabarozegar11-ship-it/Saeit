import hashlib, hmac, io, json, os, re, secrets, time
from pathlib import Path
from functools import wraps
from django.conf import settings
from django.http import FileResponse,HttpResponse,JsonResponse,Http404
from django.shortcuts import render,redirect
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from django.views.decorators.cache import never_cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .core import Store,Rejected
from .gateway import Zarinpal,GatewayError
from .config import ROOT,TERMS_VERSION,price,readiness,package,artifact_hash,data_path,archive_package,archived

def store(): return Store(data_path())
def gateway(): return Zarinpal(os.getenv('ZARINPAL_MERCHANT_ID',''),sandbox=os.getenv('ZARINPAL_SANDBOX','0')=='1')
def secure_response(r):
    r['Cache-Control']='no-store, private';r['Referrer-Policy']='no-referrer';r['X-Robots-Tag']='noindex, nofollow';r['X-Content-Type-Options']='nosniff';return r
def private(view):
    @wraps(view)
    def wrapped(*a,**k):return secure_response(view(*a,**k))
    return wrapped
def session_id(request):
    if 'costkit_visit' not in request.session:request.session['costkit_visit']=secrets.token_hex(16)
    return request.session['costkit_visit']
def limited(request,kind,count=10):
    # Do not trust a caller-controlled X-Forwarded-For header.
    ip=request.META.get('REMOTE_ADDR','unknown')
    key=hmac.new(settings.SECRET_KEY.encode(),(kind+ip).encode(),hashlib.sha256).hexdigest()
    return not store().rate(key,count)
def context(request,**kw):
    ready=not readiness()
    structured={'@context':'https://schema.org','@type':'SoftwareApplication','name':'Zomorod CostKit 1.0','applicationCategory':'BusinessApplication','operatingSystem':'Web browser','url':'https://zomorodmelal.ir/costkit/'}
    if ready:structured['offers']={'@type':'Offer','price':str(price()),'priceCurrency':'IRR','availability':'https://schema.org/InStock','url':'https://zomorodmelal.ir/costkit/'}
    schema=json.dumps(structured,ensure_ascii=False).replace('<','\\u003c')
    return dict(price_irr=price(),price_toman=price()//10,ready=ready,seller=os.getenv('ZM_COSTKIT_SELLER','شرکت کشت و صنعت زمرد ملل'),support_email=os.getenv('ZM_COSTKIT_SUPPORT_EMAIL',''),terms_version=TERMS_VERSION,schema_json=schema,**kw)
def render_page(request,name,**kw):return render(request,'revenue_stream/'+name+'.html',context(request,**kw))
def granted(request,oid):return time.time()-float(request.session.get('costkit_orders',{}).get(oid,0))<3600
def grant(request,oid):
    request.session.cycle_key();rows=request.session.get('costkit_orders',{});rows={k:v for k,v in rows.items() if time.time()-v<3600};rows[oid]=time.time();request.session['costkit_orders']=rows

@require_GET
def landing(request):
    sid=session_id(request)
    source=request.GET.get('utm_source','direct')
    campaign=request.GET.get('utm_campaign','')
    tag=re.sub('[^A-Za-z0-9_-]','',source)[:40]+(':'+re.sub('[^A-Za-z0-9_-]','',campaign)[:40] if campaign else '')
    request.session.setdefault('costkit_source',tag or 'direct')
    if not any(x in request.META.get('HTTP_USER_AGENT','').lower() for x in ('bot','spider','crawler')):
        store().event('visit','visit:'+sid,source=request.session['costkit_source'])
    r=render_page(request,'landing');r['Cache-Control']='private, no-cache';return r

@require_GET
def asset(request,name):
    if name not in ('sales.css',):raise Http404
    p=ROOT/'static/revenue_stream'/name
    if not p.exists():raise Http404
    return FileResponse(p.open('rb'),content_type='text/css' if name.endswith('css') else 'image/png')

@private
@require_http_methods(['GET','POST'])
def checkout(request):
    if readiness():return render(request,'revenue_stream/pending.html',context(request),status=503)
    nonce=request.session.setdefault('costkit_nonce',secrets.token_hex(24))
    if request.method=='GET':
        store().event('checkout','checkout:'+nonce,source=request.session.get('costkit_source','direct'))
        return render_page(request,'checkout',nonce=nonce)
    if limited(request,'checkout',8):return HttpResponse('تلاش زیاد؛ بعداً دوباره امتحان کنید.',status=429)
    if not hmac.compare_digest(str(request.POST.get('nonce','')),nonce) or request.POST.get('accept')!='yes':return HttpResponse('فرم یا پذیرش شرایط معتبر نیست.',status=400)
    email=request.POST.get('email','').strip();password=request.POST.get('password','')
    try:
        validate_email(email)
        if password!=request.POST.get('password_confirm',''):raise Rejected('password_confirmation')
        oid_nonce=hashlib.sha256((session_id(request)+nonce).encode()).hexdigest()
        order=store().create(email,password,price(),archive_package(),oid_nonce,request.session.get('costkit_source','direct'),TERMS_VERSION)
    except (ValidationError,Rejected):return render(request,'revenue_stream/checkout.html',context(request,nonce=nonce,error='ایمیل، رمز حداقل ۱۲ کاراکتری و تکرار رمز را بررسی کنید.'),status=400)
    grant(request,order['id'])
    return redirect('/costkit/order/'+order['id']+'/')

@private
@require_GET
def order_page(request,oid):
    if not granted(request,oid):return redirect('/costkit/access/')
    order=store().get(oid)
    if not order:raise Http404
    return render_page(request,'order',order=order,tickets=store().tickets(oid))

@private
@require_POST
def pay(request,oid):
    if not granted(request,oid):return HttpResponse('ورود لازم است.',status=401)
    if readiness():return render(request,'revenue_stream/pending.html',context(request),status=503)
    order=store().get(oid)
    if not order:raise Http404
    if order['state']=='paid':return redirect('/costkit/order/'+oid+'/')
    if order['authority'] and order['state']=='awaiting_payment':return redirect(gateway().url(order['authority']))
    if not store().claim_request(oid):return redirect('/costkit/order/'+oid+'/')
    try:
        authority=gateway().create(order['amount'],oid,'https://zomorodmelal.ir/costkit/callback/')
        store().attach(oid,authority);store().event('payment_requested','request:'+oid,oid,order['source'])
    except (GatewayError,Rejected,ValueError):
        store().uncertain(oid);store().event('payment_error','request-error:'+oid,oid,order['source'])
        return redirect('/costkit/order/'+oid+'/')
    return redirect(gateway().url(authority))

@private
@require_GET
def callback(request):
    authority=request.GET.get('Authority','')
    if not re.fullmatch('[A-Za-z0-9-]{30,64}',authority):return HttpResponse('شناسه پرداخت معتبر نیست.',status=400)
    order=store().by_authority(authority)
    if not order:return HttpResponse('سفارش مرتبط پیدا نشد.',status=404)
    if request.GET.get('Status')!='OK':return render_page(request,'callback',message='پرداخت تأیید نشد. از صفحه سفارش وضعیت را بررسی کنید.')
    if limited(request,'verify',40):return HttpResponse('بعداً وضعیت را دوباره بررسی کنید.',status=429)
    if order['state']!='paid':
        try:
            result=gateway().verify(authority,order['amount'])
            store().verified(order['id'],authority,order['amount'],result['reference'],result['code'])
        except (GatewayError,Rejected):return render(request,'revenue_stream/callback.html',context(request,message='تأیید سروری کامل نشد. پرداخت دوباره انجام ندهید؛ از صفحه سفارش دوباره بررسی یا تیکت ثبت کنید.'),status=502)
    # Callback parameters alone never grant access to a purchased artifact.
    if granted(request,order['id']):return redirect('/costkit/order/'+order['id']+'/')
    return render_page(request,'callback',message='نتیجه پرداخت ثبت شد. برای دریافت فایل با شماره سفارش و رمز انتخابی وارد شوید.')

@private
@require_POST
def recheck(request,oid):
    if not granted(request,oid):return HttpResponse('ورود لازم است.',status=401)
    order=store().get(oid)
    if not order or not order['authority']:return HttpResponse('پرداخت قابل بررسی ثبت نشده است.',status=400)
    if limited(request,'verify',40):return HttpResponse('تلاش زیاد.',status=429)
    try:
        result=gateway().verify(order['authority'],order['amount'])
        store().verified(oid,order['authority'],order['amount'],result['reference'],result['code'])
    except (GatewayError,Rejected):return render(request,'revenue_stream/callback.html',context(request,message='هنوز تأیید معتبر دریافت نشد. پرداخت مجدد نکنید؛ از پشتیبانی پیگیری کنید.'),status=502)
    return redirect('/costkit/order/'+oid+'/')

@private
@require_http_methods(['GET','POST'])
def access(request):
    error=''
    if request.method=='POST':
        if limited(request,'access',8):return HttpResponse('تلاش زیاد؛ ۱۵ دقیقه بعد امتحان کنید.',status=429)
        oid=request.POST.get('order','')[:64]
        if store().authenticate(oid,request.POST.get('email',''),request.POST.get('password','')):
            grant(request,oid);return redirect('/costkit/order/'+oid+'/')
        error='اطلاعات ورود معتبر نیست.'
    return render_page(request,'access',error=error)

@private
@require_POST
def logout(request):
    request.session.pop('costkit_orders',None);return redirect('/costkit/access/')

@private
@require_POST
def download(request,oid):
    if not granted(request,oid):return HttpResponse('ورود لازم است.',status=401)
    order=store().get(oid)
    if not order:raise Http404
    try:content=archived(order['artifact'])
    except (OSError,ValueError):return HttpResponse('فایل این نسخه نیازمند بررسی است؛ تیکت ثبت کنید.',status=503)
    try:store().download(oid,hashlib.sha256(content).hexdigest())
    except Rejected:return HttpResponse('دسترسی دانلود معتبر نیست یا سقف دریافت تمام شده است. تیکت ثبت کنید.',status=403)
    return FileResponse(io.BytesIO(content),as_attachment=True,filename='Zomorod-CostKit-1.0.zip',content_type='application/zip')

@private
@require_POST
def ticket(request,oid):
    if not granted(request,oid):return HttpResponse('ورود لازم است.',status=401)
    try:store().ticket(oid,request.POST.get('kind','support'),request.POST.get('body',''))
    except Rejected:return HttpResponse('متن باید بین ۱۰ و ۳۰۰۰ کاراکتر باشد؛ سقف روزانه ۵ درخواست است.',status=400)
    if request.POST.get('kind')=='feedback':store().event('feedback','feedback:'+oid,oid)
    return redirect('/costkit/order/'+oid+'/')

@require_GET
def terms(request):return render_page(request,'terms')

@private
@require_http_methods(['GET','POST'])
def owner(request):
    # Reuse the existing owner identity; never introduce a second admin credential.
    try:
        from moj.communication.auth import authenticated
        allowed=authenticated(request)
    except ImportError:allowed=False
    if not allowed:return HttpResponse('ورود مالک لازم است.',status=403)
    error=''
    if request.method=='POST':
        try:
            if request.POST.get('action')=='reply':store().respond(request.POST.get('ticket',''),request.POST.get('response',''))
            elif request.POST.get('action')=='record_refund':
                if request.POST.get('confirmed')!='yes':raise Rejected('human_confirmation')
                store().record_external_refund(request.POST.get('order',''),int(request.POST.get('amount','0')),request.POST.get('evidence',''))
            else:raise Rejected('unsupported_action')
        except (Rejected,ValueError):error='ثبت انجام نشد؛ داده و تأیید انسانی را بررسی کنید.'
    return render_page(request,'owner',metrics=store().metrics(),tickets=store().tickets(),missing=readiness(),error=error,artifact=artifact_hash())
