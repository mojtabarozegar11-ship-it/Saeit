"""No buyer has to publish/send/upload a social post to join MOJ PROP Plan1.

All results here are source-only and synthetic: no online account, contract,
customer data, wallet, external posts, or real sale is created by these tests.
"""
from dataclasses import FrozenInstanceError
from unittest.mock import patch
import unittest

from prop_firm.plan1_buyer_no_social_amendment import (
    SKU, HISTORICAL_TERMS_VERSION, AMENDMENT_VERSION, STATUS,
    FA_NO_POST, EN_NO_POST, buyer_no_social_post_amendment,
    current_plan1_buyer_copy,
)
from prop_firm.plan1_buyer_disclosure_v12 import buyer_disclosure


class NoBuyerPostingTests(unittest.TestCase):
    def setUp(self):
        self.waiver = buyer_no_social_post_amendment()
        self.current = current_plan1_buyer_copy()
        self.old = buyer_disclosure()

    def test_canonical_sku_is_only_plan_one(self):
        self.assertEqual(self.waiver.sku, "MOJ-PROP-01")

    def test_contract_source_version_stays_historically_verifiable(self):
        self.assertEqual(self.waiver.historical_terms_version, HISTORICAL_TERMS_VERSION)

    def test_waiver_has_new_explicit_identifier(self):
        self.assertEqual(self.waiver.amendment_version, AMENDMENT_VERSION)

    def test_historical_document_is_retained_unchanged(self):
        self.assertIn("ONE original Instagram and ONE original Facebook", self.old.en)

    def test_old_source_digest_still_bound(self):
        self.assertEqual(self.waiver.historical_disclosure_digest_sha256,
                         self.old.digest_sha256)

    def test_new_copy_does_not_keep_old_instagram_demand(self):
        self.assertNotIn("ONE original Instagram and ONE original Facebook", self.current.en)

    def test_new_farsi_copy_does_not_keep_old_post_demand(self):
        self.assertNotIn("یک پست اصیل اینستاگرام", self.current.fa)

    def test_new_copy_contains_explicit_farsi_waiver(self):
        self.assertIn("خریدار چالش MOJ-PROP-01 موظف", self.current.fa)

    def test_new_copy_contains_explicit_english_waiver(self):
        self.assertIn("NOT required", self.current.en)

    def test_buyer_required_instagram_count_zero(self):
        self.assertEqual(self.waiver.instagram_posts_required, 0)

    def test_buyer_required_facebook_count_zero(self):
        self.assertEqual(self.waiver.facebook_posts_required, 0)

    def test_no_social_link_submission_required(self):
        self.assertFalse(self.waiver.buyer_post_links_required)

    def test_no_social_upload_required(self):
        self.assertFalse(self.waiver.buyer_media_upload_required)

    def test_no_post_cannot_fail_assessment(self):
        self.assertFalse(self.waiver.posting_a_condition_of_challenge_pass)

    def test_no_post_cannot_waive_real_profit(self):
        self.assertFalse(self.waiver.posting_a_condition_of_funded_profit)

    def test_no_post_cannot_block_fair_refund(self):
        self.assertFalse(self.waiver.posting_a_condition_of_fair_refund)

    def test_no_marketing_optin_inferred(self):
        self.assertFalse(self.waiver.marketing_consent_inferred)

    def test_no_owner_social_account_use_allowed(self):
        self.assertFalse(self.waiver.personal_owner_social_use_allowed)

    def test_no_executed_contract_assertion(self):
        self.assertFalse(self.waiver.current_signed_terms_verified_by_this_module)

    def test_no_invoice_enabled(self):
        self.assertFalse(self.waiver.payable_invoice_enabled)

    def test_no_enrollment_enabled(self):
        self.assertFalse(self.waiver.paid_enrollment_enabled)

    def test_current_copy_requires_buyer_acceptance_of_revised_terms(self):
        self.assertTrue(self.current.requires_separate_buyer_contract_acceptance)

    def test_current_copy_requires_independent_kyc_and_funding(self):
        self.assertTrue(self.current.requires_independent_kyc_and_funding)

    def test_current_copy_is_not_sale(self):
        self.assertFalse(self.current.payment_enabled)

    def test_current_copy_is_not_invoice(self):
        self.assertFalse(self.current.invoice_enabled)

    def test_current_copy_is_not_enrollment(self):
        self.assertFalse(self.current.enrollment_enabled)

    def test_waiver_status_is_nonpayable(self):
        self.assertEqual(self.waiver.status, STATUS)

    def test_new_copy_retains_native_tron_price(self):
        self.assertEqual(self.current.fee_sun, 30_000_000)
        self.assertEqual(self.current.network, "TRON-mainnet")

    def test_new_copy_preserves_simulated_phase_notice(self):
        self.assertIn("BOTH evaluation stages are simulated", self.current.en)

    def test_new_copy_preserves_deadline(self):
        self.assertIn("28-consecutive-day", self.current.en)

    def test_new_copy_preserves_50_closed_trades(self):
        self.assertIn("50 distinct", self.current.en)

    def test_new_copy_preserves_6_days_each_stage(self):
        self.assertIn("6 verified trading days IN EACH stage", self.current.en)

    def test_new_copy_preserves_real_funding_condition(self):
        self.assertIn("real USD 100 initial funded account is CONDITIONAL", self.current.en)

    def test_new_copy_preserves_profit_split(self):
        self.assertIn("70% trader / 30% firm", self.current.en)

    def test_new_copy_preserves_refund_and_kyc_conditions(self):
        self.assertIn("cancellation and fair refunds", self.current.en)
        self.assertIn("identity checks", self.current.en)

    def test_new_copy_preserves_no_wallet_or_payment_request(self):
        self.assertIn("NO invoice, wallet or payment request", self.current.en)

    def test_different_old_copy_digest_blocks_waiver(self):
        from dataclasses import replace
        with patch("prop_firm.plan1_buyer_no_social_amendment.buyer_disclosure",
                   return_value=replace(self.old, digest_sha256="f"*64)):
            with self.assertRaises(ValueError):
                buyer_no_social_post_amendment()

    def test_old_social_clause_drift_blocks_new_copy(self):
        from dataclasses import replace
        with patch("prop_firm.plan1_buyer_no_social_amendment.buyer_disclosure",
                   return_value=replace(self.old, en=self.old.en.replace(
                       "ONE original Instagram", "TWO original Instagram"))):
            with self.assertRaises(ValueError):
                current_plan1_buyer_copy()

    def test_new_disclosure_is_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            self.current.payment_enabled = True

    def test_amendment_is_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            self.waiver.buyer_media_upload_required = True

    def test_current_copy_digest_differs_from_original(self):
        self.assertNotEqual(self.current.digest_sha256, self.old.digest_sha256)

    def test_copy_is_reproducible_from_source(self):
        self.assertEqual(self.current.digest_sha256, current_plan1_buyer_copy().digest_sha256)

    def test_no_customer_pii_is_returned(self):
        for text in (repr(self.current).lower(), repr(self.waiver).lower()):
            self.assertNotIn("passport_number", text)
            self.assertNotIn("wallet_private_key", text)

    def test_optional_promotions_require_separate_consent(self):
        self.assertIn("separate informed consent", self.current.en)

    def test_current_copy_refers_to_buyer_waiver(self):
        self.assertIn("waives the earlier two-post obligation", self.current.en)

    def test_facing_pre_purchase_copy_now_says_no_buyer_social_post(self):
        from prop_firm.order_readiness import PREPURCHASE_DISCLOSURES
        copy = " ".join(PREPURCHASE_DISCLOSURES)
        self.assertIn("No Instagram or Facebook post", copy)

    def test_facing_pre_purchase_copy_keeps_optional_social_consent_separate(self):
        from prop_firm.order_readiness import PREPURCHASE_DISCLOSURES
        copy = " ".join(PREPURCHASE_DISCLOSURES)
        self.assertIn("Optional promotions", copy)

    def test_facing_pre_purchase_copy_mentions_legacy_waiver(self):
        from prop_firm.order_readiness import PREPURCHASE_DISCLOSURES
        copy = " ".join(PREPURCHASE_DISCLOSURES)
        self.assertIn("no-social-post waiver", copy)

    def test_buyer_social_refusal_cannot_change_other_required_evidence_gates(self):
        from prop_firm.order_readiness import REQUIRED
        for gate in (
            "buyer_kyc_verified", "buyer_country_permitted",
            "buyer_age_verified", "terms_version_accepted",
            "independent_funding_proof", "refund_policy_disclosed",
        ):
            with self.subTest(gate=gate):
                self.assertIn(gate, REQUIRED)

    def test_current_farsi_buyer_copy_says_both_stages_demo(self):
        from prop_firm.plan1_buyer_no_social_amendment import current_plan1_buyer_copy
        self.assertIn("هر دو مرحله چالش تنها با حساب دمو", current_plan1_buyer_copy().fa)

    def test_current_english_buyer_copy_says_live_broker_account_not_needed(self):
        from prop_firm.plan1_buyer_no_social_amendment import current_plan1_buyer_copy
        self.assertIn("live LiteFinance or other broker account is NOT a prerequisite",
                      current_plan1_buyer_copy().en)

    def test_current_buyer_copy_says_real_only_after_two_passes(self):
        from prop_firm.plan1_buyer_no_social_amendment import current_plan1_buyer_copy
        self.assertIn("AFTER independently passing BOTH", current_plan1_buyer_copy().en)

    def test_current_buyer_copy_preserves_legal_sale_checks(self):
        from prop_firm.plan1_buyer_no_social_amendment import current_plan1_buyer_copy
        self.assertIn("legally required", current_plan1_buyer_copy().en)
