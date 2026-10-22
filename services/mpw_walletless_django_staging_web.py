"""Complete walletless TRX Django buyer journey, STAGING TEST DATABASE ONLY.

Strictly isolated: the test_ MariaDB gate must pass before ANY SQL operation,
no URL is mounted in production and public feature flag must remain False.
No wallet address or txid is accepted from the customer for payment authority.
Buyer click -> locked order + reserved amount -> mobile invoice + wallet/QR ->
independent server settlement -> owner-only status -> protected private file.
"""
from __future__ import annotations

from datetime import timezone
from decimal import Decimal
import os

from services.mpw_trx_walletless_core import InvoiceIntent,PaymentHold
from services.mpw_walletless_django_test_bridge import (
    _test_only_guard,unpaid_owner_safe_status,
)
from services.mpw_walletless_django_test_invoice import reserve_to_django_test_database
from services.mpw_trx_walletless_one_tap_ui import render_one_tap_invoice


def _ensure_test(request):
    from django.conf import settings
    from django.db import connection
    from django.http import Http404
    try:
        _test_only_guard(settings,connection)
    except PaymentHold as exc:
        raise Http404("This secure checkout is not available") from exc
    if not request.is_secure() or not request.user.is_authenticated or not request.user.is_active:
        raise Http404("A secure active buyer session is required")
    if not str(request.get_host()).lower().split(":")[0].endswith((".test",".invalid")):
        raise Http404("Staging-only hostname required")
    return connection


def _owner_invoice(conn,invoice_id:int,buyer_id:int):
    from django.http import Http404
    from core.models import Order
    if type(invoice_id) is not int or invoice_id<=0 or type(buyer_id) is not int or buyer_id<=0:
        raise Http404
    with conn.cursor() as cur:
        cur.execute(
          """SELECT order_id,customer_id,network,recipient,amount_sun,total_usd,
                    rate_usd_per_trx,issued_at,expires_at,status,verified_tx_hash
             FROM mpw_walletless_trx_reservation_v1
             WHERE id=%s AND customer_id=%s LIMIT 1""",[invoice_id,buyer_id])
        row=cur.fetchone()
    if row is None:
        raise Http404
    order=Order.objects.filter(pk=row[0],customer_id=buyer_id).first()
    if order is None:
        raise Http404
    return order,row


def _trusted_status(conn,invoice_id,buyer_id):
    from core.models import LedgerEntry,OrderItem
    from mpw_commerce.models import CommerceFulfillment
    from mpw_commerce.fulfillment import _private_file
    order,row=_owner_invoice(conn,invoice_id,buyer_id)
    (order_id,owner,network,recipient,sun,usd,rate,issued,expires,
     status,tx_hash)=row
    result={"status":"awaiting","can_download":False}
    if status=="expired":
        return {"status":"expired","can_download":False}
    if status!="paid" or network!="tron-mainnet" or not tx_hash or order.status!="paid":
        return result
    with conn.cursor() as cur:
        cur.execute(
         """SELECT tx_hash,recipient,amount_sun
            FROM mpw_walletless_trx_receipt_v1
            WHERE invoice_id=%s AND network=%s AND tx_hash=%s LIMIT 1""",
            [invoice_id,network,tx_hash])
        receipt=cur.fetchone()
    if not receipt or receipt[1]!=recipient or int(receipt[2])!=int(sun):
        return result
    ref="walletless:"+network+":"+tx_hash
    real_ledger=LedgerEntry.objects.filter(order=order,reference=ref,
      entry_type="credit",currency="USD",amount=Decimal(str(usd))).exists()
    items=list(OrderItem.objects.filter(order=order)[:2])
    if len(items)!=1:
        return result
    item=items[0]
    ready=CommerceFulfillment.objects.filter(
        item=item,kind="digital",status=CommerceFulfillment.Status.READY).exists()
    result=unpaid_owner_safe_status(
        customer_id=buyer_id,order_owner_id=order.customer_id,
        invoice_status=status,has_verified_ledger=real_ledger,
        has_ready_fulfillment=ready)
    if not result["can_download"]:
        return result
    try:
        path=_private_file(item)
        if path.is_symlink() or not path.is_file():
            raise OSError("Private file unavailable")
    except (OSError,ValueError):
        return {"status":"review","can_download":False}
    result["download_path"]=f"/commerce/trx-easy/download/{invoice_id}/"
    return result


def _rate_provider():
    from mpw_commerce.buyer_wallets import fetch_server_rate
    rate=fetch_server_rate("TRX")
    return rate.usd_per_asset,rate.observed_at


def _configured_receiver():
    from mpw_commerce.invoicing import RECEIVERS
    network,receiver=RECEIVERS["TRX"]
    if network!="tron-mainnet":
        raise PaymentHold("Not a TRON mainnet merchant receiver")
    return receiver


