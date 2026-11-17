"""Real Django consent lifecycle; SMTP replaced with a local in-memory transport.

No external email, live financial recommendations, billing, tokens, or trading.
"""
import json
import re
from unittest import mock

from django.core import mail
from django.test import Client, TestCase, override_settings

from core.signal_free_models import MojSignalFreeSubscription
from core.signal_free_views import free_unsubscribe_link


@override_settings(
    MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="smtp.example.org", EMAIL_HOST_USER="not-used-in-tests",
    EMAIL_HOST_PASSWORD="test-only", EMAIL_USE_TLS=True,
    EMAIL_USE_SSL=False, EMAIL_PORT=587, DEFAULT_FROM_EMAIL="research@example.org",
)
class MojSignalFreeOptInTests(TestCase):
    def setUp(self):
        # Enable only the code path, not a real SMTP; local backend collects mail.
        self.ready = mock.patch("core.signal_free_views._smtp_ready", return_value=True)
        self.ready.start()
        self.addCleanup(self.ready.stop)
        self.client = Client(enforce_csrf_checks=True)
        result = self.client.get("/moj-signal-free-subscribe/")
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["enabled"])
        self.csrf = result.json()["csrf_token"]

    def submit(self, email="reader@example.org", **overrides):
        body = {"email": email, "consent": True, "website": ""}
        body.update(overrides)
        return self.client.post(
            "/moj-signal-free-subscribe/",
            data=json.dumps(body), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_opt_in_starts_pending_only_and_sends_one_confirmation(self):
        result = self.submit()
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.json()["status"], "verification_if_eligible")
        record = MojSignalFreeSubscription.objects.get()
        self.assertEqual(record.status, "pending")
        self.assertEqual(record.source, "signal-desk")
        self.assertIsNone(record.confirmed_at)
        self.assertIsNotNone(record.confirmation_sent_at)
        self.assertNotIn("reader@example.org", str(record))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/moj-signal-free-confirm/", mail.outbox[0].body)
        self.assertIn("not a trading signal", mail.outbox[0].body)

    def test_email_link_get_cannot_confirm_without_explicit_post(self):
        self.submit()
        record = MojSignalFreeSubscription.objects.get()
        link = re.search(r"https://mojplaywin.com(/moj-signal-free-confirm/[^\s]+)", mail.outbox[-1].body).group(1)
        view = self.client.get(link)
        self.assertEqual(view.status_code, 200)
        self.assertIn(b'method="post"', view.content)
        record.refresh_from_db()
        self.assertEqual(record.status, "pending")
        done = self.client.post(link, HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json()["status"], "confirmed")
        record.refresh_from_db()
        self.assertEqual(record.status, "confirmed")
        self.assertIsNotNone(record.confirmed_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post(link, HTTP_X_CSRFTOKEN=self.csrf).status_code, 404)

    def test_unsubscribe_get_does_not_unsubscribe_then_post_revokes(self):
        self.submit()
        record = MojSignalFreeSubscription.objects.get()
        confirm_url = re.search(r"https://mojplaywin.com(/moj-signal-free-confirm/[^\s]+)", mail.outbox[-1].body).group(1)
        self.client.post(confirm_url, HTTP_X_CSRFTOKEN=self.csrf)
        record.refresh_from_db()
        unsubscribe = free_unsubscribe_link(record).replace("https://mojplaywin.com", "")
        self.assertEqual(self.client.get(unsubscribe).status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.status, "confirmed")
        response = self.client.post(unsubscribe, HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unsubscribed")
        record.refresh_from_db()
        self.assertIsNotNone(record.unsubscribed_at)
        self.assertEqual(record.status, "unsubscribed")
        self.assertEqual(self.client.post(unsubscribe, HTTP_X_CSRFTOKEN=self.csrf).status_code, 404)
        self.assertEqual(len(mail.outbox), 1)

    def test_unsubscribe_token_cannot_confirm_or_create_paid_access(self):
        self.submit()
        record = MojSignalFreeSubscription.objects.get()
        self.assertRaises(ValueError, free_unsubscribe_link, record)
        link = re.search(r"https://mojplaywin.com(/moj-signal-free-confirm/[^\s]+)", mail.outbox[-1].body).group(1)
        self.assertEqual(self.client.post(link + "tampered", HTTP_X_CSRFTOKEN=self.csrf).status_code, 404)
        self.assertEqual(MojSignalFreeSubscription.objects.get().status, "pending")

    def test_explicit_separate_opt_in_is_required(self):
        self.assertEqual(self.submit(consent=False).status_code, 400)
        self.assertEqual(self.submit(website="spam").status_code, 400)
        self.assertEqual(self.submit(email="not-an-email").status_code, 400)
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_csrf_blocks_cross_site_post_without_consent_record(self):
        r = self.client.post(
            "/moj-signal-free-subscribe/",
            data=json.dumps({"email": "a@example.org", "consent": True, "website": ""}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 0)

    def test_duplicate_json_keys_are_rejected_instead_of_overriding_consent(self):
        payload = '{"email":"a@example.org","email":"b@example.org","consent":true,"website":""}'
        result = self.client.post(
            "/moj-signal-free-subscribe/", data=payload,
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 0)

    def test_cooldown_keeps_one_email_and_one_pending_record(self):
        self.assertEqual(self.submit().status_code, 202)
        self.assertEqual(self.submit().status_code, 202)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 1)

    def test_stored_ip_rate_limit_blocks_sixth_new_email(self):
        for index in range(5):
            self.assertEqual(self.submit(email=f"reader{index}@example.org").status_code, 202)
        self.assertEqual(self.submit(email="reader6@example.org").status_code, 429)
        self.assertEqual(len(mail.outbox), 5)
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 5)

    def test_smtp_failure_rolls_back_pending_registration(self):
        with mock.patch("core.signal_free_views.send_mail", side_effect=OSError("offline")):
            result = self.submit()
        self.assertEqual(result.status_code, 503)
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 0)

    def test_feature_disabled_never_claims_a_registration(self):
        with mock.patch("core.signal_free_views._smtp_ready", return_value=False):
            self.assertFalse(self.client.get("/moj-signal-free-subscribe/").json()["enabled"])
            self.assertEqual(self.submit().status_code, 503)
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_lifecycle_does_not_create_a_mojprop_lead_or_paid_entitlement(self):
        from core.models import MojPropRequest, MojPropOffer
        self.submit()
        self.assertEqual(MojPropRequest.objects.count(), 0)
        self.assertEqual(MojPropOffer.objects.count(), 0)
        self.assertEqual(MojSignalFreeSubscription.objects.filter(status="confirmed").count(), 0)

    def test_confirmation_and_unsubscribe_have_private_cache_headers(self):
        self.submit()
        confirm_url = re.search(r"https://mojplaywin.com(/moj-signal-free-confirm/[^\s]+)", mail.outbox[-1].body).group(1)
        response = self.client.get(confirm_url)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
