import hashlib
import hmac
import json

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from core.models import LedgerEntry, Order, PaymentIntent, PaymentWebhookEvent


def signed_post(client, payload, provider="demo", event_id="evt-1", secret="test-secret"):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.generic(
        "POST",
        "/api/payment-webhooks/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYMENT_PROVIDER=provider,
        HTTP_X_PAYMENT_EVENT_ID=event_id,
        HTTP_X_PAYMENT_SIGNATURE=signature,
    )


@pytest.mark.django_db
@override_settings(PAYMENT_WEBHOOK_SECRET="test-secret")
def test_signed_success_webhook_settles_once(django_user_model):
    owner = django_user_model.objects.create_user(
        username="webhook-owner", password="x"
    )
    order = Order.objects.create(
        customer=owner, status="pending", total="250.00", currency="IRR"
    )
    intent = PaymentIntent.objects.create(
        order=order,
        amount=order.total,
        currency=order.currency,
        idempotency_key="webhook-pay-1",
        status="ready_for_gateway",
        provider="demo",
    )
    client = APIClient()
    payload = {
        "event_type": "payment.succeeded",
        "payment_intent_id": intent.pk,
        "amount": "250.00",
        "currency": "IRR",
        "provider_reference": "demo-ref-1",
    }

    first = signed_post(client, payload)
    assert first.status_code == 200
    intent.refresh_from_db()
    order.refresh_from_db()
    assert intent.status == "succeeded"
    assert order.status == "paid"
    assert LedgerEntry.objects.filter(reference="payment:demo:evt-1").count() == 1

    second = signed_post(client, payload)
    assert second.status_code == 200
    assert PaymentWebhookEvent.objects.filter(provider="demo", event_id="evt-1").count() == 1
    assert LedgerEntry.objects.filter(reference="payment:demo:evt-1").count() == 1


@pytest.mark.django_db
@override_settings(PAYMENT_WEBHOOK_SECRET="test-secret")
def test_webhook_rejects_bad_signature(django_user_model):
    owner = django_user_model.objects.create_user(username="bad-sign", password="x")
    order = Order.objects.create(customer=owner, status="pending", total="100.00", currency="IRR")
    intent = PaymentIntent.objects.create(
        order=order, amount=order.total, currency=order.currency,
        idempotency_key="bad-sign-1", status="ready_for_gateway", provider="demo"
    )
    raw = json.dumps({
        "event_type": "payment.succeeded", "payment_intent_id": intent.pk,
        "amount": "100.00", "currency": "IRR"
    }).encode()
    response = APIClient().generic(
        "POST", "/api/payment-webhooks/", data=raw,
        content_type="application/json",
        HTTP_X_PAYMENT_PROVIDER="demo",
        HTTP_X_PAYMENT_EVENT_ID="evt-bad",
        HTTP_X_PAYMENT_SIGNATURE="invalid",
    )
    assert response.status_code == 401
    intent.refresh_from_db()
    assert intent.status == "ready_for_gateway"


@pytest.mark.django_db
@override_settings(PAYMENT_WEBHOOK_SECRET="test-secret")
def test_webhook_rejects_amount_mismatch(django_user_model):
    owner = django_user_model.objects.create_user(username="mismatch", password="x")
    order = Order.objects.create(customer=owner, status="pending", total="100.00", currency="IRR")
    intent = PaymentIntent.objects.create(
        order=order, amount=order.total, currency=order.currency,
        idempotency_key="mismatch-1", status="ready_for_gateway", provider="demo"
    )
    response = signed_post(
        APIClient(),
        {
            "event_type": "payment.succeeded", "payment_intent_id": intent.pk,
            "amount": "99.00", "currency": "IRR"
        },
        event_id="evt-mismatch",
    )
    assert response.status_code == 409
    intent.refresh_from_db()
    order.refresh_from_db()
    assert intent.status == "ready_for_gateway"
    assert order.status == "pending"


@pytest.mark.django_db
@override_settings(PAYMENT_WEBHOOK_SECRET="")
def test_webhook_requires_configured_secret(django_user_model):
    response = APIClient().post("/api/payment-webhooks/", {}, format="json")
    assert response.status_code == 401
