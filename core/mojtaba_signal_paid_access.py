"""ONE mojtaba.bot.ai signal entitlement backed by a real settled native-TRX order.

A verified signal source is NOT a paid subscription, a backtest is NOT a
realized-return guarantee, and a paid order is NOT authority to execute trades.
This module is the internal read-only buyer-entitlement decision that the one
company bot may consume later. No HTTP endpoint, sender, broker order,
notification or wallet transfer is implemented here.
"""
from dataclasses import dataclass
from datetime import timedelta
import re

from django.conf import settings
from django.http import Http404
from django.utils import timezone

from .models import LedgerEntry, OrderItem, PaymentWebhookEvent
from .tron_gateway_verify import TX_PATTERN

CANONICAL_BOT = "mojtaba.bot.ai"
MONTHLY_DAYS = 30
PLAN_SKUS = frozenset((
    "moj-signals-standard",
    "moj-signals-plus",
    "moj-signals-professional",
))
REQUIRED_APPROVALS = (
    "independent_signal_history_audited",
    "signal_loss_fee_disclosures_approved",
    "signal_jurisdiction_authorized",
    "signal_buyer_terms_approved",
    "signal_delivery_capacity_verified",
    "signal_cancellation_refund_ready",
)
REVOKING_ENTRY_TYPES = frozenset(("refund", "reversal", "chargeback", "debit"))


def approved_signal_offer_snapshot(metadata, kind):
    """Immutable original-order SKU/term snapshot or fail-closed refusal.

    A merchant's Product metadata can change after a purchase; buyer rights
    use the invoice+credit snapshots instead of current catalog price.
    """
    if type(metadata) is not dict:
        raise ValueError("Product metadata missing")
    sku = metadata.get("mojtaba_signal_plan_sku")
    if sku is None:
        return "", 0
    if (type(sku) is not str or sku not in PLAN_SKUS or kind != "service"
            or metadata.get("signal_term_days") != MONTHLY_DAYS
            or any(metadata.get(key) is not True for key in REQUIRED_APPROVALS)):
        raise ValueError("Signal product lacks independent release approvals")
    return sku, MONTHLY_DAYS


@dataclass(frozen=True)
class PaidSignalAccess:
    permitted: bool
    reason: str
    bot_identity: str = CANONICAL_BOT
    sku: str | None = None
    issuer_host: str | None = None
    expires_at_iso: str | None = None
    sends_messages: bool = False
    executes_trades: bool = False
    creates_orders: bool = False


def paid_signal_access(request, invoice_id, sku, *, now=None):
    """Read-only policy: exact buyer email session + finalized ledger evidence.

    The internal bot must first verify a buyer's original email claim through
    gateway session/recovery. Cross-origin sessions are NOT inferred or shared.
    A separate approved dispatcher and actual signal history are required
    before any alert is sent.
    """
    denied = lambda reason: PaidSignalAccess(False, reason)
    if getattr(settings, "MOJ_SIGNAL_BOT_PAID_DELIVERY_ENABLED", False) is not True:
        return denied("bot_signal_paid_delivery_not_approved")
    if type(sku) is not str or sku not in PLAN_SKUS:
        return denied("unknown_canonical_signal_plan")
    if now is None:
        now = timezone.now()
    if (not hasattr(now, "utcoffset") or now.utcoffset() is None):
        return denied("independent_aware_clock_required")
    try:
        # No explicit user-provided host, merchant, buyer or wallet is trusted.
        from .tron_gateway_web import _host, _owner, PROVIDER
        host, _ = _host(request)
        invoice = _owner(request, invoice_id, host)
    except (Http404, TypeError, ValueError, AttributeError):
        return denied("buyer_email_claim_or_exact_merchant_missing")
    intent, order = invoice.payment_intent, invoice.order
    if (invoice.status != "paid" or invoice.fulfillment_kind != "service"
            or invoice.signal_sku_snapshot != sku
            or invoice.signal_term_days_snapshot != MONTHLY_DAYS
            or not invoice.merchant_tenant_id or not invoice.receiver
            or not invoice.txid or not invoice.proof_digest
            or TX_PATTERN.fullmatch(invoice.txid) is None
            or intent.status != "paid" or intent.provider != PROVIDER
            or intent.provider_reference != invoice.txid
            or intent.order_id != order.pk or order.status != "paid"
            or invoice.verified_at is None or invoice.verified_at.utcoffset() is None):
        return denied("paid_merchant_signal_order_incomplete")
    expiry = invoice.verified_at + timedelta(days=MONTHLY_DAYS)
    if not invoice.verified_at <= now < expiry:
        return denied("signal_subscription_not_current")
    items = list(OrderItem.objects.filter(order=order).select_related("product")[:2])
    if len(items) != 1 or items[0].quantity != 1 or items[0].currency != order.currency:
        return denied("subscription_item_not_unique")
    if items[0].unit_price != order.total:
        return denied("subscription_order_total_mismatch")
    product = items[0].product
    md = product.metadata if type(product.metadata) is dict else {}
    if md.get("rights_revoked") is True or md.get("delivery_suspended") is True:
        return denied("signal_rights_or_delivery_suspended")
    events = PaymentWebhookEvent.objects.filter(
        provider=PROVIDER, event_id=invoice.txid, payment_intent=intent,
        event_type="tron_finalized", status="processed",
        payload_hash=invoice.proof_digest,
    ).count()
    credits = list(LedgerEntry.objects.filter(
        order=order, payment_intent=intent, entry_type="credit",
        reference="tron-mainnet:" + invoice.txid,
        amount=order.total, currency=order.currency,
    )[:2])
    if events != 1 or len(credits) != 1:
        return denied("finalized_receipt_and_unique_credit_missing")
    data = credits[0].metadata
    if (type(data) is not dict or data.get("network") != "tron-mainnet"
            or data.get("asset") != "TRX"
            or data.get("amount_sun") != invoice.amount_sun
            or data.get("receiver") != invoice.receiver
            or data.get("merchant_tenant_id") != invoice.merchant_tenant_id
            or data.get("source_host") != invoice.source_host
            or data.get("proof_digest") != invoice.proof_digest
            or data.get("signal_sku_snapshot") != sku
            or data.get("signal_term_days_snapshot") != MONTHLY_DAYS):
        return denied("subscription_not_bound_to_original_paid_invoice")
    if LedgerEntry.objects.filter(
            order=order, payment_intent=intent,
            entry_type__in=REVOKING_ENTRY_TYPES).exists():
        return denied("subscription_payment_reversed_or_refunded")
    # Current product metadata never grants buyer rights by itself. The
    # audited payment+invoice snapshots grant read-only plan access.
    return PaidSignalAccess(
        True, "verified_current_single_bot_subscription",
        sku=sku, issuer_host=host, expires_at_iso=expiry.isoformat(),
    )
