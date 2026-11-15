"""Single global Mojtaba.bot.ai entitlement: source-only, no buyer emails stored."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from core.signal_entitlement_contract import (
    SignalEntitlementError, canonical_buyer_email,
    issue_signal_lease, verify_signal_access,
)

KEY = b"owner-configured-private-signing-key-32-bytes-minimum-for-tests"
OTHER = b"other-source-key-material-long-enough-for-hmac-tests"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


class SingleGlobalSignalEntitlementTests(SimpleTestCase):
    def lease(self, **kwargs):
        values = {
            "trusted_gateway_invoice": "mpw:trx:invoice:10001",
            "verified_buyer_email": "buyer@realcompany.net",
            "merchant_tenant_id": "signal_saman",
            "sku": "moj-signals-standard",
            "issued_at_utc": NOW - timedelta(days=1),
            "expires_at_utc": NOW + timedelta(days=29),
            "signing_key": KEY,
        }
        values.update(kwargs)
        return issue_signal_lease(**values)

    def access(self, *, lease=None, **kwargs):
        x = self.lease() if lease is None else lease
        fields = {
            "lease": x,
            "buyer_email": "BUYER@REALCOMPANY.NET",
            "requested_sku": "moj-signals-standard",
            "mirror_brand": "saman",
            "now_utc": NOW,
            "signing_key": KEY,
            "independently_reconciled_invoices": {"mpw:trx:invoice:10001"},
        }
        fields.update(kwargs)
        return verify_signal_access(**fields)

    def test_same_entitlement_works_on_three_mirrors_after_server_reconciliation(self):
        for brand in ("saman", "zahra", "taniya"):
            with self.subTest(brand=brand):
                self.assertTrue(self.access(mirror_brand=brand))

    def test_no_unverified_invoice_has_access_despite_matching_hmac(self):
        self.assertFalse(self.access(independently_reconciled_invoices=set()))

    def test_owner_or_email_difference_cannot_reuse_receipt(self):
        self.assertFalse(self.access(buyer_email="other@realcompany.net"))

    def test_wrong_plan_cannot_upgrade_with_valid_basic_lease(self):
        self.assertFalse(self.access(requested_sku="moj-signals-professional"))

    def test_cross_brand_is_allowed_but_not_unknown_brand(self):
        self.assertFalse(self.access(mirror_brand="unregistered"))

    def test_expired_or_not_yet_issued_lease_is_denied(self):
        lease = self.lease()
        self.assertFalse(self.access(lease=lease, now_utc=NOW + timedelta(days=30)))
        self.assertFalse(self.access(lease=lease, now_utc=NOW - timedelta(days=2)))

    def test_revocation_blocks_without_mutating_original_invoice(self):
        self.assertFalse(self.access(revoked_invoice_ids={"mpw:trx:invoice:10001"}))

    def test_signed_invoice_or_tenant_tampering_is_detected(self):
        x = self.lease()
        self.assertFalse(self.access(lease=replace(x, invoice_id="mpw:trx:invoice:10002"),
                                     independently_reconciled_invoices={"mpw:trx:invoice:10002"}))
        self.assertFalse(self.access(lease=replace(x, merchant_tenant_id="signal_zahra")))

    def test_key_rotation_blocks_old_entitlements(self):
        self.assertFalse(self.access(signing_key=OTHER))

    def test_placeholder_and_invalid_emails_cannot_be_issued(self):
        for email in ("", "invalid", "a@example.com", "a@guest.mojplaywin.com",
                      "a@bad..domain.com", "name @a.org", "a@x.invalid", "a@bad.local",
                      "x" * 200 + "@b.org"):
            with self.subTest(email=email[:25]), self.assertRaises(SignalEntitlementError):
                self.lease(verified_buyer_email=email)

    def test_source_lease_keeps_only_hash_not_raw_email(self):
        x = self.lease()
        self.assertEqual(len(x.buyer_digest), 64)
        self.assertNotIn("buyer@", repr(x))
        self.assertEqual(canonical_buyer_email("USER@COMPANY.NET"), "user@company.net")

    def test_bound_term_and_strict_nonfloat_dates(self):
        with self.assertRaises(SignalEntitlementError):
            self.lease(expires_at_utc=NOW + timedelta(days=400))
        with self.assertRaises(SignalEntitlementError):
            self.lease(issued_at_utc=datetime(2026, 11, 15))

    def test_untrusted_reconciliation_payload_is_not_a_server_ledger(self):
        self.assertFalse(self.access(independently_reconciled_invoices=["mpw:trx:invoice:10001"]))
        self.assertFalse(self.access(independently_reconciled_invoices={"proof": True}))

    def test_untrusted_boolean_identity_is_never_a_buyer_email(self):
        self.assertFalse(self.access(buyer_email=True))
        self.assertFalse(self.access(buyer_email=None))

    def test_malformed_signature_and_claim_fields_denied(self):
        x = self.lease()
        self.assertFalse(self.access(lease=replace(x, hmac_sha256="1" * 63)))
        self.assertFalse(self.access(lease=replace(x, issuing_bot="second_bot")))
        self.assertFalse(self.access(lease=replace(x, buyer_digest="not-a-digest")))
