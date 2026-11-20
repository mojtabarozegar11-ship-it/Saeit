"""MOJ-PROP-01 private order review — synthetic fixtures, no customer data."""
import hmac
import json
import unittest
from dataclasses import FrozenInstanceError
from dataclasses import replace

from prop_firm.order_readiness import REQUIRED
from prop_firm.buyer_order_review import (
    FIXED, REQUIRED_PROOFS, SCHEMA, PURPOSE,
    Plan1OrderGateClosed, evaluate_signed_plan1_request,
)

KEY = b"test-key-only-do-not-use-in-production-64-bytes!!!!!!!!!!!!"
REQUEST = "REQUEST-ABCDEFGHIJKLMNO"
BUYER = "BUYER-ABCDEFGHIJKLMNOP"
SELLER = "SELLER-ABCDEFGHIJKLMNOP"
NOW = 1_795_000_000
INQUIRY_DIGEST = "8" * 64  # Synthetic original inquiry form SHA-256.


def packet():
    base = dict(FIXED)
    base.update(
        schema=SCHEMA, purpose=PURPOSE,
        request_ref=REQUEST, buyer_ref=BUYER, seller_ref=SELLER,
        inquiry_intent_sha256=INQUIRY_DIGEST,
        facts={name: True for name in REQUIRED},
        proofs={name: hex(n + 1)[2:] * 64 for n, name in enumerate(REQUIRED_PROOFS)},
        requested_at_sec=NOW-120,
        reviewed_at_sec=NOW-20,
        expires_at_sec=NOW+3600,
    )
    # Avoid oversize SHA fixture for 10..15: always exactly 64 hex nibbles.
    base["proofs"] = {name: format(n+1, "x") * 64
                      for n, name in enumerate(REQUIRED_PROOFS)}
    return base


