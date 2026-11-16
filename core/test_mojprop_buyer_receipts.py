"""Real CSRF intake -> bearer receipt -> privacy-preserving review status."""
import json
from unittest.mock import patch

from django.core import signing
from django.test import Client, TestCase
from django.urls import reverse

from core.models import MojPropRequest
from core.mojprop_receipts import make_receipt_token, verify_receipt_token


class MojPropBuyerReceiptTests(TestCase):
    def setUp(self):
        self.browser = Client(enforce_csrf_checks=True)
        self.token = self.browser.get("/moj-prop-intake/").json()["csrf_token"]

    def make_lead(self):
        payload = {
            "name": "Buyer with a real need", "email": "buyer@mailhost.example.org",
            "service": "audit", "horizon": "week",
            "notes": "Please review actual customer scope, privacy and deliverable controls.",
            "consent": True, "website": "",
        }
        response = self.browser.post(
            "/moj-prop-intake/", data=json.dumps(payload),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_success_receipt_contains_unpredictable_signed_token_no_buyer_pii(self):
        result = self.make_lead()
        self.assertEqual(verify_receipt_token(result["receipt_token"]), result["request_id"])
        self.assertNotIn("buyer@", result["receipt_token"])
        self.assertNotIn("Buyer with", result["receipt_token"])

    def test_signed_receipt_tracks_real_manual_review_status_without_pii(self):
        result = self.make_lead()
        MojPropRequest.objects.filter(request_id=result["request_id"]).update(status="reviewing")
        response = self.browser.get(
            reverse("mojprop_receipt_status"), {"receipt_token": result["receipt_token"]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "reviewing")
        self.assertIn("Being reviewed", response.json()["stage"])
        self.assertEqual(response.json()["payment_status"], "not_collected_by_this_service")
        self.assertNotIn("email", response.json())
        self.assertNotIn("notes", response.json())
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

    def test_unverified_or_mutated_receipt_cannot_reveal_customer_status(self):
        result = self.make_lead()
        for token in ("", "guessed", result["receipt_token"] + "broken", "x" * 1000):
            with self.subTest(token=token[:24]):
                response = self.browser.get("/moj-prop-status/", {"receipt_token": token})
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("status", response.json())

    def test_duplicate_bearer_receipts_are_rejected_even_with_valid_last_token(self):
        result = self.make_lead()
        response = self.browser.get(
            "/moj-prop-status/?receipt_token=invalid&receipt_token="
            + result["receipt_token"]
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("status", response.json())
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_invalid_token_has_same_no_cache_and_no_referrer_headers(self):
        response = self.browser.get("/moj-prop-status/", {"receipt_token": "invalid"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_expired_receipt_requires_private_manual_recovery(self):
        result = self.make_lead()
        with patch.object(signing.TimestampSigner, "unsign", side_effect=signing.SignatureExpired("old")):
            response = self.browser.get("/moj-prop-status/", {"receipt_token": result["receipt_token"]})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("email", response.json())

    def test_private_post_receipt_is_read_only_and_requires_json(self):
        result = self.make_lead()
        # A browser-encoded form is not a trusted bearer JSON envelope.
        malformed = self.browser.post(
            "/moj-prop-status/", {"receipt_token": result["receipt_token"]},
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(malformed.status_code, 400)
        response = self.browser.post(
            "/moj-prop-status/",
            data=json.dumps({"receipt_token": result["receipt_token"]}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "not_collected_by_this_service")
        self.assertEqual(
            MojPropRequest.objects.get(request_id=result["request_id"]).status,
            "new",
        )


    def test_same_receipt_is_bound_to_one_actual_request(self):
        result = self.make_lead()
        forged = make_receipt_token("MOJPROP-20000101-00000000")
        self.assertEqual(
            self.browser.get("/moj-prop-status/", {"receipt_token": forged}).status_code, 404
        )
        self.assertEqual(
            self.browser.get("/moj-prop-status/", {"receipt_token": result["receipt_token"]}).status_code,
            200,
        )

    def test_keyed_receipt_round_trips_status_without_duplicate_intake(self):
        data = {
            "name": "Manual review buyer", "email": "manual@buyer.example.org",
            "service": "brief", "horizon": "week",
            "notes": "Please review this dated educational scope for me.",
            "consent": True, "website": "",
            "idempotency_key": "12345678-1234-4234-8234-123456789abc",
        }
        def submit():
            return self.browser.post(
                "/moj-prop-intake/", data=json.dumps(data),
                content_type="application/json", HTTP_X_CSRFTOKEN=self.token,
            )
        first = submit()
        self.assertEqual(first.status_code, 201)
        same = submit()
        self.assertEqual(same.status_code, 200)
        self.assertEqual(same.json()["request_id"], first.json()["request_id"])
        self.assertEqual(verify_receipt_token(same.json()["receipt_token"]),
                         first.json()["request_id"])
        status = self.browser.post(
            "/moj-prop-status/",
            data=json.dumps({"receipt_token": same.json()["receipt_token"]}),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["request_id"], first.json()["request_id"])
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_old_and_keyed_receipt_shapes_preserve_strict_validation(self):
        for identifier in (
            "MOJPROP-20261116-ABCDEF12",
            "MOJPROP-ID-ABCDEF0123456789ABCDEF01",
        ):
            with self.subTest(identifier=identifier):
                self.assertEqual(verify_receipt_token(make_receipt_token(identifier)),
                                 identifier)
        for identifier in (
            "MOJPROP-ID-" + "a" * 24,
            "MOJPROP-ID-" + "0" * 23,
            "MOJPROP-ID-" + "0" * 25,
            "MOJPROP-ID-" + "X" * 24,
            "MOJPROP-20261116-ABCDEF1",
        ):
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError):
                    make_receipt_token(identifier)
