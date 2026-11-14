"""Read-only, evidence-level revenue reconciliation for sole mojtaba.bot.ai.

This module NEVER attests externally settled cash from first-party database
records alone. A signed webhook and an internally consistent chain receipt
are evidence to reconcile, not independent bank/chain settlement proof.
No writes, provider requests, purchases, payouts or email.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

from .models import LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent
from .crown_tron_receipts import (
    PROVIDER as WALLETLESS_PROVIDER,
    verified_walletless_credit,
)

MAX_ORDERS = 200
WINDOW_DAYS = 30
CURRENCY = re.compile(r"[A-Z]{3,10}\Z")
HEX_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
REF = re.compile(r"payment:[a-f0-9]{64}\Z")
BAD_PROVIDERS = frozenset({"", "demo", "not_configured", "test", "sandbox"})
REVERSALS = frozenset({"refund", "reversal", "chargeback"})


def _money(value):
    """Only finite nonnegative exact decimal quantities are reportable."""
    if type(value) is not Decimal or not value.is_finite() or value < 0:
        return None
    return value


def inspect_revenue_order(order):
    """Report account-record consistency; NEVER return verified revenue.

    The 20-point source gate is intentionally independent of webhook status.
    No order ID, buyer email, provider reference, or transaction address is
    emitted from this function; such details stay in the protected database.
    """
    reasons = []
    def reject(code):
        if code not in reasons:
            reasons.append(code)

    if not isinstance(order, Order) or type(getattr(order, "pk", None)) is not int:
        return {
            "state": "invalid_record", "reasons": ["ORDER_INVALID"],
            "currency": None, "nominal_amount": None,
            "externally_settled_cash": None, "settlement_verified": False,
        }

    if order.status != "paid":
        reject("ORDER_NOT_PAID")
    value = _money(order.total)
    if value is None or value <= 0:
        reject("ORDER_AMOUNT_INVALID")
    if type(order.currency) is not str or CURRENCY.fullmatch(order.currency) is None:
        reject("ORDER_CURRENCY_INVALID")

    items = list(OrderItem.objects.filter(order_id=order.pk).order_by("pk")[:102])
    if not items:
        reject("ORDER_ITEMS_MISSING")
    if len(items) > 100:
        reject("ORDER_ITEM_LIMIT_EXCEEDED")
    item_total = Decimal("0")
    for item in items:
        if type(item.quantity) is not int or not 1 <= item.quantity <= 100:
            reject("ORDER_ITEM_QUANTITY_INVALID")
        price = _money(item.unit_price)
        if price is None or price <= 0:
            reject("ORDER_ITEM_PRICE_INVALID")
        if item.currency != order.currency:
            reject("ORDER_ITEM_CURRENCY_MISMATCH")
        if price is not None and type(item.quantity) is int:
            item_total += price * item.quantity
    if value is not None and item_total != value:
        reject("ORDER_LINE_SUM_MISMATCH")

    intent = PaymentIntent.objects.filter(order_id=order.pk).first()
    provider = None
    if intent is None:
        reject("PAYMENT_INTENT_MISSING")
    else:
        if intent.order_id != order.pk:
            reject("PAYMENT_INTENT_ORDER_MISMATCH")
        if _money(intent.amount) is None or intent.amount != value:
            reject("PAYMENT_AMOUNT_MISMATCH")
        if intent.currency != order.currency:
            reject("PAYMENT_CURRENCY_MISMATCH")
        provider = intent.provider
        if type(provider) is not str or provider.casefold() in BAD_PROVIDERS:
            reject("PROVIDER_NOT_INDEPENDENTLY_CONFIGURED")
        if (type(intent.idempotency_key) is not str
                or not 8 <= len(intent.idempotency_key) <= 128):
            reject("PAYMENT_IDEMPOTENCY_INVALID")
        if (type(intent.provider_reference) is not str
                or not intent.provider_reference.strip()
                or len(intent.provider_reference) > 200):
            reject("PROVIDER_REFERENCE_MISSING")
        if intent.provider_reference and PaymentIntent.objects.filter(
            provider=intent.provider, provider_reference=intent.provider_reference
        ).exclude(pk=intent.pk).exists():
            reject("PROVIDER_REFERENCE_REUSED")

    reversals = LedgerEntry.objects.filter(
        order_id=order.pk, entry_type__in=REVERSALS,
    ).exists()
    if reversals:
        reject("PAYMENT_REVERSAL_PRESENT")

    if intent is not None and provider == WALLETLESS_PROVIDER:
        if not verified_walletless_credit(order, intent):
            reject("TRON_INTERNAL_RECEIPT_INCONSISTENT")
    elif intent is not None:
        if intent.status != "succeeded":
            reject("PAYMENT_INTENT_NOT_SUCCEEDED")
        payments = list(LedgerEntry.objects.filter(
            order_id=order.pk, entry_type="payment",
        ).order_by("pk")[:2])
        if len(payments) != 1:
            reject("PAYMENT_LEDGER_NOT_UNIQUE")
        else:
            payment = payments[0]
            if (payment.payment_intent_id != intent.pk
                    or _money(payment.amount) != value
                    or payment.currency != order.currency
                    or REF.fullmatch(payment.reference or "") is None):
                reject("PAYMENT_LEDGER_MISMATCH")
            meta = payment.metadata if type(payment.metadata) is dict else {}
            events = list(PaymentWebhookEvent.objects.filter(
                payment_intent_id=intent.pk,
                provider=intent.provider,
                event_type="payment.succeeded",
                status="processed",
            ).order_by("pk")[:2])
            if len(events) != 1:
                reject("WEBHOOK_EVENT_NOT_UNIQUE")
            else:
                event = events[0]
                if (event.processed_at is None
                        or type(event.payload_hash) is not str
                        or HEX_DIGEST.fullmatch(event.payload_hash) is None):
                    reject("WEBHOOK_EVIDENCE_INCOMPLETE")
                if (meta.get("provider") != intent.provider
                        or meta.get("event_id") != event.event_id):
                    reject("WEBHOOK_LEDGER_BINDING_MISMATCH")

    # "Internally consistent" is not independent third-party settlement.
    state = (
        "not_paid" if order.status != "paid" else
        "requires_reconciliation" if reasons else
        "internally_consistent_unverified"
    )
    return {
        "state": state,
        "reasons": sorted(reasons),
        "currency": order.currency if CURRENCY.fullmatch(str(order.currency)) else None,
        "nominal_amount": str(value) if value is not None else None,
        "externally_settled_cash": None,
        "settlement_verified": False,
    }


def revenue_evidence_snapshot(*, days=WINDOW_DAYS, max_orders=MAX_ORDERS):
    """Bounded, anonymized, read-only 30-day audit for the one master bot.

    If row count exceeds the bound, the snapshot says incomplete and never
    extrapolates its sample into total sales or a total income statement.
    """
    if type(days) is not int or not 1 <= days <= 90:
        raise ValueError("REVENUE_WINDOW_INVALID")
    if type(max_orders) is not int or not 1 <= max_orders <= MAX_ORDERS:
        raise ValueError("REVENUE_SAMPLE_BOUND_INVALID")
    since = timezone.now() - timedelta(days=days)
    rows = list(Order.objects.filter(created_at__gte=since).order_by(
        "-created_at", "-pk"
    )[:max_orders + 1])
    truncated = len(rows) > max_orders
    rows = rows[:max_orders]
    counts = Counter()
    reasons = Counter()
    nominal_by_currency = {}
    for order in rows:
        record = inspect_revenue_order(order)
        counts[record["state"]] += 1
        for code in record["reasons"]:
            reasons[code] += 1
        # A nominal reconciled value is never labelled collected income.
        if (record["state"] == "internally_consistent_unverified"
                and record["nominal_amount"] is not None
                and record["currency"] is not None):
            ccy = record["currency"]
            nominal_by_currency[ccy] = nominal_by_currency.get(ccy, Decimal("0")) + Decimal(
                record["nominal_amount"]
            )
    return {
        "bot_id": "mojtaba.bot.ai",
        "read_only": True,
        "window_days": days,
        "sampled_order_count": len(rows),
        "sample_complete": not truncated,
        "sample_limit": max_orders,
        "order_states": dict(sorted(counts.items())),
        "blocker_codes": dict(sorted(reasons.items())),
        "internally_consistent_nominal_not_cash": {
            key: str(value) for key, value in sorted(nominal_by_currency.items())
        },
        "externally_settled_cash": None,
        "verified_net_profit": None,
        "settlement_provider_independently_checked": False,
        "live_delivery_verified": False,
        "revenue_claim_allowed": False,
    }