def tag(p, key=KEY):
    encoded = json.dumps(p, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    return hmac.new(key, encoded, "sha256").hexdigest()


def call(p=None, **kw):
    p = packet() if p is None else p
    inputs = dict(packet=p, signed_tag_hex=tag(p),
                  trusted_reviewer_key=KEY,
                  expected_request_ref=REQUEST, expected_buyer_ref=BUYER,
                  expected_seller_ref=SELLER,
                  expected_inquiry_intent_sha256=INQUIRY_DIGEST,
                  server_now_sec=NOW)
    inputs.update(kw)
    return evaluate_signed_plan1_request(**inputs)


class PlanOneSignedBuyerOrderTests(unittest.TestCase):
    def reject(self, key, value):
        p = packet()
        p[key] = value
        with self.assertRaises(Plan1OrderGateClosed):
            call(p)

    def test_valid_synthetic_request_is_never_payable(self):
        a=call()
        self.assertEqual((a.sku,a.native_fee_sun),("MOJ-PROP-01",30_000_000))
        self.assertFalse(a.payable_invoice_created)

    def test_no_challenge_enrollment_created(self):
        self.assertFalse(call().challenge_enrollment_created)

    def test_no_settlement_or_funding_claim(self):
        a=call()
        self.assertFalse(a.settlement_confirmed)
        self.assertFalse(a.funding_proven_by_this_code)

    def test_no_social_post_sent(self):
        self.assertFalse(call().social_post_published)

    def test_private_case_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            call().native_fee_sun=31_000_000

    def test_exact_signed_case_owner(self):
        a=call()
        self.assertEqual((a.request_ref,a.buyer_ref,a.seller_ref),
                         (REQUEST,BUYER,SELLER))

    def test_contract_version_v12_pinned(self):
        self.assertEqual(call().contract_version,"2026-11-15/v1.2")

    def test_all_versioned_contract_guards_required(self):
        self.assertEqual(len(REQUIRED), 24)
        self.assertEqual(call().verified_fact_count,len(REQUIRED))
        for gate in REQUIRED:
            p=packet()
            p["facts"][gate]=False
            with self.subTest(gate=gate),self.assertRaises(Plan1OrderGateClosed):
                call(p)

    def test_each_guard_rejects_integer_truthiness(self):
        for gate in REQUIRED:
            p=packet()
            p["facts"][gate]=1
            with self.subTest(gate=gate),self.assertRaises(Plan1OrderGateClosed):
                call(p)

    def test_each_required_proof_missing_fails(self):
        for key in REQUIRED_PROOFS:
            p=packet()
            p["proofs"].pop(key)
            with self.subTest(key=key),self.assertRaises(Plan1OrderGateClosed):
                call(p)

    def test_each_zero_digest_fails(self):
        for key in REQUIRED_PROOFS:
            p=packet()
            p["proofs"][key]="0"*64
            with self.subTest(key=key),self.assertRaises(Plan1OrderGateClosed):
                call(p)

    def test_missing_mac_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(signed_tag_hex="")

    def test_wrong_mac_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(signed_tag_hex="a"*64)

    def test_wrong_reviewer_key_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(trusted_reviewer_key=b"another-test-only-internal-key-long-enough!!")

    def test_non_bytes_key_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(trusted_reviewer_key=KEY.decode())

    def test_short_reviewer_key_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(trusted_reviewer_key=b"weak")

    def test_cross_order_replay_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(expected_request_ref="REQUEST-ZYXWVUTSRQPONML")

    def test_cross_buyer_replay_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(expected_buyer_ref="BUYER-ZYXWVUTSRQPONMLK")

    def test_cross_seller_replay_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(expected_seller_ref="SELLER-ZYXWVUTSRQPONM")

    def test_start30_educational_sku_refused(self):
        self.reject("sku","MOJPROP-STARTER30")

    def test_wrong_native_sun_refused(self):
        self.reject("native_fee_sun",29_000_000)

    def test_boolean_native_fee_refused(self):
        self.reject("native_fee_sun",True)

    def test_usd_and_irr_currency_key_refused(self):
        p=packet()
        p["currency"]="USD"
        with self.assertRaises(Plan1OrderGateClosed):
            call(p)

    def test_wrong_terms_version_refused(self):
        self.reject("contract_version","2026-11-14/v1.1")

    def test_wrong_purpose_refused(self):
        self.reject("purpose","educational_ten_session_report")

    def test_wrong_simulation_status_refused(self):
        self.reject("simulated_evaluation",False)

    def test_unconditional_funding_promise_refused(self):
        self.reject("real_account_only_after_pass_and_funding",False)

    def test_wrong_funded_usd_level_refused(self):
        self.reject("funded_tier_usd",1000)

    def test_wrong_phase_count_refused(self):
        self.reject("evaluation_phase_count",1)

    def test_wrong_challenge_duration_refused(self):
        self.reject("duration_days",29)

    def test_wrong_unique_closed_positions_refused(self):
        self.reject("min_distinct_closed_positions",49)

    def test_wrong_trading_days_each_phase_refused(self):
        self.reject("min_trading_days_per_phase",5)

    def test_wrong_profit_shares_refused(self):
        self.reject("profit_share_trader_pct",80)

    def test_mandatory_posts_only_one_per_platform(self):
        self.reject("social_posts_per_platform",2)

    def test_owner_social_account_policy_cannot_be_removed(self):
        self.reject("owner_personal_social_accounts_excluded",False)

    def test_social_requirement_requires_legal_permission(self):
        self.reject("social_posting_is_conditional_on_law",False)

    def test_stale_buyer_consent_refused(self):
        self.reject("requested_at_sec",NOW-31*86400)

    def test_unreviewed_customer_request_refused(self):
        self.reject("reviewed_at_sec",NOW+1)

    def test_future_customer_request_refused(self):
        self.reject("requested_at_sec",NOW+2)

    def test_expired_review_refused(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(server_now_sec=NOW+3600)

    def test_excess_review_window_refused(self):
        self.reject("expires_at_sec",NOW+86401)

    def test_untrusted_boolean_server_clock_refused(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(server_now_sec=True)

    def test_bad_request_ref_refused(self):
        self.reject("request_ref","REQUEST-fake")

    def test_unicode_control_character_refused(self):
        self.reject("buyer_ref","BUYER-ABC\u202eDEF")

    def test_signature_invalidated_on_contract_tampering(self):
        p=packet()
        signed=tag(p)
        p["proofs"]["contract_pdf_sha256"]="f"*64
        with self.assertRaises(Plan1OrderGateClosed):
            call(p,signed_tag_hex=signed)

    def test_original_signed_inquiry_digest_survives_review(self):
        self.assertEqual(call().inquiry_intent_sha256, INQUIRY_DIGEST)

    def test_reusing_signed_review_for_different_inquiry_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(expected_inquiry_intent_sha256="9" * 64)

    def test_missing_server_trusted_inquiry_digest_fails(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(expected_inquiry_intent_sha256="")

    def test_buyer_rewrites_inquiry_digest_after_signing_fails(self):
        p=packet()
        originally_signed=tag(p)
        p["inquiry_intent_sha256"]="f" * 64
        with self.assertRaises(Plan1OrderGateClosed):
            call(p, signed_tag_hex=originally_signed)

    def test_boolean_inquiry_digest_is_not_accepted(self):
        with self.assertRaises(Plan1OrderGateClosed):
            call(expected_inquiry_intent_sha256=True)

    def test_no_private_documents_or_email_in_result(self):
        a=repr(call())
        self.assertNotIn("contract_pdf_sha256",a)
        self.assertNotIn("email",a)

    def test_hash_is_deterministic_for_identical_attested_packet(self):
        self.assertEqual(call().review_packet_sha256,call().review_packet_sha256)


if __name__ == "__main__":
    unittest.main()
