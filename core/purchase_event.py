"""Run the bounded business-science decision when a real payment is marked settled.

This is an event-driven *local* operating review. The authenticated payment
webhook commits the payment first, then invokes this immediately using
transaction.on_commit. No periodic scheduler, external payment mutation, or
unverified factory shipment is permitted. A single payment intent creates
at most one purchase-review receipt, even on duplicate provider callbacks.
"""
import logging
import re

from django.db import transaction

from core.business_scientist import build_business_science_plan
from core.management.commands.business_operating_review import collect_management_metrics
from core.models import AuditLog, LedgerEntry, PaymentIntent, PaymentWebhookEvent


_LOG = logging.getLogger(__name__)
_ACTION = "paid_purchase_operating_review"


def process_paid_purchase_review(payment_intent_id, *, provider, event_id):
    """Execute once for the settled order; fail closed on unverified states.

    The intent row lock serializes callbacks, while the upstream
    PaymentWebhookEvent unique constraint protects provider/event identity.
    """
    with transaction.atomic():
        intent = (
            PaymentIntent.objects.select_for_update()
            .select_related("order")
            .filter(pk=payment_intent_id, provider=provider)
            .first()
        )
        if not intent or intent.order.status != "paid":
            return False
        event = PaymentWebhookEvent.objects.filter(
            provider=provider,
            event_id=event_id,
            payment_intent_id=intent.pk,
            status="processed",
        ).first()
        if not event:
            return False

        if event.event_type == "payment.succeeded" and intent.status == "succeeded":
            # The core webhook owns an authenticated success event and a
            # matching internal ledger entry. This is NOT a chain proof.
            proof_accepted = LedgerEntry.objects.filter(
                order_id=intent.order_id,
                payment_intent_id=intent.pk,
                reference=f"payment:{provider}:{event_id}",
                entry_type="payment",
                amount=intent.amount,
                currency=intent.currency,
            ).exists()
            proof_kind = "signed_provider_callback"
        elif (event.event_type == "tron_finalized"
              and provider == "mpw_walletless_trx_v1"
              and intent.status == "paid"
              and re.fullmatch(r"[0-9a-f]{64}", event_id)
              and re.fullmatch(r"[0-9a-f]{64}", event.payload_hash or "")):
            # Only the independently validated TRON settlement adapter may
            # write this receipt. Recheck its ledger-to-evidence binding.
            ledger = LedgerEntry.objects.filter(
                order_id=intent.order_id,
                payment_intent_id=intent.pk,
                reference=f"walletless:tron-mainnet:{event_id}",
                entry_type="credit",
                amount=intent.amount,
                currency=intent.currency,
            ).first()
            md = ledger.metadata if ledger and isinstance(ledger.metadata, dict) else {}
            proof_accepted = bool(
                ledger and md.get("payment_method") == provider
                and md.get("network") == "tron-mainnet"
                and md.get("tx_hash") == event_id
                and md.get("evidence_digest") == event.payload_hash
                and md.get("walletless_receipt_event_id") == event.pk
            )
            proof_kind = "dual_node_tron_settlement_receipt"
        else:
            return False
        if not proof_accepted:
            return False

        if AuditLog.objects.filter(
            action=_ACTION,
            target_type="PaymentIntent",
            target_id=str(intent.pk),
        ).exists():
            return False

        plan = build_business_science_plan(collect_management_metrics())
        diagnosis = plan["diagnosis"]
        review = plan["review"]
        AuditLog.objects.create(
            actor_type="system",
            actor_id="business-purchase-event",
            action=_ACTION,
            target_type="PaymentIntent",
            target_id=str(intent.pk),
            after_state={
                "trigger": "committed_paid_order",
                "proof_kind": proof_kind,
                "order_id": intent.order_id,
                "event_id": event_id,
                "provider": provider,
                "decision_code": diagnosis["code"],
                "decision": diagnosis["decision"],
                "next_constraint": review["next_constraint"],
                "data_scope": "local_django_only",
                "independent_cash_reconciliation": "provider_or_chain_receipt_only_not_cash_reconciliation",
                "factory_delivery": "not_connected",
            },
            trace_id=f"paid-purchase-review-{intent.pk}",
        )
        return True


def schedule_paid_purchase_review(payment_intent_id, *, provider, event_id):
    """Execute after payment commit, without affecting its HTTP settlement."""
    def run():
        try:
            process_paid_purchase_review(
                payment_intent_id, provider=provider, event_id=event_id
            )
        except Exception:
            # A diagnostic failure must never reverse a committed customer
            # payment or cause a provider retry to double-settle it.
            _LOG.exception("Paid-purchase management review failed")

    transaction.on_commit(run)


def process_paid_order_review(order_id):
    """Handle any paid-order transition backed by a recognized durable receipt.

    This is an idempotent local observer; it does not dispatch to the VPS
    factory or grant buyer access. Unknown payment rails are left untouched.
    """
    events = (
        PaymentWebhookEvent.objects.filter(
            payment_intent__order_id=order_id,
            event_type__in=("payment.succeeded", "tron_finalized"),
            status="processed",
        )
        .order_by("pk")
        .values("payment_intent_id", "provider", "event_id")[:8]
    )
    for event in events:
        if process_paid_purchase_review(
            event["payment_intent_id"],
            provider=event["provider"],
            event_id=event["event_id"],
        ):
            return True
    return False


def schedule_paid_order_review(order_id, *, using=None):
    """Run immediately upon the commit of a paid Order save."""
    def run():
        try:
            process_paid_order_review(order_id)
        except Exception:
            _LOG.exception("Paid-order management signal failed")

    transaction.on_commit(run, using=using)
