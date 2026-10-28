"""Public product entry and authenticated recovery for native TRX invoices."""
from html import escape
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from services.mpw_trx_commercial_web import _ensure_live, _nocache
from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_trx_commercial_context import rights_cleared_for_sale


def _checkout_csrf_referrer(response):
    """Permit HTTPS same-origin Referer while suppressing cross-origin referrers."""
    import re
    content,count=re.subn(
        rb'<meta\s+name=["\']referrer["\']\s+content=["\']no-referrer["\']\s*/?>',
        b'<meta name="referrer" content="same-origin">',
        response.content,count=1,flags=re.I)
    if count!=1:
        raise Http404("Secure checkout referrer policy is missing or ambiguous")
    response.content=content
    response["Referrer-Policy"]="same-origin"
    return response


def _page(title, content):
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+escape(title)+''' | MojPlayWin</title><style>body{margin:0;background:#101520;color:#f7f7f7;font:17px/1.65 system-ui}main{max-width:850px;margin:auto;padding:28px 18px}a{color:#83e5d4}article{border:1px solid #475368;border-radius:16px;padding:22px;margin:18px 0;background:#182234}.button{display:inline-block;background:#83e5d4;color:#102326;padding:10px 18px;border-radius:9px;text-decoration:none;font-weight:700}h1{line-height:1.2}small{color:#c4cbd8}</style><main><nav><a href="/">Home</a> · <a href="/store/">Products</a> · <a href="/commerce/trx-easy/purchases/">My TRX purchases</a></nav><h1>'''+escape(title)+'''</h1>'''+content+'''<p><a href="/support/">Purchase support</a> · <a href="/terms/">Terms</a> · <a href="/privacy/">Privacy</a></p></main></html>'''
    response=_nocache(HttpResponse(html))
    response['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    return response


@require_GET
def public_shop(request):
    from django.conf import settings
    from django.db import connection
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.downloads import _private_file
    from services.mpw_walletless_commercial_intent import _commercial_db
    from types import SimpleNamespace
    if request.get_host().split(':')[0].lower() not in ('mojplaywin.com','www.mojplaywin.com') or not request.is_secure():
        raise Http404
    try: _commercial_db(settings,connection)
    except PaymentHold: raise Http404
    cards=[]
    for p in Product.objects.filter(pk__in=getattr(settings,'MPW_TRX_PUBLIC_PRODUCT_IDS',()),active=True).order_by('pk'):
        if not _eligible(p) or not rights_cleared_for_sale(p): continue
        try:
            f=_private_file(SimpleNamespace(product=p))
            if f.is_symlink() or not f.is_file() or f.stat().st_size<=0: continue
        except (OSError,ValueError): continue
        cards.append(f'<article><h2>{escape(p.title)}</h2><p>${escape(str(p.price))} USD · Pay the quoted equivalent in TRX</p><a class="button" href="/commerce/book/{p.pk}/">Buy with TRX</a></article>')
    return _page('Buy digital products with TRX','<p>Choose a product, sign in, and create your payment invoice. No sender address registration or wallet connection is needed. Pay the exact TRX amount on the TRON network; your download unlocks after confirmation.</p>'+''.join(cards))


@login_required
@require_GET
def product_checkout(request, product_id):
    from django.conf import settings
    from django.shortcuts import render
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.downloads import _private_file
    from types import SimpleNamespace
    _ensure_live(request)
    if product_id not in getattr(settings,'MPW_TRX_PUBLIC_PRODUCT_IDS',()):
        raise Http404
    product=Product.objects.select_related('knowledge_article').filter(pk=product_id).first()
    if product is None or not _eligible(product) or not rights_cleared_for_sale(product):
        raise Http404
    f=_private_file(SimpleNamespace(product=product))
    if f.is_symlink() or not f.is_file() or f.stat().st_size<=0: raise Http404
    response=_nocache(render(request,'mpw_commerce/product_checkout.html',{
        'product':product,'price_usd':format(product.price,'.2f'),
        'mpw_trx_easy_enabled':True}))
    response=_checkout_csrf_referrer(response)
    response['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    return response


@login_required
@require_GET
def purchases(request):
    from core.models import PaymentIntent
    from services.mpw_walletless_commercial_intent import PROVIDER,commercial_buyer_status,_decode
    from django.utils import timezone
    _ensure_live(request,for_paid_read=True)
    cards=[]
    for pi in PaymentIntent.objects.select_related('order').filter(provider=PROVIDER,order__customer_id=request.user.pk).order_by('-pk')[:100]:
        state=commercial_buyer_status(pi.pk,request.user.pk)
        if state.get('can_download'):
            detail=f'<a class="button" href="/commerce/trx-easy/download/{pi.pk}/">Download purchase</a>'
        elif pi.status=='awaiting_chain' and _decode(pi).expires_at>timezone.now():
            detail=f'<a href="/commerce/trx-easy/invoice/{pi.pk}/">View payment invoice</a>'
        else:
            detail='Awaiting payment verification or invoice expired. If you have paid, do not pay again; contact support with this order number.'
        cards.append(f'<article><h2>Order #{pi.order_id}</h2><p>${escape(str(pi.amount))} USD</p><p>{detail}</p></article>')
    return _page('My TRX purchases',''.join(cards) or '<p>No TRX purchases yet. <a href="/commerce/trx-easy/">Browse products</a>.</p>')
