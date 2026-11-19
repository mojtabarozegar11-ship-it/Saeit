"""Private checkout guest email identity contract, source-only and zero SMTP."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from django.test import SimpleTestCase

from services.mpw_guest_purchase_identity import (
    GuestBuyerIdentityError, GuestInvoiceIdentity,
    issue_guest_order_identity, verify_guest_order_identity, valid_guest_email,
    paid_guest_delivery_preflight,
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

    def test_guest_email_digest_is_keyed_not_guessable_sha256(self):
        from hashlib import sha256
        canonical_email = "buyer@farmco.org"
        proof = self.proof()
        self.assertNotEqual(proof.buyer_email_digest, sha256(canonical_email.encode("ascii")).hexdigest())
        rotated = self.proof(signing_key=b"independently-rotated-signing-key-over-thirtytwo-bytes")
        self.assertNotEqual(proof.buyer_email_digest, rotated.buyer_email_digest)
        self.assertFalse(self.verify(proof=rotated))

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

    def paid_record(self, proof=None, **changes):
        x = proof or self.proof()
        record = dict(
            invoice_id=x.invoice_id, principal_id=x.principal_id,
            product_id=x.product_id, buyer_email_digest=x.buyer_email_digest,
            status="paid", network="tron-mainnet", asset="TRX",
            chain_finality_verified=True, provider_tx_id="a" * 64,
            expected_sun=2500000, settled_sun=2500000, refunded_sun=0,
            delivery_rights_verified=True, refunded=False,
            refund_pending=False, charge_disputed=False,
            settlement_reversed=False, entitlement_revoked=False,
        )
        record.update(changes)
        return record

    def delivery(self, *, proof=None, **changes):
        x = proof or self.proof()
        args = dict(
            proof=x, buyer_email="buyer@farmco.org",
            invoice_id="mpw:inv:123456", principal_id=52, product_id=72,
            now_utc=NOW + timedelta(days=1), signing_key=KEY,
            trusted_paid_invoice=self.paid_record(proof=x),
        )
        args.update(changes)
        return paid_guest_delivery_preflight(**args)

    def test_paid_guest_receipt_only_allows_readonly_delivery_decision(self):
        decision = self.delivery()
        self.assertTrue(decision["eligible_for_private_delivery"])
        self.assertFalse(decision["file_delivered"])
        self.assertFalse(decision["email_sent"])
        self.assertFalse(decision["payment_changed"])

    def test_valid_guest_hmac_without_paid_ledger_never_unblocks_file(self):
        for invoice in (None, {}, True, "paid"):
            with self.subTest(invoice=invoice):
                self.assertFalse(self.delivery(trusted_paid_invoice=invoice)["eligible_for_private_delivery"])

    def test_paid_ledger_customer_invoice_product_binding_is_exact(self):
        for wrong in (
            {"invoice_id": "mpw:inv:123457"}, {"principal_id": 53},
            {"product_id": 225}, {"buyer_email_digest": "f" * 64},
        ):
            with self.subTest(wrong=wrong):
                self.assertEqual(
                    self.delivery(trusted_paid_invoice=self.paid_record(**wrong))["reason"],
                    "invoice_owner_product_mismatch",
                )

    def test_fake_transaction_or_no_independent_finality_does_not_deliver(self):
        for wrong in (
            {"status": "pending"}, {"network": "tron-testnet"},
            {"asset": "USDT"}, {"chain_finality_verified": "yes"},
            {"chain_finality_verified": False}, {"provider_tx_id": "x" * 64},
            {"provider_tx_id": "A" * 64}, {"settled_sun": 0},
            {"settled_sun": True}, {"settled_sun": 1},
            {"expected_sun": 0}, {"expected_sun": True},
            {"expected_sun": 2500001}, {"settled_sun": 2499999},
            {"settled_sun": 2500001}, {"refunded_sun": True},
            {"refunded_sun": -1}, {"refunded_sun": 1},
        ):
            with self.subTest(wrong=wrong):
                self.assertEqual(
                    self.delivery(trusted_paid_invoice=self.paid_record(**wrong))["reason"],
                    "independent_tron_payment_unverified",
                )

    def test_refund_dispute_or_rights_change_stops_delivery(self):
        for wrong in (
            {"refund_pending": True}, {"charge_disputed": True},
            {"delivery_rights_verified": False}, {"refunded": True},
            {"settlement_reversed": True}, {"entitlement_revoked": True},
        ):
            with self.subTest(wrong=wrong):
                self.assertEqual(
                    self.delivery(trusted_paid_invoice=self.paid_record(**wrong))["reason"],
                    "rights_or_dispute_hold",
                )

    def test_guest_checkout_dust_payment_cannot_unlock_download(self):
        for paid in (1, 2499999, 2500001, 2600000):
            with self.subTest(sun=paid):
                decision = self.delivery(trusted_paid_invoice=self.paid_record(
                    settled_sun=paid,
                ))
                self.assertEqual(decision["reason"], "independent_tron_payment_unverified")

    def test_invoice_quote_amount_must_exist_and_be_positive_int(self):
        record = self.paid_record()
        for missing_or_bad in (None, True, False, 0, -1, "2500000", 2500001):
            with self.subTest(quote=repr(missing_or_bad)):
                candidate = dict(record)
                if missing_or_bad is None:
                    candidate.pop("expected_sun")
                else:
                    candidate["expected_sun"] = missing_or_bad
                self.assertEqual(
                    self.delivery(trusted_paid_invoice=candidate)["reason"],
                    "independent_tron_payment_unverified",
                )

    def test_refund_total_must_be_explicit_zero_int(self):
        record = self.paid_record()
        for invalid in (None, True, False, -1, 1, 2500000, "0"):
            with self.subTest(refunded_sun=repr(invalid)):
                candidate = dict(record)
                if invalid is None:
                    candidate.pop("refunded_sun")
                else:
                    candidate["refunded_sun"] = invalid
                self.assertEqual(
                    self.delivery(trusted_paid_invoice=candidate)["reason"],
                    "independent_tron_payment_unverified",
                )

    def test_partially_refunded_purchase_cannot_still_be_delivered(self):
        ledger = self.paid_record(
            settled_sun=2500000, expected_sun=2500000,
            refunded_sun=1, refunded=False, refund_pending=False,
        )
        self.assertFalse(self.delivery(
            trusted_paid_invoice=ledger,
        )["eligible_for_private_delivery"])

    def test_completed_refund_or_reversal_revokes_after_pending_clears(self):
        self.assertTrue(self.delivery()["eligible_for_private_delivery"])
        for changed_flag in ("refunded", "settlement_reversed", "entitlement_revoked"):
            with self.subTest(status=changed_flag):
                candidate = self.paid_record(**{
                    changed_flag: True, "refund_pending": False,
                    "charge_disputed": False, "refunded_sun": 0,
                })
                self.assertEqual(
                    self.delivery(trusted_paid_invoice=candidate)["reason"],
                    "rights_or_dispute_hold",
                )

    def test_refund_revocation_fields_must_explicitly_be_false(self):
        for field in ("refunded", "settlement_reversed", "entitlement_revoked"):
            for bad in (None, 0, "false", [], {}):
                with self.subTest(field=field, value=repr(bad)):
                    candidate = self.paid_record(**{field: bad})
                    if bad is None:
                        candidate.pop(field)
                    self.assertEqual(
                        self.delivery(trusted_paid_invoice=candidate)["reason"],
                        "rights_or_dispute_hold",
                    )

    def test_unpaid_document_cannot_be_unlocked_by_email_hmac_alone(self):
        proof = self.proof()
        record = self.paid_record(proof=proof)
        record.pop("expected_sun")
        record.pop("refunded")
        self.assertFalse(self.delivery(
            proof=proof, trusted_paid_invoice=record,
        )["eligible_for_private_delivery"])

    def test_zero_side_effects_even_when_proven_guest_can_read(self):
        decision = self.delivery()
        self.assertTrue(decision["eligible_for_private_delivery"])
        self.assertFalse(decision["email_sent"])
        self.assertFalse(decision["file_delivered"])
        self.assertFalse(decision["payment_changed"])

    def test_email_and_invoice_identity_do_not_approve_payment(self):
        proof = self.proof()
        self.assertIsInstance(proof, GuestInvoiceIdentity)
        self.assertFalse(hasattr(proof, "payment_verified"))
        self.assertFalse(hasattr(proof, "send_email"))
        self.assertFalse(hasattr(proof, "wallet_address"))
