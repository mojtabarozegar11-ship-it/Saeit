"""Moj Prop informational lead intake — never an account, invoice or funded promise."""
from datetime import timedelta
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from prop_firm.models import PropInformationInquiry
from prop_firm.interest import (
    PropInterestError, canonical_inquiry_email, intake_enabled, submit_inquiry,
)

APPROVED_SETTINGS = {
    "MOJ_PROP_INTEREST_ENABLED": True,
    "MOJ_PROP_INTEREST_HMAC_KEY_HEX": "7d" * 32,
    "MOJ_PROP_PRIVACY_URL": "/moj-prop/privacy/",
    "ALLOWED_HOSTS": ["mojplaywin.com", "www.mojplaywin.com", "testserver"],
}


class MojPropInformationIntakeTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, **kwargs):
        data = {"email": "interested@company.net", "privacy_consent": "yes"}
        data.update(kwargs)
        return self.client.post(
            "/moj-prop/interest/", data,
            secure=True, HTTP_HOST="mojplaywin.com",
        )

    @override_settings(**APPROVED_SETTINGS)
    def test_secure_interest_page_renders(self):
        response = self.client.get(
            "/moj-prop/interest/", secure=True, HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not a challenge application")
        self.assertContains(response, "/moj-prop/privacy/")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    @override_settings(**APPROVED_SETTINGS)
    def test_privacy_disclosure_is_reachable(self):
        response = self.client.get("/moj-prop/privacy/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "30-day retention")

    def test_unreleased_interest_is_not_public(self):
        with override_settings(
            MOJ_PROP_INTEREST_ENABLED=False,
            MOJ_PROP_INTEREST_HMAC_KEY_HEX="",
            MOJ_PROP_PRIVACY_URL="",
            ALLOWED_HOSTS=APPROVED_SETTINGS["ALLOWED_HOSTS"],
        ):
            self.assertEqual(
                self.client.get("/moj-prop/interest/", secure=True,
                                HTTP_HOST="mojplaywin.com").status_code,
                404,
            )

    @override_settings(**APPROVED_SETTINGS)
    def test_consent_required_before_record_creation(self):
        response = self.post(privacy_consent="")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PropInformationInquiry.objects.count(), 0)

    @override_settings(**APPROVED_SETTINGS)
    def test_valid_request_is_saved_once_not_paid(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        row = PropInformationInquiry.objects.get()
        self.assertEqual(row.email, "interested@company.net")
        self.assertEqual(row.status, "unreviewed")
        self.assertNotIn("funded", row.__dict__)
        self.assertAlmostEqual(
            (row.expires_at - row.created_at).total_seconds(),
            timedelta(days=30).total_seconds(),
            delta=2,
        )

    @override_settings(**APPROVED_SETTINGS)
    def test_repeat_inquiry_is_idempotent(self):
        self.post()
        self.post()
        self.assertEqual(PropInformationInquiry.objects.count(), 1)

    @override_settings(**APPROVED_SETTINGS)
    def test_email_change_creates_independent_inquiry(self):
        self.post()
        self.post(email="other@company.net")
        self.assertEqual(PropInformationInquiry.objects.count(), 2)

    @override_settings(**APPROVED_SETTINGS)
    def test_invalid_address_never_stored(self):
        for email in ("", "fake", "a@example.com", "a@guest.mojplaywin.com",
                      "a@host.test", "a@host.local", "a..b@company.net"):
            with self.subTest(email=email):
                response = self.post(email=email)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(PropInformationInquiry.objects.count(), 0)

    @override_settings(**APPROVED_SETTINGS)
    def test_cross_brand_host_is_404(self):
        with override_settings(ALLOWED_HOSTS=["zomorodmelal.ir", "mojplaywin.com"]):
            response = self.client.get("/moj-prop/interest/",
                                       secure=True, HTTP_HOST="zomorodmelal.ir")
            self.assertEqual(response.status_code, 404)

    @override_settings(**APPROVED_SETTINGS)
    def test_plaintext_http_rejected(self):
        response = self.client.post(
            "/moj-prop/interest/",
            {"email": "a@company.net", "privacy_consent": "yes"},
            HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(**APPROVED_SETTINGS)
    def test_rate_limit_enforced_on_seventh_request(self):
        for i in range(6):
            self.assertEqual(
                self.post(email=f"person{i}@company.net").status_code, 200
            )
        self.assertEqual(self.post(email="person7@company.net").status_code, 429)
        self.assertEqual(PropInformationInquiry.objects.count(), 6)

    @override_settings(**APPROVED_SETTINGS)
    def test_rate_limit_failure_does_not_record_data(self):
        from unittest.mock import patch
        with patch("prop_firm.interest.cache.add", side_effect=RuntimeError("outage")):
            self.assertEqual(self.post().status_code, 503)
        self.assertEqual(PropInformationInquiry.objects.count(), 0)

    @override_settings(**APPROVED_SETTINGS)
    def test_email_digest_is_keyed_not_raw_sha256(self):
        from hashlib import sha256
        self.post()
        row = PropInformationInquiry.objects.get()
        self.assertNotEqual(row.email_digest, sha256(row.email.encode()).hexdigest())
        self.assertEqual(len(row.email_digest), 64)

    @override_settings(**APPROVED_SETTINGS)
    def test_landing_page_cta_only_when_intake_verified(self):
        response = self.client.get("/moj-prop/", HTTP_HOST="mojplaywin.com")
        self.assertContains(response, "/moj-prop/interest/")

    def test_inactive_landing_does_not_advertise_form(self):
        with override_settings(
            MOJ_PROP_INTEREST_ENABLED=False,
            MOJ_PROP_PRIVACY_URL="",
            MOJ_PROP_INTEREST_HMAC_KEY_HEX="",
            ALLOWED_HOSTS=["mojplaywin.com"],
        ):
            response = self.client.get("/moj-prop/", HTTP_HOST="mojplaywin.com")
            self.assertNotContains(response, "Request information — no payment")

    @override_settings(**APPROVED_SETTINGS)
    def test_submission_is_not_trading_or_billing(self):
        self.post()
        self.assertEqual(PropInformationInquiry.objects.count(), 1)
        # No enrollment, paid invoice, broker account, or email send occurs.
        from prop_firm.models import PropChallengeEnrollment, PropAccount
        self.assertEqual(PropChallengeEnrollment.objects.count(), 0)
        self.assertEqual(PropAccount.objects.count(), 0)


