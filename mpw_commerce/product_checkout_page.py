"""Authenticated buyer page for a fully released MojPlayWin digital product.

No product, wallet address, invoice, or charge is exposed until every
separate live-commerce switch and editorial/product gate is enabled.
This module is only integrated in the QA branch until a controlled release.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.models import Product
from mpw_native_checkout.wallet_ownership import proven_assets
from .downloads import _private_file

FLAGS = (
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
    "MPW_COMMERCE_INVOICING_ENABLED",
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
)
HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
APPROVAL_FLAGS = (
    "factory_publication_permission",
    "asset_verified",
    "quality_approved",
    "license_verified",
)


def approved_for_checkout(request, product):
    if (not request.is_secure()
        or request.get_host().split(":")[0].lower() not in HOSTS
        or not request.user.is_authenticated
        or not request.user.is_active
        or any(getattr(settings, name, False) is not True for name in FLAGS)
        or product is None
        or product.active is not True
        or product.owner_id is None
        or product.knowledge_article_id is None
        or product.knowledge_article.published is not True
        or product.currency != "USD"
        or product.product_type not in ("digital", "digital_book")
        or not Decimal("0") < product.price <= Decimal("1000")):
        return False
    metadata = product.metadata
    if not isinstance(metadata, dict):
        return False
    config = metadata.get("mpw_commerce")
    if (not isinstance(config, dict)
        or config.get("enabled") is not True
        or config.get("fulfillment") != "digital"
        or any(metadata.get(k) is not True for k in APPROVAL_FLAGS)):
        return False
    try:
        _private_file(SimpleNamespace(product=product))
    except (OSError, ValueError):
        return False
    proofs = proven_assets()
    return proofs.get("ETH") is True and proofs.get("TRX") is True


@login_required  # Resolve from the MojPlayWin customer LOGIN_URL, never staff admin.
@never_cache
@require_GET
def product_checkout_page(request, product_id):
    product = (Product.objects.select_related("knowledge_article")
               .filter(pk=product_id).first())
    if not approved_for_checkout(request, product):
        raise Http404("Checkout unavailable")
    return render(request, "mpw_commerce/product_checkout.html", {
        "product": product,
        "price_usd": format(product.price, ".2f"),
    })
