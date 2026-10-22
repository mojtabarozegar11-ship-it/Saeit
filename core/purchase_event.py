"""Run the bounded business-science decision when a real payment is marked settled.

This is an event-driven *local* operating review. The authenticated payment
webhook commits the payment first, then invokes this immediately using
transaction.on_commit. No periodic scheduler, external payment mutation, or
unverified factory shipment is permitted. A single payment intent creates
at most one purchase-review receipt, even on duplicate provider callbacks.
"""
import logging

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
        if not intent or intent.status != "succeeded" or intent.order.status != "paid":
            return False
        event = PaymentWebhookEvent.objects.filter(
            provider=provider,
            event_id=event_id,
            payment_intent_id=intent.pk,
            event_type="payment.succeeded",
            status="processed",
        ).first()
        if not event:
            return False
        if not LedgerEntry.objects.filter(
            order_id=intent.order_id,
            payment_intent_id=intent.pk,
            reference=f"payment:{provider}:{event_id}",
            entry_type="payment",
            amount=intent.amount,
            currency=intent.currency,
        ).exists():
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
                "trigger": "committed_authenticated_payment.succeeded",
                "order_id": intent.order_id,
                "event_id": event_id,
                "provider": provider,
                "decision_code": diagnosis["code"],
                "decision": diagnosis["decision"],
                "next_constraint": review["next_constraint"],
                "data_scope": "local_django_only",
                "independent_cash_reconciliation": "not_verified",
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
