"""Read-only, evidence-gated dynamic catalogue for MojPlayWin.

Never creates invoices or trusts public metadata as a licence. The existing
private gateway's product, entitlement and file checks remain authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import logging

from django.http import Http404
from .mojplaywin_checkout_route import verified_guest_checkout_url

TRUSTED_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
MAX_CURSOR = (1 << 63) - 1
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApprovedCard:
    product_id: int
    title: str
    price_usd: str
    detail_url: str


def parse_cursor(value):
    """Allow only bounded ASCII decimal cursors; never interpret Unicode digits."""
    if (type(value) is not str or not value or len(value) > 19
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
    except Exception as exc:
        # A broken release flag provider or migration must not turn the
        # informational storefront into HTTP 500. Still fail closed.
        LOGGER.warning("Private gateway release verification failed: %s",
                       type(exc).__name__)
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
        # Do not reverse the legacy namespaced URL: private config places the
        # guest-ownership checkout ahead of it at this identical path.
        if verified_guest_checkout_url(product.pk) is None:
            return None
        return ApprovedCard(
            product_id=product.pk, title=product.title.strip(),
            price_usd=format(amount, ".2f"),
            detail_url=f"/store/product/{product.pk}/",
        )
    except (ValueError, TypeError, ArithmeticError, AttributeError, LookupError):
        # A corrupt price row must be skipped, not turn the entire /store/
        # request into a 500 while the private gateway is otherwise healthy.
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
        # The private bounded catalogue may scan 256 *rejected* rows and
        # return no approved products for this window. Its cursor tracks the
        # last DB row scanned, NOT necessarily the last approved product.
        # Without this cursor, valid stock beyond rejected legacy SKUs was
        # invisible to customers. A stale/untrusted cursor is never used.
        scanned = getattr(items, "last_scanned_id", latest)
        if (type(scanned) is not int or not latest <= scanned <= MAX_CURSOR
                or (more and scanned <= cursor)):
            return (), None
        if more and scanned > cursor:
            return tuple(cards), scanned
        return tuple(cards), None
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
