"""Ten distinct prelaunch capital plans, one immutable shared challenge policy."""
from decimal import Decimal
from django.test import SimpleTestCase
from prop_firm.plans import (
    CHALLENGE_PLANS, PLAN_BY_CODE, PLAN_PREFIX, DEFAULT_PLAN_CODE,
    plan_for_code, plan_public_summary, ALL_PLANS_SELLABLE,
)
from prop_firm.rules import POLICY, LEVELS


class TenChallengePlansTests(SimpleTestCase):
    def test_exactly_ten_unique_codes_and_starting_tiers(self):
        self.assertEqual(len(CHALLENGE_PLANS),10)
        self.assertEqual(len(PLAN_BY_CODE),10)
        self.assertEqual(len({p.code for p in CHALLENGE_PLANS}),10)
        self.assertEqual(len({p.starting_tier_index for p in CHALLENGE_PLANS}),10)
        self.assertEqual([p.code for p in CHALLENGE_PLANS],
                         [f"MOJ-PROP-{n:02d}" for n in range(1,11)])

    def test_owner_plan_one_preserves_original_fee_capital_and_level_ladder(self):
        p=CHALLENGE_PLANS[0]
        self.assertEqual(p.code, DEFAULT_PLAN_CODE)
        self.assertEqual(p.entry_fee_trx, POLICY.entry_trx)
        self.assertEqual(p.entry_fee_trx, Decimal("30"))
        self.assertEqual(p.starting_capital_usd, Decimal("100"))
        self.assertEqual(p.starting_tier_index,0)
        self.assertEqual(p.maximum_capital_usd, Decimal("100000"))
        self.assertEqual(len(LEVELS),14)

    def test_all_nine_added_plans_have_distinct_starting_capital(self):
        p=CHALLENGE_PLANS
        self.assertEqual([int(z.starting_capital_usd) for z in p],
                         [100,200,400,800,1500,3000,5000,10000,20000,35000])
        self.assertEqual([int(z.entry_fee_trx) for z in p],
                         [30,45,75,120,200,330,500,800,1250,2000])
        self.assertTrue(all(a.entry_fee_trx < b.entry_fee_trx
                            for a,b in zip(p,p[1:])))

    def test_identical_risk_targets_bots_and_social_rules_for_all_ten(self):
        for plan in CHALLENGE_PLANS:
            with self.subTest(plan=plan.code):
                self.assertEqual(plan.duration_days,28)
                self.assertEqual(plan.minimum_verified_closed_trades,50)
                self.assertEqual(plan.min_trading_days_per_stage,6)
                self.assertEqual(plan.stage_one_profit_target_pct,Decimal("9.6"))
                self.assertEqual(plan.stage_two_profit_target_pct,Decimal("6"))
                self.assertEqual(plan.daily_loss_limit_pct,Decimal("4"))
                self.assertEqual(plan.total_loss_limit_pct,Decimal("8"))
                self.assertEqual(plan.max_consistency_pct,Decimal("32"))
                self.assertEqual(plan.max_risk_per_trade_pct,Decimal("0.8"))
                self.assertEqual(plan.max_open_risk_pct,Decimal("1.6"))
                self.assertEqual(plan.trader_profit_share_pct,Decimal("70"))
                self.assertEqual(plan.company_profit_share_pct,Decimal("30"))
                self.assertEqual(plan.instagram_posts_per_challenge,1)
                self.assertEqual(plan.facebook_posts_per_challenge,1)
                self.assertTrue(plan.trader_bots_allowed)
                self.assertEqual(plan.maximum_capital_usd,LEVELS[-1])

    def test_plan_one_owner_declared_active_and_funded(self):
        plan = CHALLENGE_PLANS[0]
        self.assertEqual(plan.business_status, "owner_declared_active")
        self.assertTrue(plan.business_active_owner_declared)
        self.assertTrue(plan.capital_funded_owner_declared)
        self.assertFalse(plan.temporary_owner_hold)
        self.assertFalse(plan.funding_independently_verified)
        self.assertFalse(plan.broker_live_account_independently_verified)

    def test_other_nine_under_funding_and_temporarily_inactive(self):
        for plan in CHALLENGE_PLANS[1:]:
            with self.subTest(code=plan.code):
                self.assertEqual(plan.business_status, "funding_in_progress_temporary_inactive")
                self.assertTrue(plan.temporary_owner_hold)
                self.assertFalse(plan.business_active_owner_declared)
                self.assertFalse(plan.capital_funded_owner_declared)
                self.assertFalse(plan.checkout_enabled)

    def test_owner_claim_distinguished_from_live_payment_and_bank_proof(self):
        summary = plan_public_summary(CHALLENGE_PLANS[0])
        self.assertTrue(summary["business_active_owner_declared"])
        self.assertTrue(summary["capital_funded_owner_declared"])
        self.assertFalse(summary["funding_independently_verified"])
        self.assertFalse(summary["broker_live_account_independently_verified"])
        self.assertFalse(summary["checkout_enabled"])
        self.assertFalse(summary["real_funding_guaranteed"])
        self.assertFalse(summary["fee_is_final_for_sale"])
        self.assertEqual(sum(p.business_active_owner_declared for p in CHALLENGE_PLANS), 1)
        self.assertEqual(sum(p.temporary_owner_hold for p in CHALLENGE_PLANS), 9)

    def test_no_challenge_product_can_be_purchased_prematurely(self):
        self.assertFalse(ALL_PLANS_SELLABLE)
        for plan in CHALLENGE_PLANS:
            with self.subTest(plan=plan.code):
                self.assertFalse(plan.checkout_enabled)
                self.assertFalse(plan.account_activation_enabled)
                self.assertFalse(plan.prices_approved_for_public_sale)
                summary=plan_public_summary(plan)
                self.assertFalse(summary["checkout_enabled"])
                self.assertFalse(summary["fee_is_final_for_sale"])
                self.assertFalse(summary["real_funding_guaranteed"])

    def test_exact_plan_lookup_rejects_user_tampering(self):
        for invalid in (None,"", "MOJ-PROP-00", "MOJ-PROP-11", "moj-prop-01",
                        "MOJ-PROP-01/", 1, True, [], {}, "MOJ-PROP-010"):
            with self.subTest(value=str(invalid)), self.assertRaises(ValueError):
                plan_for_code(invalid)

    def test_plan_summaries_are_canonical_not_faked(self):
        from dataclasses import replace
        with self.assertRaises(ValueError):
            plan_public_summary(replace(CHALLENGE_PLANS[0],
                                        entry_fee_trx=Decimal("0")))
        self.assertEqual(plan_public_summary(CHALLENGE_PLANS[9])["number"],10)

    def test_starting_tier_indices_match_canonical_14_step_ladder(self):
        for plan in CHALLENGE_PLANS:
            self.assertEqual(plan.starting_capital_usd,
                             LEVELS[plan.starting_tier_index])
            self.assertLessEqual(plan.starting_capital_usd,
                                 plan.maximum_capital_usd)
