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
    from mpw_commerce.signal_subscriptions import subscription_sale_ready, subscription_product_terms
    from mpw_commerce.downloads import _private_file
    from services.mpw_walletless_commercial_intent import _commercial_db
    from types import SimpleNamespace
    if request.get_host().split(':')[0].lower() not in ('mojplaywin.com','www.mojplaywin.com') or not request.is_secure():
        raise Http404
    try: _commercial_db(settings,connection)
    except PaymentHold: raise Http404
    cards=[]
    for p in Product.objects.filter(pk__in=getattr(settings,'MPW_TRX_PUBLIC_PRODUCT_IDS',()),active=True).order_by('pk'):
        if not rights_cleared_for_sale(p): continue
        if p.product_type == "subscription":
            if not subscription_sale_ready(p): continue
        else:
            if not _eligible(p): continue
            try:
                f=_private_file(SimpleNamespace(product=p))
                if f.is_symlink() or not f.is_file() or f.stat().st_size<=0: continue
            except (OSError,ValueError): continue
        cards.append(f'<article><h2>{escape(p.title)}</h2><p>${escape(str(p.price))} USD · Pay the quoted equivalent in TRX</p><a class="button" href="/commerce/book/{p.pk}/">Buy with TRX</a></article>')
    return _page('Buy digital products with TRX','<p>Choose a product and enter your purchase email to request an invoice. No account signup, wallet connection or wallet signature is needed. Pay the exact TRX amount on TRON mainnet; your private download or research access becomes available only after independent blockchain confirmation.</p>'+''.join(cards))


@login_required
@require_GET
def product_checkout(request, product_id):
    from django.conf import settings
    from django.shortcuts import render
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.signal_subscriptions import subscription_sale_ready, subscription_product_terms
    from mpw_commerce.downloads import _private_file
    from types import SimpleNamespace
    _ensure_live(request)
    if product_id not in getattr(settings,'MPW_TRX_PUBLIC_PRODUCT_IDS',()):
        raise Http404
    product=Product.objects.select_related('knowledge_article').filter(pk=product_id).first()
    if product is None or not rights_cleared_for_sale(product):
        raise Http404
    subscription = product.product_type == "subscription"
    if subscription:
        if not subscription_sale_ready(product): raise Http404
    else:
        if not _eligible(product): raise Http404
        f=_private_file(SimpleNamespace(product=product))
        if f.is_symlink() or not f.is_file() or f.stat().st_size<=0: raise Http404
    response=_nocache(render(request,'mpw_commerce/product_checkout.html',{
        'product':product,'price_usd':format(product.price,'.2f'),
        'mpw_trx_easy_enabled':True,
        'signal_subscription':subscription_product_terms(product) if subscription else None}))
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
        elif state.get('subscription'):
            detail=f'<a class="button" href="/commerce/trx-easy/invoice/{pi.pk}/">Read private research</a>'
        elif pi.status=='awaiting_chain' and _decode(pi).expires_at>timezone.now():
            detail=f'<a href="/commerce/trx-easy/invoice/{pi.pk}/">View payment invoice</a>'
        else:
            detail='Awaiting payment verification or invoice expired. If you have paid, do not pay again; contact support with this order number.'
        cards.append(f'<article><h2>Order #{pi.order_id}</h2><p>${escape(str(pi.amount))} USD</p><p>{detail}</p></article>')
    return _page('My TRX purchases',''.join(cards) or '<p>No TRX purchases yet. <a href="/commerce/trx-easy/">Browse products</a>.</p>')

@require_GET
def support_page(request):
    return _page(
        "Purchase support",
        '<article><h2>Order, invoice and download help</h2>'
        '<p>For a TRX invoice, first open <a href="/commerce/trx-easy/purchases/">My TRX purchases</a> or use <a href="/commerce/trx-easy/recover/">Purchase recovery</a> with the same purchase email.</p>'
        '<p>Never send TRX outside the exact invoice shown on the secure checkout page. Do not share a seed phrase or private key.</p>'
        '<p>For unresolved order questions, email <a href="mailto:support@mojplaywin.com">support@mojplaywin.com</a> and include your order number. Do not include wallet secrets.</p></article>'
    )


@require_GET
def terms_page(request):
    return _page(
        "Terms of digital purchase",
        '<article><h2>Digital products and TRX checkout</h2>'
        '<p>Products are digital downloads or explicitly described prepaid educational research terms. Research terms are not automatically renewed. The displayed USD price is converted to a quoted TRX amount on the invoice. Payment is considered received only after server-side TRON confirmation.</p>'
        '<p>Do not pay an expired invoice. If you believe you paid an invoice, use purchase recovery and contact support with the order number.</p>'
        '<p>No investment, trading, income or performance guarantee is made by a digital product listing.</p></article>'
    )


@require_GET
def privacy_page(request):
    return _page(
        "Privacy",
        '<article><h2>Purchase data</h2>'
        '<p>The store uses the purchase email to issue an invoice, reconcile payment and provide recovery of an eligible digital order. Wallet information is used only as needed to validate the submitted payment.</p>'
        '<p>Do not submit seed phrases or private keys. Requests about access, correction or deletion can be sent to <a href="mailto:support@mojplaywin.com">support@mojplaywin.com</a>.</p></article>'
    )


@require_GET
def cookies_page(request):
    return _page(
        "Cookies",
        '<article><h2>Minimal session cookies</h2>'
        '<p>The checkout may use essential session and security cookies. The store does not require an advertising cookie to request a TRX invoice or recover a purchase.</p></article>'
    )
