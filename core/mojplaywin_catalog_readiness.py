"""Read-only, tenant-scoped launch gates for MojPlayWin's main digital store.

No money movement, file entitlement, payment webhook, wallet, state mutation or
new route is performed by this module. A product being active is NOT evidence
that its payment and delivery systems work.
"""
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
import re
from urllib.parse import urlsplit

from django.conf import settings


def safe_main_path(value, prefix):
    """Allow only relative paths on the designated main site; never child sites."""
    if not isinstance(value, str) or not value.startswith(prefix):
        return ""
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return ""
    if not parsed.path.startswith(prefix) or "//" in parsed.path or ".." in parsed.path:
        return ""
    if not re.fullmatch(r"/[A-Za-z0-9._/-]+", parsed.path) or "\\\\" in parsed.path:
        return ""
    return parsed.path


# These are the EIGHT release controls of the *existing* MojPlayWin ETH/TRX
# commerce engine. A storefront must not invent a new payment integration.
CRYPTO_RELEASE_FLAGS = (
    "MPW_COMMERCE_RELEASE_READY",
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
    "MPW_COMMERCE_INVOICING_ENABLED",
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED",
    "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED",
    "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
)
CRYPTO_PRODUCT_FLAGS = (
    "factory_publication_permission",
    "asset_verified",
    "quality_approved",
    "license_verified",
)


def existing_crypto_checkout_path(product):
    """Resolve an ALREADY-INSTALLED native ETH/TRX checkout, otherwise no link.

    The older commerce engine lives on a separate unmerged branch; do not
    treat its source code as proof that it is deployed or released. Even when
    the global flags are on, refuse to link unless buyer checkout routes,
    wallet ownership evidence and a real private deliverable all exist.
    """
    if any(getattr(settings, flag, False) is not True
           for flag in CRYPTO_RELEASE_FLAGS):
        return ""
    meta = product.metadata if isinstance(product.metadata, dict) else {}
    cfg = meta.get("mpw_commerce")
    if (not isinstance(cfg, dict) or cfg.get("enabled") is not True
            or cfg.get("fulfillment") != "digital"
            or any(meta.get(flag) is not True for flag in CRYPTO_PRODUCT_FLAGS)
            or meta.get("owner_sales_release") is not True
            or not isinstance(getattr(product, "pk", None), int)
            or product.pk <= 0
            or getattr(product, "owner_id", None) is None
            or getattr(product, "knowledge_article_id", None) is None
            or product.product_type not in {"digital", "digital_book"}
            or str(product.currency).upper() != "USD"
            or not Decimal("0") < product.price <= Decimal("1000")):
        return ""
    try:
        # Import must fail CLOSED on branches/hosts without the real engine.
        from django.urls import reverse
        from mpw_commerce.downloads import _private_file
        from mpw_native_checkout.wallet_ownership import proven_assets
        _private_file(SimpleNamespace(product=product))
        proofs = proven_assets()
        if proofs.get("ETH") is not True or proofs.get("TRX") is not True:
            return ""
        path = reverse("mpw_commerce:book",
                       kwargs={"product_id": product.pk})
    except Exception:
        # An unavailable package, private file, wallet proof or URL is NOT
        # permission to advertise checkout.
        return ""
    if not re.fullmatch(r"/commerce/book/[1-9][0-9]*/", path):
        return ""
    return path


def public_product_card(product, *, paid_enabled=False):
    """Pure projection: expose only approved main-brand fields, never metadata."""
    meta = product.metadata if isinstance(product.metadata, dict) else {}
    if meta.get("brand") != "mojplaywin" or not product.active:
        return None
    article = getattr(product, "knowledge_article", None)
    if article is None or not article.published:
        return None
    try:
        price = Decimal(str(product.price))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not price.is_finite() or price < 0:
        return None
    currency = str(product.currency or "").upper()
    if currency not in {"USD", "CAD", "EUR", "IRR"}:
        return None
    details = safe_main_path(meta.get("public_detail_path"), "/products/")
    description = str(meta.get("public_description") or "").strip()[:360]
    item = {
        "title": str(product.title)[:300],
        "category": str(product.product_type)[:50],
        "description": description,
        "price": price,
        "currency": currency,
        "details_path": details,
        "checkout_path": "",
        "for_sale": False,
        "is_free": price == 0,
    }
    # Buyer is directed ONLY to the existing ETH/TRX product checkout page.
    # No Stripe, fabricated payment link or auto-activation is ever created.
    if price > 0 and paid_enabled:
        checkout = existing_crypto_checkout_path(product)
        if checkout:
            item["checkout_path"] = checkout
            item["for_sale"] = True
    return item


def read_main_store_catalog():
    """Run a SELECT only if explicitly enabled. No cross-tenant product leaks."""
    if not getattr(settings, "MOJPLAYWIN_NATIVE_CATALOG_ENABLED", False):
        return []
    from .models import Product
    paid_enabled = bool(getattr(settings, "MOJPLAYWIN_NATIVE_CRYPTO_CHECKOUT_ENABLED", False))
    products = (Product.objects
                .filter(active=True, knowledge_article__published=True,
                        metadata__brand="mojplaywin")
                .select_related("knowledge_article")
                .order_by("-id")[:80])
    return [card for product in products
            if (card := public_product_card(product, paid_enabled=paid_enabled))
            is not None]
