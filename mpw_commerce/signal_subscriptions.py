"""Persistent subscription terms and receipt-backed access for the existing merchant.

This is an internal adapter, not a new checkout, agent, payment processor,
marketing list or signal generator. The caller must be the existing trusted
order-creation service, before invoice issuance.
"""
from datetime import timedelta
from decimal import Decimal
import json

from django.db import transaction
from django.utils import timezone

from core.crown_tron_receipts import PROVIDER, verified_walletless_credit
from core.models import LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent
from mpw_commerce.models import CommerceFulfillment, CommerceInvoice, SignalSubscription
from services.mojtaba_signal_catalog import get_signal_plan
from services.mojtaba_tron_owner_receiver import APPROVED_NATIVE_TRX_RECIPIENT

TERMS = {"education-weekly": 1, "education-monthly": 4, "education-quarterly": 12}


class SubscriptionRejected(ValueError):
    pass


def snapshot_subscription(item_id):
    """Freeze the actual order's selected plan before issuing any invoice.

    Only a real server-owned pending subscription product may enter this path.
    The existing one-time SKU 1467 is explicitly excluded.
    """
    if type(item_id) is not int or item_id <= 0:
        raise SubscriptionRejected("Invalid order item")
    with transaction.atomic():
        item = OrderItem.objects.select_related("product").get(pk=item_id)
        order = Order.objects.select_for_update().get(pk=item.order_id)
        item = OrderItem.objects.select_for_update().select_related("product").get(pk=item_id)
        product = item.product
        meta = product.metadata if type(product.metadata) is dict else {}
        commerce = meta.get("mpw_commerce")
        plan_id = meta.get("signal_plan_id")
        if (type(plan_id) is not str or plan_id not in TERMS or product.pk == 1467
                or product.product_type != "subscription" or not product.active
                or product.currency != "USD" or meta.get("rights_cleared") is not True
                or type(commerce) is not dict or commerce.get("enabled") is not True
                or commerce.get("fulfillment") != "subscription"
                or order.status != "pending" or order.currency != "USD"
                or item.quantity != 1 or item.currency != "USD"
                or order.items.count() != 1):
            raise SubscriptionRejected("Order is not an eligible Signal Desk subscription")
        price = get_signal_plan(plan_id).price_usd
        if not item.unit_price == order.total == product.price == price:
            raise SubscriptionRejected("Order does not match the fixed plan price")
        old = SignalSubscription.objects.filter(item=item).first()
        if old is not None:
            if (old.plan_id, old.price_usd, old.term_weeks) != (plan_id, price, TERMS[plan_id]):
                raise SubscriptionRejected("Original plan terms differ")
            return old
        if (PaymentIntent.objects.filter(order=order).exists()
                or CommerceInvoice.objects.filter(order=order).exists()):
            raise SubscriptionRejected("Cannot attach a new subscription to an issued invoice")
        return SignalSubscription.objects.create(
            item=item, plan_id=plan_id, price_usd=price, term_weeks=TERMS[plan_id])


def existing_subscription_terms(item, intent):
    """Validate original pre-invoice terms for settlement, never create them."""
    sub = SignalSubscription.objects.filter(item=item).first()
    if (sub is None or item.product_id == 1467 or sub.plan_id not in TERMS
            or sub.term_weeks != TERMS[sub.plan_id]
            or sub.price_usd != get_signal_plan(sub.plan_id).price_usd
            or item.quantity != 1 or item.currency != "USD"
            or item.unit_price != sub.price_usd
            or intent.order_id != item.order_id
            or intent.amount != sub.price_usd or intent.currency != "USD"
            or intent.provider != PROVIDER or sub.created_at > intent.created_at):
        raise SubscriptionRejected("Original subscription invoice terms unavailable")
    return sub


def subscription_access(customer, item_id, *, now=None):
    """Read persisted settlement and return only the authenticated buyer's term.

    Rechecks revocation and exact receipt on each access. A queued fulfillment
    is not a delivered brief. No payment, publication or delivery is performed.
    """
    if (getattr(customer, "is_authenticated", False) is not True
            or getattr(customer, "is_active", False) is not True
            or type(getattr(customer, "pk", None)) is not int
            or type(item_id) is not int or item_id <= 0):
        return None
    current = timezone.now() if now is None else now
    if timezone.is_naive(current):
        return None
    sub = (SignalSubscription.objects.select_related("item__order")
           .filter(item_id=item_id, item__order__customer_id=customer.pk).first())
    if sub is None:
        return None
    item, order = sub.item, sub.item.order
    if (item.product_id == 1467 or sub.plan_id not in TERMS
            or sub.term_weeks != TERMS[sub.plan_id]
            or item.quantity != 1 or item.currency != "USD"
            or order.currency != "USD" or order.items.count() != 1
            or item.unit_price != sub.price_usd or order.total != sub.price_usd):
        return None
    intent = PaymentIntent.objects.filter(order=order, provider=PROVIDER).first()
    if (intent is None or CommerceInvoice.objects.filter(order=order).exists()
            or not verified_walletless_credit(order, intent)
            or LedgerEntry.objects.filter(order=order, entry_type__in=(
                "refund", "reversal", "chargeback", "debit")).exists()):
        return None
    try:
        existing_subscription_terms(item, intent)
        recipient = json.loads(intent.provider_reference)["to"]
    except (TypeError, ValueError, KeyError, SubscriptionRejected):
        return None
    if recipient != APPROVED_NATIVE_TRX_RECIPIENT:
        return None
    if not CommerceFulfillment.objects.filter(
            item=item, kind=CommerceFulfillment.Kind.SUBSCRIPTION,
            status__in=(CommerceFulfillment.Status.QUEUED,
                        CommerceFulfillment.Status.COMPLETE)).exists():
        return None
    event = PaymentWebhookEvent.objects.get(
        payment_intent=intent, provider=PROVIDER, event_type="tron_finalized",
        status="processed")
    start = event.created_at
    end = start + timedelta(weeks=sub.term_weeks)
    if not sub.created_at <= start <= current < end:
        return None
    return {"agent": "mojtaba.bot.ai", "plan_id": sub.plan_id,
            "starts_at": start, "expires_at": end, "term_weeks": sub.term_weeks,
            "current_week": (current - start).days // 7 + 1}
