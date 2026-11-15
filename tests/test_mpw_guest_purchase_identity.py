"""Private checkout guest email identity contract, source-only and zero SMTP."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from django.test import SimpleTestCase

from services.mpw_guest_purchase_identity import (
    GuestBuyerIdentityError, GuestInvoiceIdentity,
    issue_guest_order_identity, verify_guest_order_identity, valid_guest_email,
)

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
KEY = b"not-production-secret-key-over-32-bytes-for-guest-binding"


class GuestPurchaseIdentityTests(SimpleTestCase):
    def proof(self, **changes):
        kwargs = dict(
            buyer_email="buyer@farmco.org", invoice_id="mpw:inv:123456",
            principal_id=52, product_id=72, bound_at_utc=NOW, signing_key=KEY,
        )
        kwargs.update(changes)
        return issue_guest_order_identity(**kwargs)

    def verify(self, *, proof=None, **changes):
        kwargs = dict(
            proof=self.proof() if proof is None else proof,
            buyer_email="BUYER@FARMCO.ORG", invoice_id="mpw:inv:123456",
            principal_id=52, product_id=72,
            now_utc=NOW + timedelta(days=1), signing_key=KEY,
        )
        kwargs.update(changes)
        return verify_guest_order_identity(**kwargs)

    def test_valid_real_email_invoice_identity_can_be_verified(self):
        self.assertTrue(self.verify())
        self.assertEqual(valid_guest_email("OWNER@FARMCO.ORG"), "owner@farmco.org")

    def test_no_raw_customer_email_in_signed_invoice_record(self):
        proof = self.proof()
        self.assertNotIn("buyer@", repr(proof))
        self.assertEqual(len(proof.buyer_email_digest), 64)

    def test_missing_or_placeholder_guest_email_denied(self):
        for email in ("", "fake", "x@example.com", "a@guest.mojplaywin.com",
                      "a@domain.invalid", "a@bad.local", "name @host.org", "x@bad..com",
                      " a@host.com", "a@host.com "):
            with self.subTest(email=email[:30]), self.assertRaises(GuestBuyerIdentityError):
                self.proof(buyer_email=email)

    def test_boolean_or_control_character_email_denied(self):
        for email in (True, 123, None, "me@host.org\n"):
            with self.subTest(email=repr(email)), self.assertRaises(GuestBuyerIdentityError):
                self.proof(buyer_email=email)

    def test_unrelated_invoice_does_not_recover_another_purchase(self):
        self.assertFalse(self.verify(invoice_id="mpw:inv:123457"))

    def test_unrelated_product_does_not_inherit_download_right(self):
        self.assertFalse(self.verify(product_id=225))

    def test_wrong_guest_principal_cannot_recover_buyer_order(self):
        self.assertFalse(self.verify(principal_id=53))

    def test_different_email_cannot_read_other_customer_invoice(self):
        self.assertFalse(self.verify(buyer_email="other@farmco.org"))

    def test_expiry_and_future_issued_identities_denied(self):
        proof = self.proof()
        self.assertFalse(self.verify(proof=proof, now_utc=NOW + timedelta(days=30)))
        self.assertFalse(self.verify(proof=proof, now_utc=NOW - timedelta(seconds=1)))

    def test_signature_tampering_or_key_rotation_denied(self):
        proof = self.proof()
        self.assertFalse(self.verify(proof=replace(proof, hmac_sha256="f" * 64)))
        self.assertFalse(self.verify(signing_key=b"different-rotation-key-more-than-thirty-two-bytes"))

    def test_invalid_invoice_id_or_zero_account_product_denied(self):
        for changes in ({"invoice_id": "../bad"}, {"principal_id": 0},
                        {"product_id": -1}, {"principal_id": True},
                        {"product_id": True}):
            with self.subTest(changes=changes), self.assertRaises(GuestBuyerIdentityError):
                self.proof(**changes)

    def test_email_and_invoice_identity_do_not_approve_payment(self):
        proof = self.proof()
        self.assertIsInstance(proof, GuestInvoiceIdentity)
        self.assertFalse(hasattr(proof, "payment_verified"))
        self.assertFalse(hasattr(proof, "send_email"))
        self.assertFalse(hasattr(proof, "wallet_address"))
