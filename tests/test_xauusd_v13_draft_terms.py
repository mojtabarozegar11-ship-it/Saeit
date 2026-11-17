"""Strict offline tests for the independent, nonpayable FA/EN v1.3 draft."""
from dataclasses import replace
from decimal import Decimal
import re
import unittest
from unittest.mock import patch

from prop_firm.rules import POLICY
from prop_firm.plans import plan_for_code
from prop_firm.plan1_buyer_no_social_amendment import buyer_no_social_post_amendment
from prop_firm.xauusd_v13_draft_terms import (
    CANDIDATE_SCHEMA, DRAFT_CONTRACT_VERSION, SKU,
    draft_gold_terms_v13,
)


class DraftV13BuyerTermsTests(unittest.TestCase):
    def test_candidate_schema_is_explicit(self):
        self.assertIn("review-only", draft_gold_terms_v13().schema)

    def test_exact_challenge_sku_not_educational(self):
        self.assertEqual(draft_gold_terms_v13().sku, "MOJ-PROP-01")
        self.assertNotEqual(draft_gold_terms_v13().sku, "MOJPROP-STARTER30")

    def test_native_tron_fee_only(self):
        x = draft_gold_terms_v13()
        self.assertEqual((x.network, x.entry_sun), ("TRON-mainnet", 30_000_000))

    def test_previous_contract_not_replaced(self):
        x = draft_gold_terms_v13()
        self.assertEqual(x.previous_contract_version, "2026-11-15/v1.2")
        self.assertEqual(POLICY.version, "2026-11-15/v1.2")
        self.assertEqual(x.contract_version, DRAFT_CONTRACT_VERSION)
        self.assertNotEqual(x.previous_contract_version, x.contract_version)

    def test_two_demo_targets(self):
        x = draft_gold_terms_v13()
        self.assertEqual((x.stage_one_profit_target_pct, x.stage_two_profit_target_pct),
                         (Decimal("9.6"), Decimal("6")))

    def test_fifty_closed_trades_total(self):
        x = draft_gold_terms_v13()
        self.assertEqual(x.min_closed_trades_total, 50)
        self.assertIn("50 independently verified CLOSED positions TOTAL", x.en)
        self.assertIn("۵۰ معامله", x.fa)

    def test_min_six_trading_days_each_stage(self):
        x = draft_gold_terms_v13()
        self.assertEqual(x.min_trading_days_per_stage, 6)
        self.assertIn("six verified trading days in EACH phase", x.en)

    def test_twenty_eight_day_window(self):
        self.assertEqual(draft_gold_terms_v13().evaluation_days, 28)

    def test_new_instrument_and_risk_caps(self):
        x = draft_gold_terms_v13()
        self.assertEqual((x.instrument, x.risk_per_order_pct, x.open_risk_pct),
                         ("XAUUSD", Decimal("3"), Decimal("8")))

    def test_both_drawdown_caps_retained(self):
        x = draft_gold_terms_v13()
        self.assertEqual((x.daily_drawdown_pct, x.total_drawdown_pct),
                         (Decimal("4"), Decimal("8")))

    def test_posted_profit_split_retained(self):
        x = draft_gold_terms_v13()
        self.assertEqual((x.trader_share_pct, x.organizer_share_pct),
                         (Decimal("70"), Decimal("30")))

    def test_conditional_real_account_not_gifted(self):
        x = draft_gold_terms_v13()
        self.assertEqual(x.initial_real_allocation_usd, Decimal("100"))
        self.assertFalse(x.independently_financed_account_verified)
        self.assertFalse(x.broker_live_trading_approved)

    def test_single_either_platform_post_is_proposed_for_28_days(self):
        x = draft_gold_terms_v13()
        self.assertEqual((x.instagram_posts_required, x.facebook_posts_required), (0, 0))
        self.assertEqual(x.minimum_posts_on_either_platform, 1)
        self.assertEqual(x.continuous_visibility_days, 28)
        self.assertIn("EITHER Instagram", x.en)
        self.assertIn("OR Facebook", x.en)
        self.assertIn("28 days", x.en)
        self.assertIn("۲۸ روز", x.fa)

    def test_social_rule_never_self_authorizes_platform_or_buyer_consent(self):
        x = draft_gold_terms_v13()
        self.assertFalse(x.social_legality_independently_approved)
        self.assertFalse(x.social_customer_terms_signed)
        self.assertFalse(x.customer_contract_signed)
        self.assertFalse(x.checkout_enabled)

    def test_payment_enrollment_execution_all_disabled(self):
        x = draft_gold_terms_v13()
        self.assertFalse(x.checkout_enabled)
        self.assertFalse(x.invoice_created)
        self.assertFalse(x.enrollment_created)
        self.assertFalse(x.order_execution_enabled)
        self.assertFalse(x.payout_enabled)

    def test_not_a_signed_contract(self):
        x = draft_gold_terms_v13()
        self.assertFalse(x.customer_contract_signed)
        self.assertTrue(x.historical_terms_conflict_open)

    def test_digest_stable_sha256(self):
        a,b = draft_gold_terms_v13(), draft_gold_terms_v13()
        self.assertEqual(a.digest_sha256,b.digest_sha256)
        self.assertRegex(a.digest_sha256,r"^[0-9a-f]{64}$")

    def test_best_day_cap_is_disclosed_fa_en(self):
        x = draft_gold_terms_v13()
        self.assertEqual(x.max_profitable_day_share_pct, Decimal("32"))
        self.assertIn("32% of independently verified net profit", x.en)
        self.assertIn("۳۲٪", x.fa)

    def test_waiver_digest_is_bound_in_customer_draft(self):
        waiver = buyer_no_social_post_amendment()
        x = draft_gold_terms_v13()
        self.assertEqual(x.social_waiver_digest_sha256, waiver.digest_sha256)
        self.assertRegex(x.social_waiver_digest_sha256, r"^[0-9a-f]{64}$")

    def test_best_day_rule_drift_blocks_new_buyer_terms(self):
        with patch("prop_firm.xauusd_v13_draft_terms.POLICY",
                   replace(POLICY,best_day_share_pct=Decimal("40"))):
            with self.assertRaises(ValueError):
                draft_gold_terms_v13()

    def test_plan_best_day_cap_drift_blocks_new_terms(self):
        p = plan_for_code(SKU)
        with patch("prop_firm.xauusd_v13_draft_terms.plan_for_code",
                   return_value=replace(p,max_consistency_pct=Decimal("50"))):
            with self.assertRaises(ValueError):
                draft_gold_terms_v13()

    def test_legacy_rule_drift_blocks_draft(self):
        with patch("prop_firm.xauusd_v13_draft_terms.POLICY",
                   replace(POLICY,min_closed_trades_per_challenge=100)):
            with self.assertRaises(ValueError):
                draft_gold_terms_v13()

    def test_legacy_checkout_enabled_blocks_draft(self):
        with patch("prop_firm.xauusd_v13_draft_terms.POLICY",
                   replace(POLICY,trx_checkout_enabled=True)):
            with self.assertRaises(ValueError):
                draft_gold_terms_v13()

    def test_legacy_plan_price_drift_blocks_draft(self):
        p = plan_for_code(SKU)
        with patch("prop_firm.xauusd_v13_draft_terms.plan_for_code",
                   return_value=replace(p,entry_fee_trx=Decimal("35"))):
            with self.assertRaises(ValueError):
                draft_gold_terms_v13()

    def test_legacy_plan_checkout_flag_blocks_draft(self):
        p = plan_for_code(SKU)
        with patch("prop_firm.xauusd_v13_draft_terms.plan_for_code",
                   return_value=replace(p,checkout_enabled=True)):
            with self.assertRaises(ValueError):
                draft_gold_terms_v13()

    def test_social_waiver_drift_blocks_draft(self):
        waiver = buyer_no_social_post_amendment()
        with patch("prop_firm.xauusd_v13_draft_terms.buyer_no_social_post_amendment",
                   return_value=replace(waiver,instagram_posts_required=1)):
            with self.assertRaises(ValueError):
                draft_gold_terms_v13()

    def test_legacy_public_copy_change_forces_review(self):
        with patch("prop_firm.xauusd_v13_draft_terms.PREPURCHASE_DISCLOSURES",
                   ("irrelevant","modified")):
            with self.assertRaises(ValueError):
                draft_gold_terms_v13()


if __name__ == "__main__":
    unittest.main()
