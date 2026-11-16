"""Unittest-only disclosure safeguards; no customers, invoices or real funds."""
import hashlib
import json
import re
import unittest
from dataclasses import FrozenInstanceError, asdict, replace
from decimal import Decimal
from unittest.mock import patch

from prop_firm.plans import plan_for_code
from prop_firm.plan1_buyer_disclosure_v12 import (
    DOC_SCHEMA, NATIVE_SUN, NO_CHECKOUT, NETWORK, SKU,
    _source_values, buyer_disclosure,
)


class CanonicalPlan1BuyerDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.x = buyer_disclosure()

    def test_sku_is_exclusive_real_prop_plan_one(self):
        self.assertEqual(self.x.sku, "MOJ-PROP-01")

    def test_disclosure_is_not_starter30(self):
        self.assertNotEqual(self.x.sku, "MOJPROP-STARTER30")

    def test_exact_native_trx_network(self):
        self.assertEqual(self.x.network, "TRON-mainnet")

    def test_exact_integer_sun_amount(self):
        self.assertIs(type(self.x.fee_sun), int)
        self.assertEqual(self.x.fee_sun, 30_000_000)

    def test_currency_is_native_not_legacy_irr_usd(self):
        self.assertEqual(self.x.currency, "TRX_NATIVE")

    def test_fa_states_exact_price(self):
        self.assertIn("۳۰٬۰۰۰٬۰۰۰ SUN", self.x.fa)

    def test_en_states_exact_price(self):
        self.assertIn("30,000,000 SUN", self.x.en)

    def test_disclosure_has_v12_contract_version(self):
        self.assertEqual(self.x.contract_version, "2026-11-15/v1.2")

    def test_two_stages_are_simulated(self):
        self.assertIs(self.x.two_phases_simulated, True)
        self.assertIn("BOTH evaluation stages are simulated", self.x.en)

    def test_fa_is_explicit_about_simulated_phases(self):
        self.assertIn("هر دو مرحله ارزیابی شبیه‌سازی", self.x.fa)

    def test_28_day_starts_at_finalized_payment(self):
        self.assertIn("28-consecutive-day", self.x.en)
        self.assertIn("independently finalized payment", self.x.en)

    def test_fa_28_day_starts_at_settlement(self):
        self.assertIn("۲۸ روز", self.x.fa)
        self.assertIn("تأیید مستقل تسویه", self.x.fa)

    def test_closed_positions_total_is_fifty_not_per_phase(self):
        self.assertIn("50 distinct, reconciled CLOSED positions in total", self.x.en)

    def test_each_stage_requires_six_days(self):
        self.assertIn("6 verified trading days IN EACH stage", self.x.en)

    def test_phase_one_profit_goal(self):
        self.assertIn("9.6%", self.x.en)

    def test_phase_two_profit_goal(self):
        self.assertIn("then 6%", self.x.en)

    def test_daily_loss_is_four_percent(self):
        self.assertIn("loss 4%", self.x.en)

    def test_total_loss_is_eight_percent(self):
        self.assertIn("loss 8%", self.x.en)

    def test_best_day_consistency_is_32_percent(self):
        self.assertIn("32%", self.x.en)

    def test_risk_per_order_point_eight(self):
        self.assertIn("0.8%", self.x.en)

    def test_aggregate_open_risk_1_point_6(self):
        self.assertIn("1.6%", self.x.en)

    def test_real_account_is_contingent_on_actual_money(self):
        self.assertIn("CONDITIONAL", self.x.en)
        self.assertIn("genuine available capital allocation", self.x.en)
        self.assertEqual(self.x.initial_real_usd_conditional, "100")

    def test_fa_real_capital_is_conditional(self):
        self.assertIn("فقط در صورت", self.x.fa)
        self.assertIn("تخصیص واقعی سرمایه", self.x.fa)

    def test_capital_ladder_is_not_guaranteed(self):
        self.assertEqual(self.x.max_funded_usd_conditional, "100000")
        self.assertIn("not a guarantee", self.x.en)

    def test_profits_split_only_on_real_funded_account(self):
        self.assertIn("70% trader / 30% firm", self.x.en)
        self.assertIn("only eligible realized profit", self.x.en)

    def test_one_original_post_per_platform_total(self):
        self.assertIn("ONE original Instagram and ONE original Facebook post", self.x.en)
        self.assertIn("entire challenge", self.x.en)

    def test_social_posts_have_clear_incentive_disclosure(self):
        self.assertIn("commercial-relationship disclosure", self.x.en)

    def test_social_posts_28_day_retention(self):
        self.assertIn("retained for 28 days after posting", self.x.en)

    def test_owner_private_social_accounts_excluded(self):
        self.assertIn("owner's private social", self.x.en)

    def test_cancellation_refund_consumer_rights_stated(self):
        self.assertIn("cancellation and fair refunds", self.x.en)
        self.assertIn("استرداد", self.x.fa)

    def test_country_age_kyc_eligibility_disclosed(self):
        self.assertIn("age/country restrictions", self.x.en)
        self.assertIn("identity checks", self.x.en)

    def test_inquiry_not_marketing_optin(self):
        self.assertIn("neither marketing consent", self.x.en)

    def test_does_not_issue_invoice(self):
        self.assertFalse(self.x.invoice_issued)
        self.assertIn("issues NO invoice", self.x.en)

    def test_checkout_is_not_enabled_by_copy(self):
        self.assertFalse(self.x.checkout_enabled)

    def test_customer_signature_not_fabricated(self):
        self.assertFalse(self.x.customer_contract_signed)

    def test_settlement_not_fabricated(self):
        self.assertFalse(self.x.settlement_confirmed)

    def test_enrollment_not_created(self):
        self.assertFalse(self.x.challenge_enrollment_created)

    def test_capital_not_automatically_allocated(self):
        self.assertFalse(self.x.real_capital_allocated)

    def test_customer_marketing_optin_not_fabricated(self):
        self.assertFalse(self.x.customer_marketing_opt_in)

    def test_source_only_state_explicit(self):
        self.assertEqual(self.x.status, NO_CHECKOUT)

    def test_data_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.x.fee_sun = 100

    def test_digest_uses_exact_bilingual_copy_and_terms(self):
        d=asdict(self.x)
        digest=d.pop("digest_sha256")
        for field in (
            "status", "invoice_issued", "checkout_enabled",
            "customer_identity_verified", "customer_contract_signed",
            "settlement_confirmed", "challenge_enrollment_created",
            "real_capital_allocated", "customer_marketing_opt_in",
        ):
            d.pop(field)
        expected=hashlib.sha256(json.dumps(
            d,sort_keys=True,separators=(",",":"),ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")).hexdigest()
        self.assertEqual(digest,expected)

    def test_digest_repeated_calls_stable(self):
        self.assertEqual(self.x.digest_sha256,buyer_disclosure().digest_sha256)

    def test_both_languages_change_digest_when_wording_changes(self):
        self.assertNotEqual(self.x.digest_sha256,hashlib.sha256(
            (self.x.fa+self.x.en+"changed").encode("utf-8")).hexdigest())

    def test_digest_and_schema_are_strictly_shaped(self):
        self.assertEqual(self.x.schema,DOC_SCHEMA)
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{64}",self.x.digest_sha256))

    def test_fee_drift_blocks_buyer_copy(self):
        p=plan_for_code(SKU)
        with patch("prop_firm.plan1_buyer_disclosure_v12.plan_for_code",
                   return_value=replace(p,entry_fee_trx=Decimal("31"))):
            with self.assertRaises(ValueError):
                buyer_disclosure()

    def test_funding_drift_blocks_buyer_copy(self):
        p=plan_for_code(SKU)
        with patch("prop_firm.plan1_buyer_disclosure_v12.plan_for_code",
                   return_value=replace(p,starting_capital_usd=Decimal("1000"))):
            with self.assertRaises(ValueError):
                buyer_disclosure()

    def test_phase_goal_drift_blocks_buyer_copy(self):
        p=plan_for_code(SKU)
        with patch("prop_firm.plan1_buyer_disclosure_v12.plan_for_code",
                   return_value=replace(p,stage_one_profit_target_pct=Decimal("10"))):
            with self.assertRaises(ValueError):
                buyer_disclosure()

    def test_closed_trade_count_drift_blocks_buyer_copy(self):
        p=plan_for_code(SKU)
        with patch("prop_firm.plan1_buyer_disclosure_v12.plan_for_code",
                   return_value=replace(p,minimum_verified_closed_trades=60)):
            with self.assertRaises(ValueError):
                buyer_disclosure()

    def test_trading_days_drift_blocks_buyer_copy(self):
        p=plan_for_code(SKU)
        with patch("prop_firm.plan1_buyer_disclosure_v12.plan_for_code",
                   return_value=replace(p,min_trading_days_per_stage=5)):
            with self.assertRaises(ValueError):
                buyer_disclosure()

    def test_instagram_post_quota_drift_blocks_buyer_copy(self):
        p=plan_for_code(SKU)
        with patch("prop_firm.plan1_buyer_disclosure_v12.plan_for_code",
                   return_value=replace(p,instagram_posts_per_challenge=2)):
            with self.assertRaises(ValueError):
                buyer_disclosure()

    def test_facebook_post_quota_drift_blocks_buyer_copy(self):
        p=plan_for_code(SKU)
        with patch("prop_firm.plan1_buyer_disclosure_v12.plan_for_code",
                   return_value=replace(p,facebook_posts_per_challenge=2)):
            with self.assertRaises(ValueError):
                buyer_disclosure()


if __name__=="__main__":
    unittest.main()
