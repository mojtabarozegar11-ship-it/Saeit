"""Paid orders trigger one bounded management review, without any scheduler."""
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from core.models import AuditLog, LedgerEntry, Order, PaymentIntent
from core.purchase_event import process_paid_purchase_review
from core.tests.test_payment_webhook import signed_post


def fixture_intent(django_user_model, label):
    owner = django_user_model.objects.create_user(
        username=f"purchase-review-{label}", password="x"
    )
    order = Order.objects.create(
        customer=owner, status="pending", total="250.00", currency="IRR"
    )
    intent = PaymentIntent.objects.create(
        order=order,
        amount=order.total,
        currency=order.currency,
        idempotency_key=f"review-{label}",
        status="ready_for_gateway",
        provider="demo",
    )
    return order, intent


@pytest.mark.django_db(transaction=True)
@override_settings(PAYMENT_WEBHOOK_SECRET="test-secret")
def test_settled_payment_immediately_creates_one_management_receipt(django_user_model):
    order, intent = fixture_intent(django_user_model, "success")
    payload = {
        "event_type": "payment.succeeded",
        "payment_intent_id": intent.pk,
        "amount": "250.00",
        "currency": "IRR",
        "provider_reference": "demo-ref",
    }
    response = signed_post(APIClient(), payload, event_id="evt-review-1")
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == "paid"

    receipts = AuditLog.objects.filter(
        action="paid_purchase_operating_review",
        target_type="PaymentIntent",
        target_id=str(intent.pk),
    )
    assert receipts.count() == 1
    assert receipts.first().after_state["factory_delivery"] == "not_connected"
    assert receipts.first().after_state["data_scope"] == "local_django_only"

    assert signed_post(APIClient(), payload, event_id="evt-review-1").status_code == 200
    assert receipts.count() == 1
    assert process_paid_purchase_review(
        intent.pk, provider="demo", event_id="evt-review-1"
    ) is False
    assert receipts.count() == 1
    assert LedgerEntry.objects.filter(order=order, entry_type="payment").count() == 1


@pytest.mark.django_db(transaction=True)
@override_settings(PAYMENT_WEBHOOK_SECRET="test-secret")
def test_failed_or_unverified_payments_do_not_trigger(django_user_model):
    order, intent = fixture_intent(django_user_model, "failed")
    result = signed_post(
        APIClient(),
        {"event_type": "payment.failed", "payment_intent_id": intent.pk},
        event_id="evt-review-fail",
    )
    assert result.status_code == 200
    assert not AuditLog.objects.filter(action="paid_purchase_operating_review").exists()
    assert process_paid_purchase_review(
        intent.pk, provider="demo", event_id="evt-review-fail"
    ) is False
    order.refresh_from_db()
    assert order.status == "pending"

    other_order, other_intent = fixture_intent(django_user_model, "invalid")
    mismatch = signed_post(
        APIClient(),
        {
            "event_type": "payment.succeeded",
            "payment_intent_id": other_intent.pk,
            "amount": "249.00",
            "currency": "IRR",
        },
        event_id="evt-review-mismatch",
    )
    assert mismatch.status_code == 409
    assert not AuditLog.objects.filter(action="paid_purchase_operating_review").exists()
    other_order.refresh_from_db()
    assert other_order.status == "pending"


@pytest.mark.django_db(transaction=True)
@override_settings(PAYMENT_WEBHOOK_SECRET="test-secret")
def test_review_error_never_reverses_committed_payment(django_user_model, monkeypatch):
    order, intent = fixture_intent(django_user_model, "deferred")

    def broken_review(*args, **kwargs):
        raise RuntimeError("simulated analysis outage")

    monkeypatch.setattr("core.purchase_event.process_paid_purchase_review", broken_review)
    response = signed_post(
        APIClient(),
        {
            "event_type": "payment.succeeded",
            "payment_intent_id": intent.pk,
            "amount": "250.00",
            "currency": "IRR",
        },
        event_id="evt-review-outage",
    )
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == "paid"
    assert LedgerEntry.objects.filter(order=order, entry_type="payment").count() == 1
