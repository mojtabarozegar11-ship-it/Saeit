"""Strict existing-TRX-paid-item entitlement *decision* for a future private download adapter.

Corrects a verified compatibility gap: old walletless TRX transactions have a
real finalized core credit + ready CommerceFulfillment but NO CommerceInvoice,
whereas the existing commerce download gate requires CommerceInvoice/Receipt.

This module never creates invoices/receipts, writes entitlements, broadcasts,
opens/downloads private assets, sends email, or grants a web session. A trusted
authenticated download view must supply request.user AND an independently
reviewed private-asset+license resolver. It is disabled by default until real
DB/media rollback and signed buyer routing have been independently approved.
"""
from __future__ import annotations

import json
from decimal import Decimal

from django.conf import settings

from services.mojtaba_tron_owner_receiver import APPROVED_NATIVE_TRX_RECIPIENT
from core.crown_tron_receipts import PROVIDER, verified_walletless_credit

_ALLOWED_READY = ("ready", "complete")


def verified_existing_walletless_item_access(user, item_id, *, asset_is_releasable):
    """Fail-closed boolean decision for a *specific authenticated* buyer/item.

    No special email, wallet or invoice magic. Only the persisted already paid
    walletless TRX credit, exact customer/OrderItem, irreversible refund locks,
    ready same-item CommerceFulfillment and an independently trusted exact
    private-asset resolver may jointly authorize a digital item.
    """
    if (getattr(settings, "MPW_WALLETLESS_EXISTING_PAID_DIGITAL_ACCESS_ENABLED", False)
            is not True):
        return False
    if (user is None or getattr(user, "is_authenticated", False) is not True
            or getattr(user, "is_active", False) is not True
            or type(getattr(user, "pk", None)) is not int
            or user.pk <= 0
            or type(item_id) is not int or item_id <= 0
            or not callable(asset_is_releasable)):
        return False

    from django.apps import apps
    from core.models import LedgerEntry, OrderItem

    item = OrderItem.objects.filter(
        pk=item_id, order__customer_id=user.pk
    ).select_related("order", "product", "order__payment_intent").first()
    if item is None:
        return False

    order = item.order
    product = item.product
    if (order.customer_id != user.pk
            or order.status != "paid" or order.currency != "USD"
            or order.total <= Decimal("0")
            or product.active is not True
            or product.product_type == "game_cosmetic"
            or item.currency != "USD"
            or type(item.quantity) is not int or item.quantity < 1
            or item.unit_price <= Decimal("0")):
        return False

    try:
        intent = order.payment_intent
    except Exception:
        return False
    if (intent.provider != PROVIDER or intent.status != "paid"
            or intent.order_id != order.pk
            or intent.currency != "USD"
            or intent.amount != order.total):
        return False

    try:
        doc = json.loads(intent.provider_reference)
        if (type(doc) is not dict
                or doc.get("to") != APPROVED_NATIVE_TRX_RECIPIENT
                or type(doc.get("sun")) is not int
                or doc["sun"] <= 0):
            return False
    except (ValueError, TypeError):
        return False

    if LedgerEntry.objects.filter(
        order_id=order.pk,
        entry_type__in=("refund", "reversal", "chargeback")
    ).exists():
        return False

    try:
        if verified_walletless_credit(order, intent) is not True:
            return False
        grant = apps.get_model("mpw_commerce", "CommerceFulfillment")
        field = grant._meta.get_field("item")
        related = getattr(field, "related_model", None)
        if getattr(getattr(related, "_meta", None), "label_lower", "") != "core.orderitem":
            return False
        if not grant.objects.filter(
            item_id=item.pk, status__in=_ALLOWED_READY
        ).exists():
            return False
        # This callback MUST be the existing trusted server's private-file
        # authorization, never a client-provided path or affirmative boolean.
        return asset_is_releasable(product) is True
    except Exception:
        # A missing private app/model/file must never expose an asset.
        return False
