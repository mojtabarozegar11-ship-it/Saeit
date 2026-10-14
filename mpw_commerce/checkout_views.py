"""Protected customer-only REST endpoints for native ETH/TRX checkout.

NOT ROUTED ON THE LIVE SITE. All operations require explicit release gates,
authenticated active buyer, MojPlayWin HTTPS hostname and Django CSRF.
The customer's JSON can NEVER mark an Order paid or affect ledger accounting.
"""
import json
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from core.models import Order
from .buyer_wallets import (
    issue_buyer_wallet_challenge,submit_buyer_wallet_signature,
    invoice_from_verified_buyer,WalletLinkRejected,
)
from .invoicing import InvoiceRejected,RECEIVERS
from .models import BuyerWalletChallenge,CommerceInvoice


HOSTS=frozenset(("mojplaywin.com","www.mojplaywin.com"))


def _ready(request):
    return (
        getattr(settings,"MPW_COMMERCE_RELEASE_READY",False) is True
        and getattr(settings,"MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",False) is True
        and request.is_secure()
        and request.get_host().split(":")[0].lower() in HOSTS
        and request.user.is_active
    )


def _parse_json_request(request,expected):
    if not request.content_type or request.content_type!="application/json":
        raise ValueError("JSON body required")
    if len(request.body)>2048:
        raise ValueError("Body too large")
    obj=json.loads(request.body.decode("utf-8"))
    if type(obj) is not dict or set(obj)!=set(expected):
        raise ValueError("Unexpected or missing fields")
    return obj


def _deny():
    return JsonResponse({"error":"Checkout unavailable"},status=404)


@login_required
@never_cache
@csrf_protect
@require_POST
def checkout_challenge(request):
    if not _ready(request):
        return _deny()
    try:
        p=_parse_json_request(request,{"order_id","asset","sender"})
        challenge,message=issue_buyer_wallet_challenge(
            p["order_id"],request.user,p["asset"],p["sender"]
        )
        return JsonResponse({
            "challenge_id":challenge.pk,
            "message":message,
            "expires_at":challenge.expires_at.isoformat(),
            "purpose":"Customer wallet identity only; no transfer or spending approval",
        },status=201)
    except (ValueError,TypeError,WalletLinkRejected,Order.DoesNotExist):
        return JsonResponse({"error":"Order or wallet verification unavailable"},status=400)


@login_required
@never_cache
@csrf_protect
@require_POST
def checkout_verify_signature(request):
    if not _ready(request):
        return _deny()
    try:
        p=_parse_json_request(request,{"challenge_id","signature"})
        verified=submit_buyer_wallet_signature(
            request.user,p["challenge_id"],p["signature"],
        )
        if not verified:
            return JsonResponse({"verified":False},status=400)
        return JsonResponse({"verified":True},status=200)
    except (ValueError,TypeError,WalletLinkRejected):
        return JsonResponse({"verified":False},status=400)


@login_required
@never_cache
@csrf_protect
@require_POST
def checkout_invoice(request):
    if not _ready(request):
        return _deny()
    try:
        p=_parse_json_request(request,{"challenge_id"})
        invoice=invoice_from_verified_buyer(request.user,p["challenge_id"])
    except (ValueError,TypeError,WalletLinkRejected,InvoiceRejected,Order.DoesNotExist):
        return JsonResponse({"error":"Unable to create a verified payment quote"},status=400)
    network,receiver,decimals=RECEIVERS[invoice.asset]
    native=(Decimal(invoice.amount_atomic)/(Decimal(10)**decimals))
    return JsonResponse({
        "order_id":invoice.order_id,
        "invoice_id":invoice.pk,
        "asset":invoice.asset,
        "network":network,
        "receiver":receiver,
        "usd_total":format(invoice.total_usd,".2f"),
        "amount_atomic":invoice.amount_atomic,
        "amount_native":format(native,"."+str(decimals)+"f"),
        "expires_at":invoice.expires_at.isoformat(),
        "state":"awaiting",
        "payment_note":"Send exactly the stated native coin amount on the stated mainnet",
    },status=201)


@login_required
@never_cache
@require_GET
def checkout_status(request,order_id):
    if not _ready(request):
        return _deny()
    if type(order_id) is not int or order_id<=0:
        return JsonResponse({"error":"Order not found"},status=404)
    invoice=CommerceInvoice.objects.select_related("order").filter(
        order_id=order_id,order__customer_id=request.user.pk,
    ).first()
    if invoice is None:
        return JsonResponse({"error":"Order not found"},status=404)
    return JsonResponse({
        "order_id":order_id,
        "state":invoice.status,
        "network":invoice.network,
        "asset":invoice.asset,
        "can_access_purchased_items":invoice.status==CommerceInvoice.Status.PAID,
    })
