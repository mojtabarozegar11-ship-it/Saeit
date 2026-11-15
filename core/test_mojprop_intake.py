import json

from django.test import Client, TestCase

from .models import MojPropRequest


class MojPropIntakeTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        response = self.client.get("/moj-prop/intake/")
        self.assertEqual(response.status_code, 200)
        self.csrf_token = response.json()["csrf_token"]

    def payload(self, **overrides):
        value = {
            "name": "Moj Prop Client",
            "email": "client@example.com",
            "service": "brief",
            "horizon": "week",
            "notes": "Need a dated gold market brief for educational review.",
            "consent": True,
            "website": "",
        }
        value.update(overrides)
        return value

    def post(self, value):
        return self.client.post(
            "/moj-prop/intake/",
            data=json.dumps(value),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_X_REAL_IP="198.51.100.40",
        )

    def test_valid_request_is_stored_for_manual_review(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["request_id"].startswith("MOJPROP-"))
        record = MojPropRequest.objects.get(request_id=body["request_id"])
        self.assertEqual(record.status, "new")
        self.assertEqual(record.route, "brief")
        self.assertEqual(record.email, "client@example.com")

    def test_invalid_consent_is_rejected(self):
        response = self.post(self.payload(consent=False))
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent", response.json()["fields"])
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_honeypot_is_rejected(self):
        response = self.post(self.payload(website="bot-filled"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_invalid_email_is_rejected(self):
        response = self.post(self.payload(email="not-an-email"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["fields"])

    def test_rate_limit_returns_retry_after_header_and_does_not_create_sixth_lead(self):
        for index in range(5):
            response = self.post(self.payload(name=f"Manual Review Buyer {index}"))
            self.assertEqual(response.status_code, 201)
        rejected = self.post(self.payload(name="Manual Review Buyer Six"))
        self.assertEqual(rejected.status_code, 429)
        self.assertEqual(rejected.headers["Retry-After"], "600")
        self.assertEqual(rejected.json()["retry_after"], 600)
        self.assertEqual(rejected.headers["Cache-Control"], "no-store")
        self.assertEqual(MojPropRequest.objects.count(), 5)

    def test_first_keyed_request_creates_one_durable_manual_lead(self):
        payload = self.payload(idempotency_key="11111111-1111-4111-8111-111111111111")
        response = self.post(payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertFalse(data["reused"])
        self.assertRegex(data["request_id"], r"^MOJPROP-ID-[A-F0-9]{24}$")
        self.assertEqual(MojPropRequest.objects.count(), 1)
        self.assertNotIn(payload["idempotency_key"], str(data))
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_lost_response_identical_retry_returns_same_receipt_no_second_lead(self):
        payload = self.payload(idempotency_key="22222222-2222-4222-8222-222222222222")
        first = self.post(payload)
        second = self.post(payload)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(second.json()["request_id"], first.json()["request_id"])
        self.assertTrue(second.json()["reused"])
        self.assertTrue(second.json()["receipt_token"])
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_recovered_lead_retains_manual_review_stage(self):
        payload = self.payload(idempotency_key="33333333-3333-4333-8333-333333333333")
        first = self.post(payload)
        MojPropRequest.objects.filter(request_id=first.json()["request_id"]).update(status="reviewing")
        second = self.post(payload)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "reviewing")
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_reused_key_with_changed_buyer_email_must_not_disclose_receipt(self):
        key = "44444444-4444-4444-8444-444444444444"
        first = self.post(self.payload(idempotency_key=key))
        mismatch = self.post(self.payload(idempotency_key=key, email="other@example.com"))
        self.assertEqual(first.status_code, 201)
        self.assertEqual(mismatch.status_code, 409)
        self.assertNotIn("receipt_token", mismatch.json())
        self.assertNotIn(first.json()["request_id"], str(mismatch.json()))
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_reused_key_with_changed_plan_or_notes_fails_closed(self):
        key = "55555555-5555-4555-8555-555555555555"
        self.assertEqual(self.post(self.payload(idempotency_key=key)).status_code, 201)
        for changes in ({"notes": "Different educational report scope with audit."},
                        {"service": "signals"}, {"horizon": "month"},
                        {"name": "Another customer"}):
            result = self.post(self.payload(idempotency_key=key, **changes))
            self.assertEqual(result.status_code, 409)
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_non_uuid4_or_noncanonical_keys_are_rejected(self):
        for invalid in (
            "00000000-0000-1000-8000-000000000000",
            "11111111-1111-4111-8111-11111111111A",
            "11111111111141118111111111111111",
            "not-a-secret", "",
        ):
            with self.subTest(key=invalid):
                self.assertEqual(
                    self.post(self.payload(idempotency_key=invalid)).status_code, 400
                )
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_boolean_and_array_keys_are_rejected_without_server_error(self):
        for value in (True, 5, ["11111111-1111-4111-8111-111111111111"]):
            with self.subTest(value=value):
                self.assertEqual(
                    self.post(self.payload(idempotency_key=value)).status_code, 400
                )
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_separate_uuid4_creates_distinct_unpaid_leads(self):
        keys = ("66666666-6666-4666-8666-666666666666",
                "77777777-7777-4777-8777-777777777777")
        ids = [self.post(self.payload(idempotency_key=k)).json()["request_id"] for k in keys]
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(MojPropRequest.objects.count(), 2)

    def test_recovery_remains_available_after_throttle_but_new_lead_is_blocked(self):
        key = "88888888-8888-4888-8888-888888888888"
        first = self.post(self.payload(idempotency_key=key))
        self.assertEqual(first.status_code, 201)
        for n in range(4):
            self.assertEqual(self.post(self.payload(name=f"Additional Buyer {n}")).status_code, 201)
        again = self.post(self.payload(idempotency_key=key))
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()["reused"])
        blocked = self.post(self.payload(idempotency_key="99999999-9999-4999-8999-999999999999"))
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(MojPropRequest.objects.count(), 5)

    def test_recovery_requires_consent_even_when_key_was_valid(self):
        key = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        self.assertEqual(self.post(self.payload(idempotency_key=key)).status_code, 201)
        denied = self.post(self.payload(idempotency_key=key, consent=False))
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_legacy_unkeyed_api_remains_compatible(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["reused"])
        self.assertRegex(response.json()["request_id"], r"^MOJPROP-[0-9]{8}-[A-F0-9]{8}$")


from pathlib import Path
from django.test import SimpleTestCase


class MojPropIntakeFrontendRecoveryContract(SimpleTestCase):
    def test_form_sends_secret_key_in_body_never_url(self):
        html = (Path(__file__).resolve().parents[1] /
                "templates/moj-prop-v4/index.html").read_text(encoding="utf-8")
        self.assertIn("window.crypto.randomUUID()", html)
        self.assertIn("idempotency_key:pendingSubmission.key", html)
        self.assertIn("pendingSubmission.fingerprint!==fingerprint", html)
        self.assertIn("pendingSubmission.uncertain=true", html)
        self.assertNotIn("idempotency_key=", html)

    def test_form_accepts_only_explicit_success_or_recovered_lead(self):
        html = (Path(__file__).resolve().parents[1] /
                "templates/moj-prop-v4/index.html").read_text(encoding="utf-8")
        self.assertIn("response.status===201 && data.reused!==true", html)
        self.assertIn("response.status===200 && data.reused===true", html)
        self.assertIn("ID-[A-F0-9]{24}", html)
        self.assertIn("Retry the SAME unchanged form", html)
        self.assertIn("No payment was attempted.", html)
