"""Moj Prop fee eligibility must not become unauthorized TRON payment."""
from django.test import SimpleTestCase
from core.tron_tenant_policy import (
    CANONICAL_ASSET, CANONICAL_CHAIN, REQUIRED_ATTESTATIONS,
    registered_scope,
)
from prop_firm.challenge_commerce import REQUIRED, assess_challenge_checkout


TRON_REGISTRY = {
    ("mojplaywin.com", "moj_prop"): {
        "tenant_id": "moj_prop",
        "network": CANONICAL_CHAIN,
        "asset": CANONICAL_ASSET,
        **{name: True for name in REQUIRED_ATTESTATIONS},
    },
    ("mojplaywin.com", "saman"): {
        "tenant_id": "signal_saman",
        "network": CANONICAL_CHAIN,
        "asset": CANONICAL_ASSET,
        **{name: True for name in REQUIRED_ATTESTATIONS},
    },
}


class MojPropChallengeCheckoutSafetyTests(SimpleTestCase):
    def tenant(self, brand="moj_prop"):
        return registered_scope(
            host="mojplaywin.com", brand=brand, registry=TRON_REGISTRY
        )

    def ready(self, **change):
        kwargs = {
            "merchant_tenant": self.tenant(),
            "free_treasury_usd": "100000",
            "protected_reserves_usd": "10000",
            "existing_commitments_usd": "0",
            "required_first_tier_accounts": 1,
            "attestations": {item: True for item in REQUIRED},
        }
        kwargs.update(change)
        return assess_challenge_checkout(**kwargs)

    def test_thirty_trx_14_tiers_and_50k_level_11(self):
        from prop_firm.rules import LEVELS
        x = self.ready()
        self.assertEqual(x.fee_trx, 30)
        self.assertEqual(x.first_real_tier_usd, 100)
        self.assertEqual(x.final_tier_usd, 100000)
        self.assertEqual(LEVELS[10], 50000)
        self.assertEqual(len(LEVELS), 14)

    def test_even_complete_evidence_is_not_auto_checkout(self):
        x = self.ready()
        self.assertTrue(x.eligible_for_external_legal_review)
        self.assertFalse(x.checkout_enabled)
        self.assertFalse(x.invoice_created)
        self.assertFalse(x.trading_enabled)

    def test_each_missing_condition_blocks_paying_challenge(self):
        for gate in REQUIRED:
            with self.subTest(gate=gate):
                flags = {item: True for item in REQUIRED}
                flags[gate] = False
                x = self.ready(attestations=flags)
                self.assertFalse(x.eligible_for_external_legal_review)
                self.assertIn(gate, x.blockers)

    def test_truthy_approvals_cannot_satisfy_legal_requirements(self):
        x = self.ready(attestations={item: "yes" for item in REQUIRED})
        self.assertFalse(x.eligible_for_external_legal_review)
        self.assertEqual(len(x.blockers), len(REQUIRED))

    def test_no_audited_treasury_rejects_initial_funding(self):
        x = self.ready(free_treasury_usd=0)
        self.assertIn("real_initial_account_capital_shortfall", x.blockers)
        self.assertEqual(x.capital_shortfall_usd, 100)

    def test_fee_revenue_does_not_count_as_treasury_backing(self):
        x = self.ready(free_treasury_usd=0, protected_reserves_usd=0)
        self.assertEqual(x.maximum_initial_funded_accounts, 0)
        self.assertEqual(x.fee_trx, 30)

    def test_reserved_cash_not_spendable(self):
        x = self.ready(free_treasury_usd=1000, protected_reserves_usd=950)
        self.assertEqual(x.maximum_initial_funded_accounts, 0)
        self.assertEqual(x.capital_shortfall_usd, 50)

    def test_existing_funded_commitments_reduced_before_new_offer(self):
        x = self.ready(free_treasury_usd=1000, protected_reserves_usd=100,
                       existing_commitments_usd=850)
        self.assertEqual(x.maximum_initial_funded_accounts, 0)

    def test_zero_or_fake_cohort_cannot_unlock_paid_prop_review(self):
        for forged in (0, -1, True, False, "1", 1.0, 10001):
            with self.subTest(value=repr(forged)), self.assertRaises(ValueError):
                self.ready(required_first_tier_accounts=forged)

    def test_single_real_cohort_keeps_existing_safe_preflight_behavior(self):
        result = self.ready(required_first_tier_accounts=1)
        self.assertTrue(result.eligible_for_external_legal_review)
        self.assertFalse(result.checkout_enabled)
        self.assertFalse(result.trading_enabled)

    def test_larger_cohort_requires_real_capacity(self):
        x = self.ready(free_treasury_usd=1000, protected_reserves_usd=0,
                       required_first_tier_accounts=11)
        self.assertIn("real_initial_account_capital_shortfall", x.blockers)
        self.assertEqual(x.capital_shortfall_usd, 100)

    def test_wrong_signal_tenant_never_sells_prop_challenge(self):
        x = self.ready(merchant_tenant=self.tenant("saman"))
        self.assertIn("dedicated_moj_prop_tron_merchant_not_verified", x.blockers)

    def test_unapproved_tenant_never_sells_prop_challenge(self):
        tenant = registered_scope(host="mojplaywin.com", brand="moj_prop")
        x = self.ready(merchant_tenant=tenant)
        self.assertFalse(x.eligible_for_external_legal_review)

    def test_bad_attestations_rejected(self):
        for value in ("yes", True, (), []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.ready(attestations=value)

    def test_negative_amounts_rejected(self):
        for amount in ("-10", -1):
            with self.subTest(value=amount), self.assertRaises(ValueError):
                self.ready(free_treasury_usd=amount)

    def test_float_currency_is_not_accepted(self):
        with self.assertRaises(ValueError):
            self.ready(free_treasury_usd=1000.0)

    def test_minimum_integer_cohort_and_exact_currency(self):
        x = self.ready(required_first_tier_accounts=900)
        self.assertEqual(x.maximum_initial_funded_accounts, 900)
        self.assertTrue(x.eligible_for_external_legal_review)

    def test_excessive_requested_cohort_is_blocked(self):
        x = self.ready(required_first_tier_accounts=901)
        self.assertFalse(x.eligible_for_external_legal_review)
        self.assertEqual(x.capital_shortfall_usd, 100)

    def test_no_private_account_or_invoice_is_mutated(self):
        x = self.ready()
        self.assertFalse(hasattr(x, "create_invoice"))
        self.assertFalse(hasattr(x, "place_order"))
