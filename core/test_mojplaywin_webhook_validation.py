"""Exercise payment webhook authentication and malformed-payload behavior without gateway access."""
import hashlib
import hmac
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory
from core.api import PaymentWebhookViewSet


@override_settings(PAYMENT_WEBHOOK_SECRET="ci-test-only-webhook-secret")
class PaymentWebhookValidationTests(SimpleTestCase):
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
