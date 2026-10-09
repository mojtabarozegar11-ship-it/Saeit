"""Exercise payment webhook authentication and malformed-payload behavior without gateway access."""
import hashlib
import hmac
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory
from core.api import PaymentWebhookViewSet
from core.models import PaymentWebhookEvent, PaymentIntent, Order, LedgerEntry


@override_settings(PAYMENT_WEBHOOK_SECRET="ci-test-only-webhook-secret")
class PaymentWebhookValidationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PaymentWebhookViewSet.as_view({"post": "create"})

    def request(self, body, signature=None, provider="test-gateway", event_id="evt-1"):
        if signature is None:
            signature = hmac.new(
                b"ci-test-only-webhook-secret", body, hashlib.sha256
            ).hexdigest()
        request = self.factory.post(
            "/api/payment-webhooks/", data=body,
            content_type="application/json",
            HTTP_X_PAYMENT_PROVIDER=provider,
            HTTP_X_PAYMENT_EVENT_ID=event_id,
            HTTP_X_PAYMENT_SIGNATURE=signature,
        )
        return self.view(request)

    def test_invalid_signature_is_rejected(self):
        response = self.request(b'{"event_type":"payment.succeeded"}', signature="bad")
        self.assertEqual(response.status_code, 401)

    def test_validly_signed_json_array_is_rejected(self):
        response = self.request(b'[]')
        self.assertEqual(response.status_code, 400)

    def test_validly_signed_json_null_is_rejected(self):
        response = self.request(b'null')
        self.assertEqual(response.status_code, 400)

    def test_validly_signed_malformed_json_is_rejected(self):
        response = self.request(b'{invalid')
        self.assertEqual(response.status_code, 400)

    def test_oversized_headers_are_rejected(self):
        response = self.request(b'{}', provider="x" * 51)
        self.assertEqual(response.status_code, 400)
        response = self.request(b'{}', event_id="e" * 129)
        self.assertEqual(response.status_code, 400)

    def test_reused_event_id_with_different_payload_is_rejected(self):
        original = b'{"event_type":"payment.failed","payment_intent_id":1}'
        PaymentWebhookEvent.objects.create(
            provider='test-gateway', event_id='evt-1', event_type='payment.failed',
            payload_hash=hashlib.sha256(original).hexdigest(), status='processed',
        )
        self.assertEqual(self.request(original).status_code, 200)
        changed = b'{"event_type":"payment.succeeded","payment_intent_id":1}'
        self.assertEqual(self.request(changed).status_code, 409)
        self.assertEqual(PaymentWebhookEvent.objects.count(), 1)

    def test_signed_success_settles_order_and_creates_one_ledger_entry(self):
        user = get_user_model().objects.create_user(username='mpw_webhook_customer', password='test-only')
        order = Order.objects.create(customer=user, total=Decimal('12.50'), currency='USD', status='pending')
        intent = PaymentIntent.objects.create(
            order=order, amount=Decimal('12.50'), currency='USD',
            idempotency_key='webhook-success-key', provider='test-gateway', status='gateway_pending',
        )
        import json
        payload = json.dumps({
            'event_type': 'payment.succeeded', 'payment_intent_id': intent.pk,
            'amount': '12.50', 'currency': 'USD', 'provider_reference': 'gateway-ref-1',
        }).encode()
        first = self.request(payload)
        self.assertEqual(first.status_code, 200)
        intent.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(intent.status, 'succeeded')
        self.assertEqual(order.status, 'paid')
        self.assertEqual(LedgerEntry.objects.filter(payment_intent=intent, entry_type='payment').count(), 1)
        self.assertEqual(self.request(payload).status_code, 200)
        self.assertEqual(LedgerEntry.objects.filter(payment_intent=intent, entry_type='payment').count(), 1)

    def test_failed_event_cannot_reverse_succeeded_payment(self):
        user = get_user_model().objects.create_user(username='mpw_webhook_paid', password='test-only')
        order = Order.objects.create(customer=user, total=Decimal('7.00'), currency='USD', status='paid')
        intent = PaymentIntent.objects.create(
            order=order, amount=Decimal('7.00'), currency='USD',
            idempotency_key='webhook-paid-key', provider='test-gateway', status='succeeded',
        )
        import json
        payload = json.dumps({
            'event_type': 'payment.failed', 'payment_intent_id': intent.pk,
        }).encode()
        response = self.request(payload, event_id='evt-late-failure')
        self.assertEqual(response.status_code, 409)
        intent.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(intent.status, 'succeeded')
        self.assertEqual(order.status, 'paid')
        self.assertFalse(LedgerEntry.objects.exists())

    def test_signed_success_rejects_order_intent_amount_divergence(self):
        user = get_user_model().objects.create_user(username='mpw_webhook_mismatch', password='test-only')
        order = Order.objects.create(customer=user, total=Decimal('18.00'), currency='USD', status='pending')
        intent = PaymentIntent.objects.create(
            order=order, amount=Decimal('12.00'), currency='USD',
            idempotency_key='webhook-mismatch-key', provider='test-gateway', status='gateway_pending',
        )
        import json
        payload = json.dumps({
            'event_type': 'payment.succeeded', 'payment_intent_id': intent.pk,
            'amount': '12.00', 'currency': 'USD',
        }).encode()
        response = self.request(payload, event_id='evt-amount-mismatch')
        self.assertEqual(response.status_code, 409)
        order.refresh_from_db()
        intent.refresh_from_db()
        self.assertEqual(order.status, 'pending')
        self.assertEqual(intent.status, 'gateway_pending')
        self.assertFalse(LedgerEntry.objects.exists())
