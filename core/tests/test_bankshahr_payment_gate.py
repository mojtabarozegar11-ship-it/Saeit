"""Prevent unverified Shahr Bank payment events from settling orders."""
import hashlib
import hmac

from django.test import SimpleTestCase, override_settings


@override_settings(PAYMENT_WEBHOOK_SECRET="test-webhook-secret")
class BankShahrPaymentGateTests(SimpleTestCase):
    def post_event(self, provider, body, valid_signature=True):
        signature = hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
        if not valid_signature:
            signature = "incorrect-signature"
        return self.client.post(
            "/api/payment-webhooks/",
            data=body,
            content_type="application/json",
            HTTP_X_PAYMENT_PROVIDER=provider,
            HTTP_X_PAYMENT_EVENT_ID="unit-event-001",
            HTTP_X_PAYMENT_SIGNATURE=signature,
        )

    def test_bank_shahr_valid_generic_hmac_must_never_credit_a_sale(self):
        body = b'{"event_type":"payment.succeeded","payment_intent_id":1,"amount":"100.00","currency":"IRR"}'
        for name in ("bankshahr", "Bank_Shahr", "shahr-bank", "bankshahripg"):
            with self.subTest(provider=name):
                response = self.post_event(name, body)
                self.assertEqual(response.status_code, 503)
                self.assertIn("official PSP verification", response.json()["detail"])

    def test_invalid_signature_is_rejected_before_gateway_gate(self):
        response = self.post_event("bankshahr", b"{}", valid_signature=False)
        self.assertEqual(response.status_code, 401)

    def test_other_gateway_retains_its_existing_validation_path(self):
        response = self.post_event("other-provider", b"not-valid-json")
        self.assertEqual(response.status_code, 400)
