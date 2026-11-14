"""Read-only digital delivery readiness and customer recovery preflight.

Part of the single mojtaba.bot.ai master agent, not a new bot or executor.
An internally consistent payment record, plausible buyer address, and self-
asserted product metadata are NOT proof of independent settled payment,
available private file, lawful rights, customer receipt or delivery. This
module does not issue download tokens, emails, grants, URLs or files.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from .models import Order, OrderItem, Product
from .revenue_evidence_gate import inspect_revenue_order

FORMAT = frozenset({"pdf", "epub", "zip", "license_key", "in_game_cosmetic"})
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
VERSION = re.compile(r"(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})\Z")
LICENSE = re.compile(r"[a-z][a-z0-9_-]{2,39}\Z")
ASSET_REF = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{15,95}\Z")
MAX_ORDERS = 100


def _buyer_email_looks_plausible(user):
    """Address syntax is only a preflight; no ownership confirmation."""
    value = getattr(user, "email", None)
    if type(value) is not str or not 5 <= len(value) <= 254:
        return False
    if value != value.strip() or not value.isascii():
        return False
    try:
        validate_email(value)
    except ValidationError:
        return False
    domain = value.rpartition("@")[2].lower()
    if domain in {"localhost", "example.com", "example.org", "example.net"}:
        return False
    if domain.endswith((".invalid", ".test", ".example", ".localhost")):
        return False
    return True


def inspect_fulfillment_order(order):
    """Return redacted blockers, never an entitlement or delivery command."""
    blockers = set()
    if not isinstance(order, Order) or type(getattr(order, "pk", None)) is not int:
        return {
            "state": "invalid_record", "blockers": ["ORDER_RECORD_INVALID"],
            "source_preflight_passed": False, "delivery_allowed": False,
            "delivery_verified": False, "buyer_email_verified": False,
            "independent_settlement_verified": False,
        }

    def block(reason):
        blockers.add(reason)

    if order.status != "paid":
        block("ORDER_NOT_PAID")
    if type(order.total) is not Decimal or not order.total.is_finite() or order.total <= 0:
        block("ORDER_AMOUNT_INVALID")
    buyer = order.customer
    if not buyer.is_active:
        block("BUYER_INACTIVE")
    if buyer.is_staff or buyer.is_superuser:
        block("BUYER_PRIVILEGED_ACCOUNT")
    if not _buyer_email_looks_plausible(buyer):
        block("BUYER_EMAIL_INVALID_OR_PLACEHOLDER")

    items = list(OrderItem.objects.filter(order_id=order.pk).select_related(
        "product__owner"
    ).order_by("pk")[:3])
    if len(items) == 0:
        block("DELIVERY_ITEM_MISSING")
    elif len(items) != 1:
        block("DELIVERY_MULTI_ITEM_NEEDS_SEPARATE_RECEIPTS")
    if items and len(items) == 1:
        item = items[0]
        if type(item.quantity) is not int or item.quantity != 1:
            block("DELIVERY_QUANTITY_UNSUPPORTED")
        if item.currency != order.currency:
            block("DELIVERY_CURRENCY_MISMATCH")
        if (type(item.unit_price) is not Decimal
                or not item.unit_price.is_finite() or item.unit_price <= 0
                or item.unit_price != order.total):
            block("DELIVERY_PRICE_MISMATCH")
        product = item.product
        if not product.active:
            block("PRODUCT_NOT_ACTIVE")
        if type(product.title) is not str or not product.title.strip():
            block("PRODUCT_TITLE_MISSING")
        owner = product.owner
        if (owner is None or not owner.is_active
                or not owner.is_superuser or not owner.is_staff):
            block("PRODUCT_OWNER_NOT_AUTHORIZED")
        metadata = product.metadata if type(product.metadata) is dict else None
        if metadata is None:
            block("PRODUCT_METADATA_NOT_OBJECT")
            metadata = {}
        if metadata.get("rights_cleared") is not True:
            block("DELIVERY_RIGHTS_NOT_CLEARED")
        if metadata.get("independent_qc_reviewed") is not True:
            block("DELIVERY_INDEPENDENT_QC_MISSING")
        if metadata.get("buyer_terms_approved") is not True:
            block("DELIVERY_BUYER_TERMS_MISSING")
        fmt = metadata.get("delivery_format")
        if type(fmt) is not str or fmt not in FORMAT:
            block("DELIVERY_FORMAT_UNSUPPORTED")
        sha = metadata.get("delivery_asset_sha256")
        if type(sha) is not str or DIGEST.fullmatch(sha) is None or sha == "0" * 64:
            block("DELIVERY_ASSET_HASH_INVALID")
        manifest = metadata.get("delivery_manifest_sha256")
        if type(manifest) is not str or DIGEST.fullmatch(manifest) is None or manifest == "0" * 64:
            block("DELIVERY_MANIFEST_HASH_INVALID")
        if type(sha) is str and type(manifest) is str and sha == manifest:
            block("DELIVERY_ASSET_MANIFEST_NOT_DISTINCT")
        version = metadata.get("delivery_version")
        if type(version) is not str or VERSION.fullmatch(version) is None:
            block("DELIVERY_VERSION_INVALID")
        license_code = metadata.get("delivery_license")
        if type(license_code) is not str or LICENSE.fullmatch(license_code) is None:
            block("DELIVERY_LICENSE_INVALID")
        asset_ref = metadata.get("delivery_asset_ref")
        if type(asset_ref) is not str or ASSET_REF.fullmatch(asset_ref) is None:
            block("DELIVERY_PRIVATE_ASSET_REF_INVALID")

    # Reuse prior real order/intent/ledger/receipt contract. A consistent
    # first-party database record is *not* independent external verification.
    money = inspect_revenue_order(order)
    if money["state"] != "internally_consistent_unverified":
        block("DELIVERY_PAYMENT_RECORDS_UNRECONCILED")
    return {
        "state": "source_preflight_passed_unverified" if not blockers else "blocked",
        "blockers": sorted(blockers),
        "source_preflight_passed": not blockers,
        "delivery_allowed": False,
        "delivery_verified": False,
        "buyer_email_verified": False,
        "private_file_bytes_verified": False,
        "independent_settlement_verified": False,
        "customer_download_receipt_verified": False,
    }


def fulfillment_preflight_snapshot(*, days=30, limit=MAX_ORDERS):
    """Anonymized bounded snapshot, with no customer/order/provider identifiers."""
    if type(days) is not int or not 1 <= days <= 90:
        raise ValueError("DELIVERY_WINDOW_INVALID")
    if type(limit) is not int or not 1 <= limit <= MAX_ORDERS:
        raise ValueError("DELIVERY_LIMIT_INVALID")
    since = timezone.now() - timedelta(days=days)
    qs = Order.objects.filter(created_at__gte=since).order_by("-created_at", "-pk")
    sampled = list(qs[:limit + 1])
    incomplete = len(sampled) > limit
    sampled = sampled[:limit]
    state_counts, causes = Counter(), Counter()
    for order in sampled:
        inspection = inspect_fulfillment_order(order)
        state_counts[inspection["state"]] += 1
        for b in inspection["blockers"]:
            causes[b] += 1
    return {
        "bot_id": "mojtaba.bot.ai",
        "read_only": True,
        "sampled_orders": len(sampled),
        "sample_complete": not incomplete,
        "days": days,
        "limit": limit,
        "states": dict(sorted(state_counts.items())),
        "blockers": dict(sorted(causes.items())),
        "delivery_enabled": False,
        "buyer_email_verified": False,
        "private_file_bytes_verified": False,
        "independent_settlement_verified": False,
        "buyer_delivery_receipt_verified": False,
        "automated_fulfillment_released": False,
    }
