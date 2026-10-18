"""Read-only, tenant-scoped launch gates for MojPlayWin's main digital store.

No money movement, file entitlement, payment webhook, wallet, state mutation or
new route is performed by this module. A product being active is NOT evidence
that its payment and delivery systems work.
"""
from decimal import Decimal, InvalidOperation
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
    if any(ord(character) < 32 or ord(character) > 126 for character in parsed.path):
        return ""
    return parsed.path


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
    # No simulated cart: paid checkout is only permitted after real provider,
    # payment, delivery and end-to-end acceptance attestations, then a separate
    # production feature flag. No existing path is rewritten.
    checkout = safe_main_path(meta.get("public_checkout_path"), "/store/checkout/")
    if (price > 0 and paid_enabled and checkout
            and meta.get("gateway_merchant_verified") is True
            and meta.get("payment_e2e_verified") is True
            and meta.get("delivery_e2e_verified") is True
            and meta.get("owner_sales_release") is True):
        item["checkout_path"] = checkout
        item["for_sale"] = True
    return item


def read_main_store_catalog():
    """Run a SELECT only if explicitly enabled. No cross-tenant product leaks."""
    if not getattr(settings, "MOJPLAYWIN_NATIVE_CATALOG_ENABLED", False):
        return []
    from .models import Product
    paid_enabled = bool(getattr(settings, "MOJPLAYWIN_PAID_CHECKOUT_ENABLED", False))
    products = (Product.objects
                .filter(active=True, knowledge_article__published=True,
                        metadata__brand="mojplaywin")
                .select_related("knowledge_article")
                .order_by("-id")[:80])
    return [card for product in products
            if (card := public_product_card(product, paid_enabled=paid_enabled))
            is not None]
