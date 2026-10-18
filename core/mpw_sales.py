"""Fail-closed MojPlayWin sales offers: no automatic payment activation.

The actual checkout and chain settlement stay in the already-deployed native
payment application; this module only decides whether a public BUY link can
be shown. Static discovery cards are never considered purchasable products.
"""
from importlib import import_module

from django.db import DatabaseError
from django.urls import NoReverseMatch, reverse

from .models import Product

HOST = "mojplaywin.com"
TENANT = "mojplaywin-main"


def _belongs_to_mpw(meta):
    return isinstance(meta, dict) and (
        meta.get("tenant") == TENANT or meta.get("site") == HOST
    )


def _production_payment_verifier():
    """Require working wallet ownership, active mainnet and delivery-verifier code.

    A configured address is not proof that live incoming transfers are watched.
    No exceptions are converted to an optimistic readiness verdict.
    """
    try:
        delivery = import_module("core.cryptopay_checkout").product_delivery_ready
        owned = import_module("mpw_native_checkout.wallet_ownership").proven_assets()
        eth = import_module("core.cryptopay_mainnet_config")
        tron = import_module("core.cryptopay_tron_config")
    except (ImportError, AttributeError, ValueError, RuntimeError, OSError):
        return None
    if not isinstance(owned, dict) or not callable(delivery):
        return None
    live_eth = getattr(eth, "MAINNET_ENABLED", False) is True and bool(owned.get("ETH"))
    live_trx = getattr(tron, "MAINNET_ENABLED", False) is True and bool(owned.get("TRX"))
    if not (live_eth or live_trx):
        return None
    return delivery


def _checkout_url(pk):
    try:
        return reverse("mpw_checkout", kwargs={"pk":pk})
    except NoReverseMatch:
        return None


def eligible_for_checkout(product, delivery_verifier):
    """Explicit product-level commercial release, rights, delivery and auto-settlement.

    Payment authorization cannot be inferred from a test receipt, an active
    product flag, or the mere existence of a customer wallet.
    """
    meta = product.metadata
    if not (_belongs_to_mpw(meta)
            and product.active is True and product.currency == "USD"
            and product.price is not None and product.price > 0
            and meta.get("payment_live") is True
            and meta.get("rights_cleared") is True
            and meta.get("publication_approved") is True
            and meta.get("auto_settlement_verified") is True):
        return False
    try:
        return delivery_verifier(product) is True
    except Exception:
        return False


def verified_sales_offers(limit=12):
    """Read-only storefront bridge, returning offers only after independent gates.

    Never activates Product, Invoice, Order, wallet, or settlement workers.
    Product rows are site-scoped, and no shared-site checkout links are made.
    """
    verifier = _production_payment_verifier()
    if verifier is None:
        return []
    offers = []
    try:
        products = Product.objects.filter(
            active=True, currency="USD", price__gt=0
        ).order_by("id")[:200]
        for product in products:
            if not eligible_for_checkout(product, verifier):
                continue
            url = _checkout_url(product.pk)
            if not url:
                continue
            offers.append({"id":product.pk,"title":product.title,
                           "price":product.price,"currency":product.currency,
                           "checkout_url":url})
            if len(offers) >= limit:
                break
    except DatabaseError:
        return []
    return offers