def _choose_locked_order(product_id,buyer_id,conn):
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from core.models import Product,Order,OrderItem
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.fulfillment import _private_file
    from django.http import Http404
    from datetime import timedelta

    # A lock on buyer identity prevents duplicate POSTs from separate browser tabs.
    with transaction.atomic(using=conn.alias):
        get_user_model().objects.select_for_update().get(pk=buyer_id)
        product=Product.objects.select_for_update().get(pk=product_id,active=True,currency="USD")
        if not _eligible(product) or Decimal(product.price)<=0 or Decimal(product.price)>1000:
            raise Http404("Digital product not currently eligible")
        for old in Order.objects.select_for_update().filter(
          customer_id=buyer_id,status="pending",currency="USD",
          created_at__gte=timezone.now()-timedelta(minutes=9)).order_by("-id")[:10]:
            only=list(OrderItem.objects.filter(order=old)[:2])
            if len(only)!=1 or only[0].product_id!=product_id:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id,amount_sun FROM mpw_walletless_trx_reservation_v1
                       WHERE order_id=%s AND customer_id=%s AND status='awaiting'
                       AND expires_at>UTC_TIMESTAMP(6) LIMIT 1""",
                       [old.pk,buyer_id])
                existing=cur.fetchone()
            if existing is not None:
                return int(existing[0])
        # Do not open an order unless the immutable digital asset exists now.
        from types import SimpleNamespace
        source=_private_file(SimpleNamespace(product=product))
        if source.is_symlink() or not source.is_file():
            raise PaymentHold("Private digital product file is not ready")
        order=Order.objects.create(customer_id=buyer_id,status="pending",
                    total=product.price,currency="USD")
        OrderItem.objects.create(order=order,product=product,quantity=1,
                   unit_price=product.price,currency="USD")
        ident,amount,created=reserve_to_django_test_database(
            order.pk,buyer_id,django_connection=conn,
            rate_provider=_rate_provider,configured_receiver=_configured_receiver)
        return ident


def _nocache(response):
    response["Cache-Control"]="no-store, private, max-age=0"
    response["Pragma"]="no-cache"
    response["X-Content-Type-Options"]="nosniff"
    response["Referrer-Policy"]="no-referrer"
    return response


def _start_order(request,product_id):
    from django.http import HttpResponseRedirect,Http404
    conn=_ensure_test(request)
    if type(product_id) is not int or product_id<=0:
        raise Http404
    try:
        invoice_id=_choose_locked_order(product_id,request.user.pk,conn)
    except (PaymentHold,ValueError) as exc:
        raise Http404("Checkout currently unavailable") from exc
    return _nocache(HttpResponseRedirect(
        f"/commerce/trx-easy/invoice/{invoice_id}/"))


def _show_invoice(request,invoice_id):
    from django.http import HttpResponse,Http404
    conn=_ensure_test(request)
    order,row=_owner_invoice(conn,invoice_id,request.user.pk)
    _,owner,network,recipient,sun,usd,rate,issued,expires,status,tx_hash=row
    if status!="awaiting":
        raise Http404("Invoice is no longer payable")
    if not (issued<expires) or expires.replace(tzinfo=timezone.utc)<=__import__("datetime").datetime.now(timezone.utc):
        raise Http404("Invoice expired")
    invoice=InvoiceIntent(order_id=order.pk,customer_id=owner,network=network,
        recipient=recipient,amount_sun=int(sun),usd_total=Decimal(str(usd)),
        quote_usd_per_trx=Decimal(str(rate)),
        issued_at=issued.replace(tzinfo=timezone.utc),
        expires_at=expires.replace(tzinfo=timezone.utc))
    html,csp=render_one_tap_invoice(invoice,status_path=f"/commerce/trx-easy/status/{invoice_id}/")
    response=HttpResponse(html,content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"]=csp
    return _nocache(response)


def _invoice_status(request,invoice_id):
    from django.http import JsonResponse
    conn=_ensure_test(request)
    result=_trusted_status(conn,invoice_id,request.user.pk)
    return _nocache(JsonResponse(result))


def _download_paid(request,invoice_id):
    from django.http import FileResponse,Http404
    from core.models import OrderItem
    from mpw_commerce.fulfillment import _private_file
    conn=_ensure_test(request)
    status=_trusted_status(conn,invoice_id,request.user.pk)
    if status.get("can_download") is not True:
        raise Http404
    order,row=_owner_invoice(conn,invoice_id,request.user.pk)
    item=OrderItem.objects.get(order=order)
    source=_private_file(item)
    if source.is_symlink() or not source.is_file():
        raise Http404
    flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(str(source),flags)
    response=FileResponse(os.fdopen(fd,"rb"),as_attachment=True,filename=source.name)
    return _nocache(response)


# Decorators keep CSRF and methods strict even in private staging.
def _decorate():
    from django.contrib.auth.decorators import login_required
    from django.views.decorators.cache import never_cache
    from django.views.decorators.csrf import csrf_protect
    from django.views.decorators.http import require_POST,require_GET
    global start_order,show_invoice,invoice_status,download_paid
    start_order=never_cache(login_required(csrf_protect(require_POST(_start_order))))
    show_invoice=never_cache(login_required(require_GET(_show_invoice)))
    invoice_status=never_cache(login_required(require_GET(_invoice_status)))
    download_paid=never_cache(login_required(require_GET(_download_paid)))

_decorate()

# NOT mounted into public config/urls.py, explicitly test_only.
STAGING_URLPATTERNS=(
    ("commerce/trx-easy/start/<int:product_id>/",start_order),
    ("commerce/trx-easy/invoice/<int:invoice_id>/",show_invoice),
    ("commerce/trx-easy/status/<int:invoice_id>/",invoice_status),
    ("commerce/trx-easy/download/<int:invoice_id>/",download_paid),
)
