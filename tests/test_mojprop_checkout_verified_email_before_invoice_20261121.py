"""Isolated security regression for verified-email Starter30 invoice admission.

No email, invoice, TRX transfer or customer data is created by these tests.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import inspect

from django.core import signing
from django.test import SimpleTestCase, override_settings

from prop_firm import starter30_checkout_email as email
from prop_firm import starter30_views, starter30_live
from prop_firm.models import PropSimulationLoginChallenge


class VerifiedPreinvoiceEmailTests(SimpleTestCase):
    def test_checkout_purpose_is_not_login_or_recovery(self):
        self.assertEqual(PropSimulationLoginChallenge.Purpose.CHECKOUT, "checkout")

    @override_settings(
        MPW_MOJPROP_PREINVOICE_TRANSACTIONAL_EMAIL_APPROVED=False,
        MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_no_mail_before_owner_approval(self):
        with (
            patch.object(starter30_live, "require_release"),
            patch.object(email, "send_mail") as sent,
        ):
            with self.assertRaises(email.CheckoutEmailUnavailable):
                email.request_checkout_email_code("buyer@example.org")
        sent.assert_not_called()

    @override_settings(
        MPW_MOJPROP_PREINVOICE_TRANSACTIONAL_EMAIL_APPROVED=True,
        MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED=False,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_no_mail_without_verified_shared_abuse_limit(self):
        with (
            patch.object(starter30_live, "require_release"),
            patch.object(email, "send_mail") as sent,
        ):
            with self.assertRaises(email.CheckoutEmailUnavailable):
                email.request_checkout_email_code("buyer@example.org")
        sent.assert_not_called()

    def _sign_proof(self, *, digest="d" * 64, identity_id=41):
        return signing.dumps({
            "v": 1, "id": identity_id, "email_digest": digest,
            "scope": "starter30-single-invoice",
        }, salt=email._SALT)

    def test_valid_short_lived_proof_matches_verified_email(self):
        with (
            patch.object(email, "require_email_verification_release"),
            patch.object(email, "_identity_keys", return_value=("s" * 64, "d" * 64)),
        ):
            self.assertEqual(
                email.verify_checkout_email_proof(
                    "buyer@example.org", self._sign_proof(),
                ), 41
            )

    def test_wrong_email_digest_rejected(self):
        with (
            patch.object(email, "require_email_verification_release"),
            patch.object(email, "_identity_keys", return_value=("s" * 64, "z" * 64)),
        ):
            with self.assertRaises(email.CheckoutEmailUnavailable):
                email.verify_checkout_email_proof(
                    "other@example.org", self._sign_proof(),
                )

    def test_wrong_purpose_and_invalid_id_rejected(self):
        for record in (
            {"v": 1, "id": 41, "scope": "other", "email_digest": "d" * 64},
            {"v": 1, "id": 0, "scope": "starter30-single-invoice", "email_digest": "d" * 64},
        ):
            with self.subTest(record=record):
                proof = signing.dumps(record, salt=email._SALT)
                with (
                    patch.object(email, "require_email_verification_release"),
                    patch.object(email, "_identity_keys", return_value=("s", "d" * 64)),
                ):
                    with self.assertRaises(email.CheckoutEmailUnavailable):
                        email.verify_checkout_email_proof("buyer@example.org", proof)

    def test_cross_application_signature_rejected(self):
        wrong_salt = signing.dumps({
            "v": 1, "id": 41, "email_digest": "d" * 64,
            "scope": "starter30-single-invoice",
        }, salt="unrelated-app")
        with patch.object(email, "require_email_verification_release"):
            with self.assertRaises(email.CheckoutEmailUnavailable):
                email.verify_checkout_email_proof("buyer@example.org", wrong_salt)

    def test_expired_proof_rejected_before_invoice(self):
        with (
            patch.object(email, "require_email_verification_release"),
            patch.object(email.signing, "loads", side_effect=signing.SignatureExpired("expired")),
        ):
            with self.assertRaises(email.CheckoutEmailUnavailable):
                email.verify_checkout_email_proof("buyer@example.org", self._sign_proof())

    def test_empty_or_oversized_proof_rejected(self):
        with patch.object(email, "require_email_verification_release"):
            for proof in ("", "x" * 2049, None):
                with self.subTest(size=len(proof) if proof else None):
                    with self.assertRaises(email.CheckoutEmailUnavailable):
                        email.verify_checkout_email_proof("buyer@example.org", proof)

    def test_code_request_rate_limit_and_no_send_on_replay(self):
        now = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)
        def setup(last, count):
            identity_manager = MagicMock()
            identity_manager.using.return_value.select_for_update.return_value.get.return_value = (
                SimpleNamespace(pk=91, status="pending")
            )
            challenge_manager = MagicMock()
            scope = challenge_manager.using.return_value.filter.return_value
            scope.count.return_value = count
            scope.order_by.return_value.values_list.return_value.first.return_value = last
            return identity_manager, challenge_manager

        @contextmanager
        def atomic(*, using):
            self.assertEqual(using, email.MOJPROP_DB_ALIAS)
            yield

        for last, count in ((now - timedelta(seconds=30), 1),
                            (now - timedelta(minutes=5), 3)):
            im, cm = setup(last, count)
            with (
                patch.object(email, "require_email_verification_release"),
                patch.object(email, "normalize_email", return_value="buyer@example.org"),
                patch.object(email, "register_identity", return_value=91),
                patch.object(email.timezone, "now", return_value=now),
                patch.object(email.PropSimulationIdentity, "objects", im),
                patch.object(email.PropSimulationLoginChallenge, "objects", cm),
                patch.object(email.transaction, "atomic", atomic),
                patch.object(email, "issue_login_challenge") as issue,
                patch.object(email, "send_mail") as sent,
            ):
                with self.assertRaises(email.CheckoutEmailUnavailable):
                    email.request_checkout_email_code("buyer@example.org")
                issue.assert_not_called()
                sent.assert_not_called()

    def test_success_code_is_purpose_scoped_and_sent_once(self):
        now = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)
        im, cm = MagicMock(), MagicMock()
        im.using.return_value.select_for_update.return_value.get.return_value = SimpleNamespace(
            pk=91, status="pending"
        )
        scope = cm.using.return_value.filter.return_value
        scope.count.return_value = 0
        scope.order_by.return_value.values_list.return_value.first.return_value = None
        issued = SimpleNamespace(code="opaque-offline-code", challenge_ref="offline-ref")
        @contextmanager
        def atomic(*, using):
            self.assertEqual(using, email.MOJPROP_DB_ALIAS)
            yield
        with (
            patch.object(email, "require_email_verification_release"),
            patch.object(email, "normalize_email", return_value="buyer@example.org"),
            patch.object(email, "register_identity", return_value=91),
            patch.object(email.timezone, "now", return_value=now),
            patch.object(email.PropSimulationIdentity, "objects", im),
            patch.object(email.PropSimulationLoginChallenge, "objects", cm),
            patch.object(email.transaction, "atomic", atomic),
            patch.object(email, "issue_login_challenge", return_value=issued) as issue,
            patch.object(email, "send_mail", return_value=1) as sent,
        ):
            self.assertEqual(email.request_checkout_email_code("buyer@example.org"), "offline-ref")
            issue.assert_called_once_with(91, purpose="checkout")
            sent.assert_called_once()

    def test_checkout_consumption_requires_exact_purpose(self):
        source = inspect.getsource(email.consume_checkout_email_code)
        self.assertIn("expected_purpose=_PURPOSE", source)

    def test_no_raw_email_or_wallet_in_signed_proof(self):
        source = inspect.getsource(email.consume_checkout_email_code)
        self.assertIn('"email_digest"', source)
        self.assertNotIn('"email":', source)
        self.assertNotIn('"wallet":', source)

    def test_invoice_creation_requires_signed_verified_mailbox(self):
        source = inspect.getsource(starter30_live.issue_invoice)
        self.assertIn("verify_checkout_email_proof(email, email_proof)", source)
        self.assertIn("select_for_update()", source)
        self.assertIn("previous = (", source)
        self.assertIn("previous.recipient", source)
        self.assertIn("except ValidationError", source)
        self.assertIn("recipient=recipient", source)

    def test_live_checkout_wires_otp_before_invoice(self):
        source = inspect.getsource(starter30_views.starter30_checkout)
        self.assertIn('action == "request_email_code"', source)
        self.assertIn('action == "verify_email_code"', source)
        self.assertIn("email_proof=request.session.get(_EMAIL_PROOF_SESSION", source)
        self.assertIn("request.session.cycle_key()", source)
