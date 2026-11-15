"""Read-only, evidence-gated dynamic catalogue for MojPlayWin.

Never creates invoices or trusts public metadata as a licence. The existing
private gateway's product, entitlement and file checks remain authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import logging

from django.http import Http404
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

TRUSTED_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
MAX_CURSOR = 9999999999999999
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApprovedCard:
    product_id: int
    title: str
    price_usd: str
    detail_url: str


def parse_cursor(value):
    """Allow only bounded ASCII decimal cursors; never interpret Unicode digits."""
    if (type(value) is not str or not value or len(value) > 16
            or not value.isascii() or not value.isdecimal()):
        raise Http404("Invalid catalogue cursor")
    cursor = int(value)
    if cursor > MAX_CURSOR:
        raise Http404("Invalid catalogue cursor")
    return cursor


def _verified_private_gateway(request):
    """Never show payable stock without HTTPS, exact host and private release."""
    if (request.method not in ("GET", "HEAD") or not request.is_secure()
            or request.get_host().split(":")[0].lower() not in TRUSTED_HOSTS):
        return None
    try:
        from services.mpw_trx_commercial_context import checkout_flags
        from services.mpw_trx_public_catalog import public_trx_catalog, public_trx_product
        if checkout_flags(request).get("mpw_trx_easy_enabled") is not True:
            return None
        return public_trx_catalog, public_trx_product
    except (ImportError, AttributeError, LookupError, RuntimeError):
        return None


def _linked_product(product):
    """Match the mounted checkout route and exact numeric USD amount."""
    try:
        if (product is None or type(product.pk) is not int or product.pk < 1
                or not isinstance(product.title, str) or not product.title.strip()
                or getattr(product, "currency", None) != "USD"):
            return None
        amount = Decimal(str(product.price))
        if (not amount.is_finite() or not Decimal("0") < amount <= Decimal("1000")
                or amount != amount.quantize(Decimal("0.01"))):
            return None
        checkout_path = reverse("mpw_commerce:book", args=[product.pk])
        match = resolve(checkout_path)
        if (match.url_name != "book" or "mpw_commerce" not in match.namespaces
                or checkout_path != f"/commerce/book/{product.pk}/"):
            return None
        return ApprovedCard(
            product_id=product.pk, title=product.title.strip(),
            price_usd=format(amount, ".2f"),
            detail_url=f"/store/product/{product.pk}/",
        )
    except (NoReverseMatch, Resolver404, ValueError, TypeError, ArithmeticError, LookupError):
        return None


def approved_cards(request, *, cursor=0, excluded_ids=frozenset()):
    """List at most one private-page of licensed stock, with safe pagination.

    Stale/private-missing releases degrade to no new items and no payment link.
    """
    if type(cursor) is not int or not 0 <= cursor <= MAX_CURSOR:
        raise ValueError("Invalid catalogue cursor")
    gateway = _verified_private_gateway(request)
    if gateway is None:
        return (), None
    catalog, lookup = gateway
    try:
        items, more = catalog(after_id=cursor)
        if not isinstance(items, (tuple, list)) or len(items) > 24 or type(more) is not bool:
            return (), None
        cards, seen, latest = [], set(), cursor
        for product in items:
            pk = getattr(product, "pk", None)
            if type(pk) is not int or pk <= latest or pk in seen:
                return (), None
            latest = pk
            seen.add(pk)
            # Recheck each SKU in the private gateway after reading this page.
            current = lookup(pk)
            if current is None or current.pk != pk:
                continue
            card = _linked_product(current)
            if card is not None and pk not in excluded_ids:
                cards.append(card)
        if more and not items:
            return (), None
        return tuple(cards), latest if more and latest > cursor else None
    except Exception as exc:
        LOGGER.warning("Private approved catalogue unavailable: %s", type(exc).__name__)
        return (), None


def approved_product(request, product_id):
    """Resolve non-curated detail pages only for currently rights-cleared SKU."""
    if type(product_id) is not int or product_id <= 0:
        return None
    gateway = _verified_private_gateway(request)
    if gateway is None:
        return None
    _, lookup = gateway
    try:
        product = lookup(product_id)
        if product is None or product.pk != product_id:
            return None
        return product if _linked_product(product) else None
    except Exception as exc:
        LOGGER.warning("Approved product lookup unavailable: %s", type(exc).__name__)
        return None
