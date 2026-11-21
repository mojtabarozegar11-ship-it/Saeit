"""Offline synthetic fixtures ONLY: these do not prove real seller/customer evidence."""
import copy
import hashlib
import hmac
import json
import unittest

from research.starter30_b.verified_draft_packet import (
    AMOUNT_SUN, DOMAIN, MERCHANT, NETWORK, SCHEMA, SCOPE, SKU,
    EvidenceGateClosed, prepare_reviewed_nonpayable_draft,
)

KEY = b"test-in-memory-only-not-a-live-secret-32+bytes"
ORDER = "MOJPROP30-ABCD1234567890"
LEAD = "LEAD-ABCDEFGHIJKLMNOP"
REQUEST = "REQUEST-ABCDEFGHIJKL"
ISSUE = 1_795_000_000


def packet():
    return dict(schema=SCHEMA, order_ref=ORDER, lead_token=LEAD,
                request_ref=REQUEST, attestation_ref="ATTEST-ABCDEFGHIJKL",
                sku=SKU, scope=SCOPE, merchant_id=MERCHANT,
                merchant_domain=DOMAIN, network=NETWORK, amount_sun=AMOUNT_SUN,
                buyer_intent="requested_one_time_educational_service_and_terms",
                contract_sha256="1" * 64, terms_sha256="2" * 64,
                consent_record_sha256="3" * 64,
                buyer_identity_proof_sha256="4" * 64,
                seller_legal_proof_sha256="5" * 64,
                buyer_signature_proof_sha256="6" * 64,
                seller_signature_proof_sha256="7" * 64,
                consent_at_sec=ISSUE - 120, buyer_signed_at_sec=ISSUE - 90,
                seller_signed_at_sec=ISSUE - 80, reviewed_at_sec=ISSUE - 30,
                issued_at_sec=ISSUE, expires_at_sec=ISSUE + 3600)


def tag(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=True).encode("ascii")
    return hmac.new(KEY, body, hashlib.sha256).hexdigest()


def call(value=None, **kwargs):
    value = packet() if value is None else value
    args = dict(payload=value, attestation_hmac_hex=tag(value),
                trusted_verifier_key=KEY, expected_order_ref=ORDER,
                expected_lead_token=LEAD, expected_request_ref=REQUEST,
                now_sec=ISSUE)
    args.update(kwargs)
    return prepare_reviewed_nonpayable_draft(**args)


