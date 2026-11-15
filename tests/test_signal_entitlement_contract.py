"""Single global Mojtaba.bot.ai entitlement: source-only, no buyer emails stored."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac

from django.test import SimpleTestCase

from core.signal_entitlement_contract import (
    SignalEntitlementError, canonical_buyer_email,
    issue_signal_lease, verify_signal_access,
    authorized_signal_delivery_preflight,
)
from core.signal_source_evidence import canonical_signal_bytes

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

    def paid_invoice_record(self, lease=None, **changes):
        lease = lease or self.lease()
        record = {
            "network": "tron-mainnet", "asset": "TRX",
            "invoice_id": lease.invoice_id,
            "tx_id": "a" * 64,
            "merchant_tenant_id": lease.merchant_tenant_id,
            "sku": lease.sku,
            "buyer_digest": lease.buyer_digest,
            "expected_sun": 12000000,
            "settled_sun": 12000000,
            "finality_verified": True,
            "refunded": False,
            "refund_pending": False,
            "charge_disputed": False,
            "settlement_reversed": False,
            "entitlement_revoked": False,
        }
        record.update(changes)
        return {lease.invoice_id: record}

    def access(self, *, lease=None, **kwargs):
        x = self.lease() if lease is None else lease
        fields = {
            "lease": x,
            "buyer_email": "BUYER@REALCOMPANY.NET",
            "requested_sku": "moj-signals-standard",
            "mirror_brand": "saman",
            "now_utc": NOW,
            "signing_key": KEY,
            "independently_reconciled_invoices": self.paid_invoice_record(x),
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

    def test_email_digest_is_keyed_and_domain_separated(self):
        from hashlib import sha256
        lease = self.lease()
        canonical_email = "buyer@realcompany.net"
        self.assertNotEqual(lease.buyer_digest, sha256(canonical_email.encode("ascii")).hexdigest())
        rotated = self.lease(signing_key=OTHER)
        self.assertNotEqual(lease.buyer_digest, rotated.buyer_digest)
        self.assertFalse(self.access(lease=rotated))

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

    def test_missing_reversal_and_revocation_fields_deny_old_ledger(self):
        lease = self.lease()
        base = self.paid_invoice_record(lease)[lease.invoice_id]
        for missing in ("refunded", "settlement_reversed", "entitlement_revoked"):
            with self.subTest(field=missing):
                record = dict(base)
                del record[missing]
                self.assertFalse(self.access(
                    lease=lease,
                    independently_reconciled_invoices={lease.invoice_id: record},
                ))

    def test_completed_refund_or_reversed_settlement_immediately_revokes(self):
        lease = self.lease()
        active = self.paid_invoice_record(lease)
        self.assertTrue(self.access(
            lease=lease, independently_reconciled_invoices=active,
        ))
        for flag in ("refunded", "settlement_reversed", "entitlement_revoked"):
            with self.subTest(flag=flag):
                revoked = self.paid_invoice_record(lease, **{
                    flag: True,
                    "refund_pending": False,
                    "charge_disputed": False,
                    "finality_verified": True,
                })
                self.assertFalse(self.access(
                    lease=lease, independently_reconciled_invoices=revoked,
                ))

    def test_revocation_requires_real_boolean_false_not_false_like_value(self):
        lease = self.lease()
        for flag in ("refunded", "settlement_reversed", "entitlement_revoked"):
            for bad in ("false", 0, None, [], {}):
                with self.subTest(flag=flag, bad=repr(bad)):
                    self.assertFalse(self.access(
                        lease=lease, independently_reconciled_invoices=(
                            self.paid_invoice_record(lease, **{flag: bad})
                        ),
                    ))

    def test_exact_tron_invoice_amount_remains_required_after_refund_fix(self):
        lease = self.lease()
        for bad_paid in (1, 11999999, 12000001, 13000000, True, "12000000"):
            with self.subTest(amount=repr(bad_paid)):
                self.assertFalse(self.access(
                    lease=lease,
                    independently_reconciled_invoices=self.paid_invoice_record(
                        lease, settled_sun=bad_paid,
                    ),
                ))
        self.assertTrue(self.access(
            lease=lease, independently_reconciled_invoices=(
                self.paid_invoice_record(lease, settled_sun=12000000)
            ),
        ))

    def test_missing_or_invalid_expected_amount_cannot_unlock_signal(self):
        lease = self.lease()
        original = self.paid_invoice_record(lease)[lease.invoice_id]
        for bad in (None, True, False, 0, -1, "12000000", 12000001):
            with self.subTest(value=repr(bad)):
                record = dict(original)
                if bad is None:
                    record.pop("expected_sun")
                else:
                    record["expected_sun"] = bad
                self.assertFalse(self.access(
                    lease=lease,
                    independently_reconciled_invoices={lease.invoice_id: record},
                ))

    def test_reversed_entitlement_denied_across_all_brand_mirrors(self):
        lease = self.lease()
        for brand in ("saman", "zahra", "taniya"):
            with self.subTest(brand=brand):
                self.assertFalse(self.access(
                    lease=lease, mirror_brand=brand,
                    independently_reconciled_invoices=self.paid_invoice_record(
                        lease, settlement_reversed=True,
                    ),
                ))
                self.assertFalse(self.access(
                    lease=lease, mirror_brand=brand,
                    independently_reconciled_invoices=self.paid_invoice_record(
                        lease, entitlement_revoked=True,
                    ),
                ))

    def test_paid_invoice_must_match_exact_tenant_sku_buyer_and_finality(self):
        variations = (
            {"merchant_tenant_id": "signal_other"},
            {"sku": "moj-signals-professional"},
            {"buyer_digest": "0" * 64},
            {"settled_sun": 0}, {"settled_sun": True},
            {"settled_sun": 1}, {"expected_sun": 12000001},
            {"expected_sun": True}, {"expected_sun": 0},
            {"tx_id": "z" * 64}, {"tx_id": "A" * 64},
            {"invoice_id": "mpw:trx:invoice:10002"},
            {"refunded": True},
            {"settlement_reversed": True},
            {"entitlement_revoked": True},
            {"settlement_reversed": "false"},
            {"entitlement_revoked": 0},
            {"asset": "USDT"}, {"network": "tron-testnet"},
            {"finality_verified": "yes"}, {"finality_verified": False},
            {"refund_pending": True}, {"charge_disputed": True},
        )
        for corrupted in variations:
            with self.subTest(corrupted=corrupted):
                self.assertFalse(self.access(
                    independently_reconciled_invoices=self.paid_invoice_record(**corrupted)
                ))

    def test_underpaid_invoice_with_matching_customer_cannot_unlock_signal(self):
        self.assertFalse(self.access(
            independently_reconciled_invoices=self.paid_invoice_record(
                settled_sun=1, expected_sun=12000000
            )
        ))

    def test_refunded_invoice_revokes_access_even_if_hmac_still_valid(self):
        self.assertFalse(self.access(
            independently_reconciled_invoices=self.paid_invoice_record(
                refunded=True, finality_verified=True
            )
        ))

    def test_invoice_id_set_alone_no_longer_grants_signal_access(self):
        self.assertFalse(self.access(independently_reconciled_invoices={"mpw:trx:invoice:10001"}))
        self.assertTrue(self.access(independently_reconciled_invoices=self.paid_invoice_record()))

    def test_untrusted_boolean_identity_is_never_a_buyer_email(self):
        self.assertFalse(self.access(buyer_email=True))
        self.assertFalse(self.access(buyer_email=None))

    def test_malformed_signature_and_claim_fields_denied(self):
        x = self.lease()
        self.assertFalse(self.access(lease=replace(x, hmac_sha256="1" * 63)))
        self.assertFalse(self.access(lease=replace(x, issuing_bot="second_bot")))
        self.assertFalse(self.access(lease=replace(x, buyer_digest="not-a-digest")))

    def test_delivery_preflight_needs_independent_paid_lease_and_authenticated_source(self):
        source_key = b"independent-trusted-broker-source-key-more-than-thirty-two"
        event = {
            "event_id": "broker:20261115:777",
            "symbol": "XAUUSD", "side": "buy",
            "created_at": NOW - timedelta(minutes=5),
            "entry": "4000", "stop_loss": "3980", "take_profit": "4040",
            "verified_source": True,
        }
        sig = hmac.new(source_key, canonical_signal_bytes(
            record=event, brand="saman", source_id="broker_verified_1",
        ), sha256).hexdigest()
        args = {
            "lease": self.lease(), "buyer_email": "buyer@realcompany.net",
            "requested_sku": "moj-signals-standard", "mirror_brand": "saman",
            "now_utc": NOW, "signing_key": KEY,
            "independently_reconciled_invoices": self.paid_invoice_record(),
            "revoked_invoice_ids": set(),
            "signal_record": event, "source_id": "broker_verified_1",
            "source_signature": sig,
            "trusted_source_keys": {("saman", "broker_verified_1"): source_key},
            "durable_seen_event_ids": set(),
            "jurisdiction_and_delivery_rights_verified": True,
        }
        allowed = authorized_signal_delivery_preflight(**args)
        self.assertTrue(allowed["eligible_to_deliver"])
        self.assertEqual(allowed["canonical_bot"], "mojtaba.bot.ai")
        self.assertFalse(allowed["delivery_performed"])
        self.assertFalse(allowed["payment_processed"])
        for changes, reason in (
            ({"jurisdiction_and_delivery_rights_verified": False},
             "jurisdiction_or_delivery_rights"),
            ({"independently_reconciled_invoices": set()},
             "unpaid_or_invalid_entitlement"),
            ({"buyer_email": "attacker@realcompany.net"},
             "unpaid_or_invalid_entitlement"),
            ({"source_signature": "0" * 64}, "untrusted_signal_source"),
            ({"durable_seen_event_ids": {event["event_id"]}},
             "untrusted_signal_source"),
            ({"source_id": "untrusted"}, "untrusted_signal_source"),
        ):
            with self.subTest(change=str(changes)[:30]):
                outcome = authorized_signal_delivery_preflight(**{**args, **changes})
                self.assertFalse(outcome["eligible_to_deliver"])
                self.assertEqual(outcome["reason"], reason)
