"""Buyer-facing TRX-only merchant checkout, never wallet-signature based.

No routes are mounted by this module. The production URL configuration must
explicitly opt in; issue/settlement is fail-closed until paid merchant canary.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from html import escape

from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_trx_commercial_context import rights_cleared_for_sale
from services.mpw_trx_walletless_one_tap_ui import render_one_tap_invoice
from services.mpw_walletless_commercial_intent import (
    PROVIDER, WAITING, _decode, reserve_commercial_intent,
    commercial_buyer_status, open_commercial_paid_file,
)
def _ensure_live(request, *, for_paid_read=False):
    from django.conf import settings
    from django.db import connection
    from django.http import Http404
    from services.mpw_walletless_commercial_intent import _commercial_db,_paid_read_db
    host=request.get_host().split(":")[0].lower()
    if (host not in ("mojplaywin.com","www.mojplaywin.com")
        or not request.is_secure() or not request.user.is_authenticated
        or not request.user.is_active):
        raise Http404("Secure purchaser session required")
    try:
        (_paid_read_db if for_paid_read else _commercial_db)(settings,connection)
    except PaymentHold as exc:
        raise Http404("TRX checkout is not released") from exc
    return connection


def _rate_provider():
    from mpw_commerce.buyer_wallets import fetch_server_rate
    quote=fetch_server_rate("TRX")
    return quote.usd_per_asset,quote.observed_at


def _configured_receiver():
    from mpw_commerce.invoicing import RECEIVERS
    data=RECEIVERS.get("TRX")
    if (not isinstance(data,(tuple,list)) or len(data)!=3
        or data[0]!="tron-mainnet" or data[2]!=6):
        raise PaymentHold("Merchant native TRX destination not configured")
    return data[1]


def _nocache(response):
    response["Cache-Control"]="private, no-store, max-age=0"
    response["Pragma"]="no-cache"
    response["X-Content-Type-Options"]="nosniff"
    response["Referrer-Policy"]="same-origin"
    return response


def _select_order(product_id: int, buyer_id: int, connection):
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from django.http import Http404
    from core.models import Product, Order, OrderItem, PaymentIntent
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.downloads import _private_file
    from types import SimpleNamespace

    with transaction.atomic(using=connection.alias):
        get_user_model().objects.select_for_update().get(pk=buyer_id)
        product=Product.objects.select_for_update().get(
            pk=product_id,active=True,currency="USD")
        if (not _eligible(product) or not rights_cleared_for_sale(product)
                or not Decimal("0") < Decimal(product.price) <= Decimal("1000")):
            raise PaymentHold("Digital product not presently eligible")
        for old in Order.objects.select_for_update().filter(
            customer_id=buyer_id,status="pending",currency="USD",
            created_at__gte=timezone.now()-timedelta(minutes=9),
        ).order_by("-id")[:10]:
            only=list(OrderItem.objects.filter(order=old)[:2])
            if len(only)!=1 or only[0].product_id!=product_id:
                continue
            pi=PaymentIntent.objects.filter(order=old,provider=PROVIDER,status=WAITING).first()
            if pi is not None:
                claim=_decode(pi)
                if claim.expires_at>timezone.now():
                    return pi.pk
        # Never issue a payable invoice for a missing or symlinked product.
        file=_private_file(SimpleNamespace(product=product))
        if file.is_symlink() or not file.is_file():
            raise PaymentHold("Private product file is not ready")
        order=Order.objects.create(customer_id=buyer_id,status="pending",
            total=product.price,currency="USD")
        OrderItem.objects.create(order=order,product=product,quantity=1,
            unit_price=product.price,currency="USD")
        intent_id,_,_=reserve_commercial_intent(
            order.pk,buyer_id,db=connection,
            rate_provider=_rate_provider,configured_receiver=_configured_receiver)
        return intent_id


def _start_order(request, product_id):
    from django.http import Http404,HttpResponseRedirect
    from core.models import Product
    from services.mpw_trx_public_catalog import public_trx_product
    db=_ensure_live(request)
    from django.conf import settings
    from services.mpw_walletless_commercial_intent import require_active_merchant_wallet
    try:
        require_active_merchant_wallet(settings, _configured_receiver())
    except PaymentHold as exc:
        raise Http404("Merchant wallet activation is not confirmed") from exc
    if type(product_id) is not int or product_id<=0:
        raise Http404
    # Dynamic product admission is fail-closed; the locked order writer then
    # rechecks rights, price, protected asset and actual product ownership.
    if public_trx_product(product_id) is None:
        raise Http404("Product is not approved for public TRX purchase")
    try:
        invoice_id=_select_order(product_id,request.user.pk,db)
    except (PaymentHold,ValueError,Product.DoesNotExist) as exc:
        raise Http404("Payment is not available") from exc
    # A guest order is always linked to its validated email and a durable
    # delivery outbox before the payable invoice is exposed to the buyer.
    from services.mpw_trx_guest_delivery import record_invoice
    record_invoice(invoice_id, request.user)
    return _nocache(HttpResponseRedirect(
        f"/commerce/trx-easy/invoice/{invoice_id}/"))


def _get_owner_invoice(request, invoice_id):
    from django.http import Http404
    from core.models import PaymentIntent
    if type(invoice_id) is not int or invoice_id<=0:
        raise Http404
    intent=PaymentIntent.objects.select_related("order").filter(
        pk=invoice_id,order__customer_id=request.user.pk,provider=PROVIDER,
    ).first()
    if intent is None:
        raise Http404
    return intent


def _show_invoice(request, invoice_id):
    from django.http import Http404,HttpResponse
    from django.utils import timezone
    from django.middleware.csrf import get_token
    _ensure_live(request)
    intent=_get_owner_invoice(request,invoice_id)
    try:
        invoice=_decode(intent)
    except PaymentHold as exc:
        raise Http404("Invoice could not be verified") from exc
    if intent.status!=WAITING or invoice.expires_at<=timezone.now():
        # Closed invoices are still accessible to their verified owner, but
        # must never display a payable amount or invite a second transfer.
        closed_page = """<!doctype html><html lang="en"><head>
        <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <meta name="robots" content="noindex,nofollow">
        <title>Invoice closed | MojPlayWin</title>
        <style>body{margin:0;background:#09192c;color:#f2f7ff;font:17px system-ui,sans-serif}
        main{max-width:650px;margin:7vh auto;padding:32px;border:1px solid #385674;
        border-radius:18px;background:#172b45}h1{font-size:clamp(25px,5vw,35px)}
        p{line-height:1.65}a{display:inline-block;margin:10px 12px 0 0;padding:13px 16px;
        border-radius:10px;background:#75e1d2;color:#082039;font-weight:700;text-decoration:none}
        a.secondary{background:#e8f0ff}</style></head><body>
        <main role="status"><h1>This invoice is no longer payable.</h1>
        <p>It has expired or its payment state has changed. Do not send TRX to
        this invoice or pay it a second time.</p>
        <p>If you already transferred TRX, check your purchase history and
        wait for verified blockchain settlement; contact support if necessary.</p>
        <a href="/commerce/trx-easy/purchases/">My TRX purchases</a>
        <a class="secondary" href="/store/">Return to store</a>
        <a class="secondary" href="/support/">Purchase support</a>
        </main></body></html>"""
        response=HttpResponse(closed_page,content_type="text/html; charset=utf-8")
        response["Content-Security-Policy"]="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        response["X-Robots-Tag"]="noindex, nofollow"
        return _nocache(response)
    # Older pending invoices remain queryable, but may not invite payments
    # while this merchant-owned receiver lacks independent activation proof.
    from django.conf import settings
    from services.mpw_walletless_commercial_intent import require_active_merchant_wallet
    try:
        require_active_merchant_wallet(settings, invoice.recipient)
    except PaymentHold:
        paused_page = (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow">'
            '<title>TRX invoice paused | MojPlayWin</title>'
            '<style>body{margin:0;background:#09192c;color:#eef5ff;'
            'font:17px system-ui,sans-serif}main{max-width:650px;margin:7vh auto;'
            'padding:32px;border:1px solid #385674;border-radius:18px;background:#172b45}'
            'h1{font-size:clamp(25px,5vw,35px)}p{line-height:1.6}a{color:#75e1d2}'
            '</style></head><body><main role="status">'
            '<h1>This TRX invoice is temporarily paused.</h1>'
            '<p>Do not send TRX yet. Merchant wallet activation must be confirmed '
            'before any payment is requested.</p>'
            '<p>If you already transferred funds, you can check settlement status '
            'without paying again.</p>'
            f'<a href="/commerce/trx-easy/status/{invoice_id}/">Check order status</a> '
            '<a href="/commerce/trx-easy/purchases/">Recover purchases</a>'
            '</main></body></html>'
        )
        response=HttpResponse(paused_page,status=503,
            content_type="text/html; charset=utf-8")
        response["Retry-After"]="900"
        response["Content-Security-Policy"]=(
            "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'")
        response["X-Robots-Tag"]="noindex, nofollow"
        return _nocache(response)
    html,csp=render_one_tap_invoice(invoice,
        status_path=f"/commerce/trx-easy/status/{invoice_id}/")
    # Include a same-origin, CSRF-protected POST path. The GET status endpoint
    # stays strictly read-only; the browser never sends a payment claim.
    token=escape(get_token(request),quote=True)
    extra=(f'<main data-reconcile-url="/commerce/trx-easy/reconcile/{invoice_id}/" '
           f'data-csrf-token="{token}" ')
    if html.count(b"<main ")!=1:
        raise Http404("Unexpected invoice markup")
    html=html.replace(b"<main ",extra.encode("ascii"),1)
    response=HttpResponse(html,content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"]=csp
    return _nocache(response)


def _invoice_status(request, invoice_id):
    from django.http import JsonResponse
    _ensure_live(request,for_paid_read=True)
    _get_owner_invoice(request,invoice_id)
    state=commercial_buyer_status(invoice_id,request.user.pk)
    return _nocache(JsonResponse(state))


def _reconcile_invoice(request, invoice_id):
    """POST-only buyer event. Only a configured server verifier may settle."""
    from django.http import JsonResponse
    from services.mpw_walletless_commercial_intent import reconcile_commercial_intent_from_candidates
    from services.mpw_tron_readonly_deposit_candidates import find_candidate_hashes
    from services.mpw_trx_commercial_chain import read_only_independent_pair
    _ensure_live(request,for_paid_read=True)
    _get_owner_invoice(request,invoice_id)
    try:
        reconcile_commercial_intent_from_candidates(
            invoice_id, request.user.pk, server_lookup=find_candidate_hashes,
            pair=read_only_independent_pair(),
        )
    except (PaymentHold, OSError, ValueError):
        # Finality not established: leave order pending and avoid a false grant.
        pass
    return _nocache(JsonResponse(commercial_buyer_status(
        invoice_id,request.user.pk)))


def _download_paid(request, invoice_id):
    from django.http import FileResponse,Http404
    from core.models import OrderItem
    from mpw_commerce.downloads import _private_file
    _ensure_live(request,for_paid_read=True)
    intent=_get_owner_invoice(request,invoice_id)
    try:
        filename=_private_file(OrderItem.objects.get(order=intent.order)).name
        stream=open_commercial_paid_file(invoice_id,request.user.pk)
    except (PaymentHold,ValueError,OSError) as exc:
        raise Http404("File is not available") from exc
    # Server opens O_NOFOLLOW after checking proof + ownership. FileResponse
    # owns and closes the descriptor after streaming the private product.
    response=FileResponse(stream,as_attachment=True,filename=filename)
    return _nocache(response)


def _views():
    from django.contrib.auth.decorators import login_required
    from django.views.decorators.cache import never_cache
    from django.views.decorators.csrf import csrf_protect
    from django.views.decorators.http import require_GET,require_POST
    global start_order,show_invoice,invoice_status,reconcile_invoice,download_paid
    start_order=never_cache(login_required(csrf_protect(require_POST(_start_order))))
    show_invoice=never_cache(login_required(require_GET(_show_invoice)))
    invoice_status=never_cache(login_required(require_GET(_invoice_status)))
    reconcile_invoice=never_cache(login_required(csrf_protect(require_POST(_reconcile_invoice))))
    download_paid=never_cache(login_required(require_GET(_download_paid)))


_views()

# NO urlpatterns; production config must explicitly mount these gated endpoints.
COMMERCIAL_URLPATTERNS=(
    ("commerce/trx-easy/start/<int:product_id>/",start_order),
    ("commerce/trx-easy/invoice/<int:invoice_id>/",show_invoice),
    ("commerce/trx-easy/status/<int:invoice_id>/",invoice_status),
    ("commerce/trx-easy/reconcile/<int:invoice_id>/",reconcile_invoice),
    ("commerce/trx-easy/download/<int:invoice_id>/",download_paid),
)

# MPW_GUEST_CHECKOUT_LIVE_V1
from services.mpw_trx_guest_commerce import patch_commercial as _mpw_patch_commercial
_mpw_patch_commercial(globals())