class ReviewedStarter30GateTests(unittest.TestCase):
    def assert_rejected(self, change):
        x = packet()
        x.update(change)
        with self.assertRaises(EvidenceGateClosed):
            call(x)

    def test_valid_fixture_yields_only_nonpayable_draft(self):
        x = call()
        self.assertEqual((x.amount_sun, x.status, x.payable),
                         (30_000_000, "draft_non_payable", False))

    def test_no_claim_of_real_signature_or_merchant_verification(self):
        x = call()
        self.assertFalse(x.signatures_authentic_by_this_code)
        self.assertFalse(x.seller_legal_status_proven_by_this_code)

    def test_no_real_receipt_or_entitlement_claim(self):
        self.assertFalse(call().receipt_validated)

    def test_draft_binding_requires_database_uniqueness(self):
        self.assertTrue(call().requires_database_unique_order_and_attestation)

    def test_evidence_digest_equals_canonical_packet_digest(self):
        x = packet()
        data = json.dumps(x, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(call().evidence_packet_sha256, hashlib.sha256(data).hexdigest())

    def test_wrong_hmac_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(attestation_hmac_hex="a" * 64)

    def test_missing_hmac_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(attestation_hmac_hex="")

    def test_short_key_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(trusted_verifier_key=b"short")

    def test_user_supplied_string_key_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(trusted_verifier_key=KEY.decode())

    def test_other_order_replay_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(expected_order_ref="MOJPROP30-ZYXW9876543210")

    def test_other_buyer_replay_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(expected_lead_token="LEAD-ZYXWVUTSRQPONMLK")

    def test_other_request_replay_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(expected_request_ref="REQUEST-ZYXWVUTSRQPO")

    def test_wrong_merchant_rejected(self):
        self.assert_rejected({"merchant_domain": "evil.example"})

    def test_wrong_network_rejected(self):
        self.assert_rejected({"network": "shasta-testnet"})

    def test_wrong_sku_rejected(self):
        self.assert_rejected({"sku": "FUNDED-CHALLENGE"})

    def test_wrong_scope_rejected(self):
        self.assert_rejected({"scope": "funded_forex_trading"})

    def test_wrong_amount_rejected(self):
        self.assert_rejected({"amount_sun": 30_000_001})

    def test_boolean_amount_is_not_sun(self):
        self.assert_rejected({"amount_sun": True})

    def test_wrong_buyer_intent_rejected(self):
        self.assert_rejected({"buyer_intent": "marketing_newsletter_optin"})

    def test_missing_consent_proof_rejected(self):
        self.assert_rejected({"consent_record_sha256": ""})

    def test_zero_placeholder_proof_rejected(self):
        self.assert_rejected({"seller_legal_proof_sha256": "0" * 64})

    def test_missing_buyer_signature_proof_rejected(self):
        self.assert_rejected({"buyer_signature_proof_sha256": ""})

    def test_missing_seller_signature_proof_rejected(self):
        self.assert_rejected({"seller_signature_proof_sha256": ""})

    def test_missing_contract_hash_rejected(self):
        self.assert_rejected({"contract_sha256": ""})

    def test_missing_terms_hash_rejected(self):
        self.assert_rejected({"terms_sha256": ""})

    def test_expiry_over_24_hours_rejected(self):
        self.assert_rejected({"expires_at_sec": ISSUE + 86_401})

    def test_zero_lifetime_rejected(self):
        self.assert_rejected({"expires_at_sec": ISSUE})

    def test_expired_now_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(now_sec=ISSUE + 3600)

    def test_future_issued_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(now_sec=ISSUE - 1)

    def test_consent_after_buyer_signature_rejected(self):
        self.assert_rejected({"consent_at_sec": ISSUE - 10})

    def test_buyer_sign_after_review_rejected(self):
        self.assert_rejected({"buyer_signed_at_sec": ISSUE})

    def test_seller_sign_after_review_rejected(self):
        self.assert_rejected({"seller_signed_at_sec": ISSUE})

    def test_review_after_issuance_rejected(self):
        self.assert_rejected({"reviewed_at_sec": ISSUE + 1})

    def test_stale_consent_rejected(self):
        self.assert_rejected({"consent_at_sec": ISSUE - 31 * 86_400})

    def test_unicode_bidi_injected_rejected(self):
        self.assert_rejected({"request_ref": "REQUEST-ABCD\u202e123456"})

    def test_extra_unrecognized_field_rejected(self):
        self.assert_rejected({"paid": True})

    def test_missing_attestation_ref_rejected(self):
        p = packet()
        p.pop("attestation_ref")
        with self.assertRaises(EvidenceGateClosed):
            call(p)

    def test_invalid_reference_rejected(self):
        self.assert_rejected({"attestation_ref": "ATT-1"})

    def test_nonfinite_or_float_timestamps_rejected(self):
        self.assert_rejected({"reviewed_at_sec": float("nan")})

    def test_boolean_now_rejected(self):
        with self.assertRaises(EvidenceGateClosed):
            call(now_sec=True)

    def test_draft_exposes_attestation_ref_for_unique_registry(self):
        self.assertEqual(call().attestation_ref, packet()["attestation_ref"])

    def test_no_personal_identifier_in_returned_repr(self):
        obj = call()
        self.assertNotIn(LEAD, repr(obj))
        self.assertNotIn(REQUEST, repr(obj))


if __name__ == "__main__":
    unittest.main()
