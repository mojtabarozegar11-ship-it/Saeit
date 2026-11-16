"""C118 free educational opt-in DB outages, no real mail or paid signal sends."""
import json
from unittest.mock import MagicMock, patch

from django.db import DatabaseError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.signal_free_models import MojSignalFreeSubscription
from core.signal_free_views import _sign, _validated_token, SignalConsentStorageUnavailable


class MojtabaConsentDbFailureC118Tests(TestCase):
    def setUp(self):
        self.browser = Client()
        self.email = "consent-test@example.org"

    def member(self, status):
        now = timezone.now()
        return MojSignalFreeSubscription.objects.create(
            email=self.email, status=status, nonce="c118-valid-local-secret",
            consent_at=now, confirmation_sent_at=now,
            confirmed_at=now if status == "confirmed" else None,
            source="signal-desk", ip_hash="d" * 64,
        )

    def assert_storage_unavailable(self, response):
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["payment_received"], False)
        self.assertEqual(response["Retry-After"], "60")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn(self.email, response.content.decode("utf-8"))
        self.assertNotIn("c118-valid-local-secret", response.content.decode("utf-8"))

    def test_signup_rate_limit_sql_unavailable_no_account_no_mail(self):
        payload = json.dumps({"email": self.email, "consent": True, "website": ""})
        with patch("core.signal_free_views._smtp_ready", return_value=True):
            with patch.object(MojSignalFreeSubscription.objects, "filter",
                              side_effect=DatabaseError("private DB credentials")):
                with patch("core.signal_free_views.send_mail") as outgoing:
                    response = self.browser.post(
                        reverse("moj_signal_free_subscribe"),
                        data=payload, content_type="application/json",
                    )
        self.assert_storage_unavailable(response)
        self.assertEqual(MojSignalFreeSubscription.objects.count(), 0)
        outgoing.assert_not_called()

    def test_confirm_signed_token_lookup_sql_failure_no_membership_change(self):
        row = self.member("pending")
        token = _sign(row, "confirm")
        with patch.object(MojSignalFreeSubscription.objects, "get",
                          side_effect=DatabaseError("private DB")):
            response = self.browser.get(
                reverse("moj_signal_free_confirm", args=[token])
            )
        self.assert_storage_unavailable(response)
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")

    def test_unsubscribe_signed_token_lookup_sql_failure_retains_suppression(self):
        row = self.member("confirmed")
        token = _sign(row, "unsubscribe")
        with patch.object(MojSignalFreeSubscription.objects, "get",
                          side_effect=DatabaseError("private DB")):
            response = self.browser.get(
                reverse("moj_signal_free_unsubscribe", args=[token])
            )
        self.assert_storage_unavailable(response)
        row.refresh_from_db()
        self.assertEqual(row.status, "confirmed")

    def test_confirm_update_failure_never_claims_verified_optin(self):
        row = self.member("pending")
        token = _sign(row, "confirm")
        query = MagicMock()
        query.update.side_effect = DatabaseError("write failed")
        with patch("core.signal_free_views._smtp_ready", return_value=True):
            with patch.object(MojSignalFreeSubscription.objects, "filter",
                              return_value=query):
                response = self.browser.post(
                    reverse("moj_signal_free_confirm", args=[token]),
                )
        self.assert_storage_unavailable(response)
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")

    def test_unsubscribe_update_failure_cannot_pretend_optout_completed(self):
        row = self.member("confirmed")
        token = _sign(row, "unsubscribe")
        query = MagicMock()
        query.update.side_effect = DatabaseError("write failed")
        with patch.object(MojSignalFreeSubscription.objects, "filter",
                          return_value=query):
            response = self.browser.post(
                reverse("moj_signal_free_unsubscribe", args=[token]),
            )
        self.assert_storage_unavailable(response)
        row.refresh_from_db()
        self.assertEqual(row.status, "confirmed")

    def test_invalid_signed_token_never_queries_unavailable_db(self):
        with patch.object(MojSignalFreeSubscription.objects, "get",
                          side_effect=DatabaseError("offline")) as getter:
            response = self.browser.get(
                reverse("moj_signal_free_unsubscribe", args=["invalid"])
            )
        self.assertEqual(response.status_code, 404)
        getter.assert_not_called()

    def test_internal_storage_error_never_contains_private_sql_details(self):
        row = self.member("pending")
        with patch.object(MojSignalFreeSubscription.objects, "get",
                          side_effect=DatabaseError("supersecret-sql-failure")):
            with self.assertRaises(SignalConsentStorageUnavailable) as context:
                _validated_token(_sign(row, "confirm"), "confirm")
        self.assertNotIn("supersecret", str(context.exception))

    def test_successful_unsubscribe_still_revokes_normal_active_free_member(self):
        row = self.member("confirmed")
        response = self.browser.post(reverse(
            "moj_signal_free_unsubscribe", args=[_sign(row, "unsubscribe")],
        ))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["paid_entitlement"])
        row.refresh_from_db()
        self.assertEqual(row.status, "unsubscribed")
