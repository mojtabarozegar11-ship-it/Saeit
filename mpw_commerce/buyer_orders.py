"""Customer-initiated digital order, guarded against unpaid/unsafe products.

No blockchain writes, payment claims, card capture or checkout approval bypass.
The order is ALWAYS created pending; money acceptance remains a separate path.
"""
from decimal import Decimal
from uuid import UUID
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.urls import reverse

from core.models import Product, Order, OrderItem
from .models import CommerceOrderRequest
from .policy import order_snapshot, CommercePolicyError
from .downloads import _private_file


def _allowed(request, asset):
    if (
        request.user.is_active is not True
        or not request.is_secure()
        or request.get_host().split(":")[0].lower() not in
        ("mojplaywin.com", "www.mojplaywin.com")
        or asset not in ("ETH", "TRX")
    ):
        return False
    for flag in (
        "MPW_COMMERCE_RELEASE_READY",
        "MPW_COMMERCE_INVOICING_ENABLED",
        "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
        "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",
        "MPW_COMMERCE_AUTORECONCILE_ENABLED",
        "MPW_COMMERCE_SETTLEMENT_ENABLED",
        "MPW_COMMERCE_REAL_RPC_ENABLED",
        "MPW_COMMERCE_DOWNLOADS_ENABLED",
    ):
        if getattr(settings, flag, False) is not True:
            return False
    # Never offer a receiving address before its owner proved control
    # through a genuine signed challenge. This also prevents accidental
    # acceptance when a deployer flips payment flags too early.
    from mpw_native_checkout.wallet_ownership import proven_assets
    return proven_assets().get(asset) is True


def _validated_json(request):
    if request.content_type != "application/json" or len(request.body)>1024:
        raise ValueError("Invalid request")
    data=json.loads(request.body.decode("utf-8"))
    if type(data) is not dict or set(data)!={
        "product_id","quantity","asset","request_id"
    }:
        raise ValueError("Unexpected cart fields")
    if type(data["product_id"]) is not int or data["product_id"]<=0:
        raise ValueError("Invalid product")
    if type(data["quantity"]) is not int or data["quantity"]!=1:
        raise ValueError("Only single-item digital orders are released")
    if data["asset"] not in ("ETH","TRX") or type(data["asset"]) is not str:
        raise ValueError("Unsupported network")
    if type(data["request_id"]) is not str:
        raise ValueError("Invalid checkout idempotency token")
    key=UUID(data["request_id"])
    if key.version!=4 or str(key)!=data["request_id"]:
        raise ValueError("Require canonical UUIDv4")
    return data,key


def _eligible(product):
    meta=product.metadata
    if type(meta) is not dict:
        return False
    sale=meta.get("mpw_commerce")
    return (
        product.active is True
        and product.owner_id is not None
        and product.knowledge_article_id is not None
        and product.knowledge_article.published is True
        and product.product_type in ("digital","digital_book")
        and product.currency=="USD"
        and Decimal("0.00") < product.price <= Decimal("1000.00")
        and type(sale) is dict
        and sale.get("enabled") is True
        and sale.get("fulfillment")=="digital"
        and type(sale.get("private_file")) is str
        and bool(sale["private_file"])
        and all(meta.get(flag) is True for flag in (
            "factory_publication_permission", "asset_verified",
            "quality_approved", "license_verified",
        ))
    )


@login_required
@never_cache
@csrf_protect
@require_POST
def create_digital_order(request):
    # No authenticated buyer may create any order while feature release
    # gates are closed, regardless of what fields they submit.
    if not getattr(settings,"MPW_COMMERCE_RELEASE_READY",False):
        return JsonResponse({"error":"Checkout unavailable"},status=404)
    try:
        data,key=_validated_json(request)
    except (ValueError,UnicodeError,TypeError):
        return JsonResponse({"error":"Invalid order request"},status=400)
    if not _allowed(request,data["asset"]):
        return JsonResponse({"error":"Checkout unavailable"},status=404)

    with transaction.atomic():
        cart,created=CommerceOrderRequest.objects.select_for_update().get_or_create(
            idempotency_key=key,
            defaults={"buyer":request.user,"asset":data["asset"],
                      "requested_product_id":data["product_id"]},
        )
        if not created:
            if (cart.buyer_id!=request.user.pk or cart.asset!=data["asset"]
                or cart.requested_product_id!=data["product_id"]
                or cart.order_id is None):
                return JsonResponse({"error":"Cart request conflict"},status=409)
            order=cart.order
            return JsonResponse({
                "order_id":order.pk,"status":order.status,
                "amount_usd":str(order.total),
                "next":reverse("mpw_commerce:challenge"),
                "reused":True,
            },status=200)
        if Order.objects.filter(customer=request.user,status="pending").count()>=5:
            transaction.set_rollback(True)
            return JsonResponse({"error":"Too many pending orders"},status=429)
        product=Product.objects.select_for_update().select_related(
            "knowledge_article"
        ).filter(pk=data["product_id"]).first()
        if product is None or not _eligible(product):
            transaction.set_rollback(True)
            return JsonResponse({"error":"Product not eligible for sale"},status=404)
        order=Order.objects.create(
            customer=request.user,status="pending",
            currency="USD",total=product.price,
        )
        item=OrderItem.objects.create(
            order=order,product=product,quantity=1,
            unit_price=product.price,currency="USD",
        )
        # Validate the real PRIVATE deliverable before an invoice can
        # ever be requested. If invalid, roll the entire transaction back.
        try:
            _private_file(item)
            order_snapshot(order)
        except (OSError,ValueError,CommercePolicyError):
            transaction.set_rollback(True)
            return JsonResponse({"error":"Product file unavailable"},status=409)
        cart.order=order
        cart.save(update_fields=["order"])
    return JsonResponse({
        "order_id":order.pk,"status":"pending",
        "amount_usd":str(order.total),
        "next":reverse("mpw_commerce:challenge"),
        "reused":False,
    },status=201)
