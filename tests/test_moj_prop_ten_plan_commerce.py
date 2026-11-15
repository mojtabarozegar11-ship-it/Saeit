"""Higher-tier offers require real tier-specific treasury, broker and fee approval."""
from decimal import Decimal
from django.test import SimpleTestCase

from core.tron_tenant_policy import TenantDecision, REQUIRED_ATTESTATIONS
from prop_firm.challenge_commerce import REQUIRED, assess_challenge_checkout
from prop_firm.economics import estimate_cohort
from prop_firm.plans import CHALLENGE_PLANS, DEFAULT_PLAN_CODE

TENANT=TenantDecision("moj-prop-merchant","mojplaywin.com","moj_prop",True,())
TRUSTED_PROP_REGISTRY = {
    ("mojplaywin.com", "moj_prop"): {
        "tenant_id": "moj-prop-merchant",
        "network": "tron-mainnet", "asset": "TRX",
        **{key: True for key in REQUIRED_ATTESTATIONS},
    },
}


class TenPlanFundingReadinessTests(SimpleTestCase):
    def quote(self, code=DEFAULT_PLAN_CODE, *, cash="100000", reserve="2000",
              attestations=None, requested=1):
        evidence={gate:True for gate in REQUIRED}
        if attestations:
            evidence.update(attestations)
        return assess_challenge_checkout(
            merchant_tenant=TENANT,
            free_treasury_usd=cash,
            protected_reserves_usd=reserve,
            required_first_tier_accounts=requested,
            plan_code=code,
            attestations=evidence,
            trusted_merchant_registry=TRUSTED_PROP_REGISTRY,
        )

    def test_owner_first_plan_still_exact_30_trx_and_100_usd(self):
        x=self.quote()
        self.assertEqual(x.fee_trx,Decimal("30"))
        self.assertEqual(x.first_real_tier_usd,Decimal("100"))
        self.assertEqual(x.final_tier_usd,Decimal("100000"))
        self.assertEqual(x.plan_code,DEFAULT_PLAN_CODE)
        self.assertFalse(x.proposed_fee_not_live)
        self.assertFalse(x.checkout_enabled)

    def test_all_nine_added_plans_have_correct_capital_and_fee(self):
        for plan in CHALLENGE_PLANS[1:]:
            with self.subTest(plan=plan.code):
                x=self.quote(plan.code)
                self.assertEqual(x.fee_trx,plan.entry_fee_trx)
                self.assertEqual(x.first_real_tier_usd,plan.starting_capital_usd)
                self.assertEqual(x.final_tier_usd,Decimal("100000"))
                self.assertFalse(x.eligible_for_external_legal_review)
                self.assertFalse(x.checkout_enabled)
                self.assertFalse(x.invoice_created)
                self.assertFalse(x.trading_enabled)

    def test_new_plan_requires_three_independent_specific_attestations(self):
        x=self.quote("MOJ-PROP-10")
        self.assertIn("selected_plan_broker_lot_approved",x.blockers)
        self.assertIn("selected_plan_customer_terms_approved",x.blockers)
        self.assertIn("selected_plan_fee_approved",x.blockers)

    def test_large_starting_capital_shortfall_is_not_paid_by_entry_fee(self):
        evidence={x:True for x in (
            "selected_plan_broker_lot_approved",
            "selected_plan_customer_terms_approved",
            "selected_plan_fee_approved",
        )}
        x=self.quote("MOJ-PROP-10",cash="30000",reserve="1000",
                     attestations=evidence)
        self.assertEqual(x.first_real_tier_usd,Decimal("35000"))
        self.assertEqual(x.capital_shortfall_usd,Decimal("6000"))
        self.assertIn("real_initial_account_capital_shortfall",x.blockers)
        self.assertEqual(x.maximum_initial_funded_accounts,0)

    def test_full_treasury_attestations_are_review_only_not_live_sale(self):
        evidence={x:True for x in (
            "selected_plan_broker_lot_approved",
            "selected_plan_customer_terms_approved",
            "selected_plan_fee_approved",
        )}
        x=self.quote("MOJ-PROP-10",cash="40000",reserve="1000",
                     attestations=evidence)
        # All capital/contract attestation booleans cannot override the
        # owner's explicit temporary hold on Plans 2..10.
        self.assertFalse(x.eligible_for_external_legal_review)
        self.assertIn("plan_temporarily_inactive_pending_owner_funding", x.blockers)
        self.assertTrue(x.proposed_fee_not_live)
        self.assertTrue(x.temporarily_inactive_pending_funding)
        self.assertFalse(x.owner_declared_funded)
        self.assertFalse(x.checkout_enabled)
        self.assertFalse(x.invoice_created)

    def test_plan_one_owner_declared_active_and_funded_not_equivalent_to_bank_proof(self):
        decision = self.quote("MOJ-PROP-01", cash="300", reserve="100")
        self.assertTrue(decision.eligible_for_external_legal_review)
        self.assertEqual(decision.owner_declared_business_status, "owner_declared_active")
        self.assertTrue(decision.owner_declared_funded)
        self.assertFalse(decision.independent_capital_proof_on_record)
        self.assertFalse(decision.temporarily_inactive_pending_funding)
        self.assertFalse(decision.checkout_enabled)
        self.assertFalse(decision.invoice_created)
        self.assertFalse(decision.trading_enabled)

    def test_all_nine_plans_remain_on_hold_even_with_every_attestation(self):
        evidence = {key: True for key in (
            "selected_plan_broker_lot_approved",
            "selected_plan_customer_terms_approved",
            "selected_plan_fee_approved",
        )}
        for plan in CHALLENGE_PLANS[1:]:
            with self.subTest(code=plan.code):
                x = self.quote(plan.code, cash="1000000", reserve="0", attestations=evidence)
                self.assertIn("plan_temporarily_inactive_pending_owner_funding", x.blockers)
                self.assertFalse(x.eligible_for_external_legal_review)
                self.assertFalse(x.checkout_enabled)

    def test_100_dollar_broker_rule_not_applied_to_larger_starts(self):
        # The 100-USD minimum-lot certification is a Plan 1 contract,
        # replaced by selected_plan_broker_lot_approved for Plans 2-10.
        evidence = {"minimum_order_size_compatible_with_100_usd": False,
                    "selected_plan_broker_lot_approved": True,
                    "selected_plan_customer_terms_approved": True,
                    "selected_plan_fee_approved": True}
        large = self.quote("MOJ-PROP-10", cash="50000", reserve="0", attestations=evidence)
        self.assertNotIn("minimum_order_size_compatible_with_100_usd", large.blockers)
        self.assertIn("plan_temporarily_inactive_pending_owner_funding", large.blockers)
        first = self.quote("MOJ-PROP-01", cash="50000", reserve="0", attestations=evidence)
        self.assertIn("minimum_order_size_compatible_with_100_usd", first.blockers)

    def test_plan10_cohort_estimate_escrows_real_35000_per_passer(self):
        x=estimate_cohort(
            applicants=10,trx_usd_assumption="0.25",
            pass_rate_percent="20",plan_code="MOJ-PROP-10",
        )
        self.assertEqual(x.hypothetical_pass_count,2)
        self.assertEqual(x.trx_fees_total,Decimal("20000"))
        self.assertEqual(x.gross_fee_usd,Decimal("5000"))
        self.assertEqual(x.first_tier_escrow_requirement_usd,Decimal("70000"))
        self.assertEqual(x.ultimate_tier_capital_usd,Decimal("200000"))
        self.assertTrue(x.gross_revenue_not_actual)

    def test_plan6_cohort_funding_not_mistaken_for_plan1(self):
        x=estimate_cohort(
            applicants=10,trx_usd_assumption="0.25",
            pass_rate_percent="20",plan_code="MOJ-PROP-06",
        )
        self.assertEqual(x.trx_fees_total,Decimal("3300"))
        self.assertEqual(x.first_tier_escrow_requirement_usd,Decimal("6000"))
        self.assertEqual(x.plan_code,"MOJ-PROP-06")

    def test_bad_code_refused_before_treasury_calculation(self):
        with self.assertRaises(ValueError):
            self.quote("MOJ-PROP-99")
        with self.assertRaises(ValueError):
            estimate_cohort(
                applicants=5,trx_usd_assumption="0.25",
                pass_rate_percent="10",plan_code="MOJ-PROP-99",
            )
