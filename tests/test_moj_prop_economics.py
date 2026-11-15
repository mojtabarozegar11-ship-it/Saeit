"""Defensible Moj Prop cohort economics and real-capital capacity gate.

The cases deliberately do NOT represent real customer receipts or investment returns.
"""
import unittest
from decimal import Decimal

from prop_firm.economics import (
    capital_level, funded_capacity, estimate_cohort,
    trading_breakeven_win_rate, total_parallel_tier_commitment,
    conservative_realization_gate,
)


class MojPropEconomicsTests(unittest.TestCase):
    def test_exact_fourteen_levels(self):
        self.assertEqual(capital_level(0), Decimal("100"))
        self.assertEqual(capital_level(10), Decimal("50000"))
        self.assertEqual(capital_level(13), Decimal("100000"))

    def test_one_account_in_each_tier_needs_381000(self):
        self.assertEqual(total_parallel_tier_commitment(), Decimal("381000"))

    def test_disallow_invalid_tier(self):
        for value in (-1, 14, True, "0", 0.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                capital_level(value)

    def test_thirty_trx_per_customer_and_stated_usd_conversion(self):
        result = estimate_cohort(applicants=1000, trx_usd_assumption="0.30", pass_rate_percent=5)
        self.assertEqual(result.trx_fees_total, Decimal("30000"))
        self.assertEqual(result.gross_fee_usd, Decimal("9000"))
        self.assertEqual(result.hypothetical_pass_count, 50)
        self.assertEqual(result.first_tier_escrow_requirement_usd, 5000)
        self.assertEqual(result.ultimate_tier_capital_usd, 5000000)

    def test_conversion_is_explicit_assumption_not_a_quote(self):
        a = estimate_cohort(applicants=1, trx_usd_assumption=".20", pass_rate_percent=0)
        b = estimate_cohort(applicants=1, trx_usd_assumption=".40", pass_rate_percent=0)
        self.assertEqual(a.gross_fee_usd, Decimal("6"))
        self.assertEqual(b.gross_fee_usd, Decimal("12"))
        self.assertTrue(a.gross_revenue_not_actual)

    def test_provisioning_rounds_up_passes(self):
        result = estimate_cohort(applicants=21, trx_usd_assumption=".3", pass_rate_percent=5)
        self.assertEqual(result.hypothetical_pass_count, 2)

    def test_zero_applicants_does_not_create_revenue(self):
        result = estimate_cohort(applicants=0, trx_usd_assumption=".3", pass_rate_percent=5)
        self.assertEqual(result.gross_fee_usd, 0)
        self.assertEqual(result.ultimate_tier_capital_usd, 0)

    def test_all_applicants_may_pass(self):
        result = estimate_cohort(applicants=9, trx_usd_assumption=".3", pass_rate_percent=100)
        self.assertEqual(result.hypothetical_pass_count, 9)

    def test_fee_contribution_subtracts_all_costs(self):
        result = estimate_cohort(applicants=10, trx_usd_assumption=".3", pass_rate_percent=0,
                                 acquisition_cost_per_applicant_usd="2",
                                 payment_cost_per_applicant_usd=".5",
                                 support_cost_per_applicant_usd="1",
                                 allocated_overhead_usd="10")
        self.assertEqual(result.gross_fee_usd, 90)
        self.assertEqual(result.acquisition_cost_usd, 20)
        self.assertEqual(result.payment_cost_usd, 5)
        self.assertEqual(result.support_cost_usd, 10)
        self.assertEqual(result.fee_contribution_usd, 45)

    def test_negative_fee_contribution_is_not_hidden(self):
        result = estimate_cohort(applicants=10, trx_usd_assumption=".3", pass_rate_percent=10,
                                 acquisition_cost_per_applicant_usd="12")
        self.assertEqual(result.fee_contribution_usd, -30)

    def test_zero_fx_rate_forbidden(self):
        with self.assertRaises(ValueError):
            estimate_cohort(applicants=1, trx_usd_assumption=0, pass_rate_percent=1)

    def test_bad_pass_rate_forbidden(self):
        for value in (101, -1, "NaN", "Infinity", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                estimate_cohort(applicants=10, trx_usd_assumption=".3", pass_rate_percent=value)

    def test_float_currency_forbidden(self):
        for value in (0.30, -0.30):
            with self.subTest(value=value), self.assertRaises(ValueError):
                estimate_cohort(applicants=1, trx_usd_assumption=value, pass_rate_percent=5)

    def test_negative_acquisition_cost_forbidden(self):
        with self.assertRaises(ValueError):
            estimate_cohort(applicants=10, trx_usd_assumption=".3", pass_rate_percent=5,
                            acquisition_cost_per_applicant_usd=-5)

    def test_cash_capacity_only_unencumbered_cash(self):
        result = funded_capacity(tier_index=0, unencumbered_cash_usd=1000,
                                 protected_reserve_usd=100, operating_buffer_usd=100,
                                 already_committed_usd=300)
        self.assertEqual(result.net_allocable_usd, Decimal("500"))
        self.assertEqual(result.maximum_fully_funded_accounts, 5)

    def test_cash_capacity_cannot_promise_account_when_insufficient(self):
        result = funded_capacity(tier_index=0, unencumbered_cash_usd=30,
                                 protected_reserve_usd=0)
        self.assertEqual(result.maximum_fully_funded_accounts, 0)
        self.assertEqual(result.additional_needed_usd, 70)

    def test_cash_capacity_account_limit_floor(self):
        result = funded_capacity(tier_index=10, unencumbered_cash_usd=99999,
                                 protected_reserve_usd=100)
        self.assertEqual(result.maximum_fully_funded_accounts, 1)

    def test_overreserved_capital_cannot_be_spent(self):
        result = funded_capacity(tier_index=0, unencumbered_cash_usd=100,
                                 protected_reserve_usd=200)
        self.assertEqual(result.maximum_fully_funded_accounts, 0)
        self.assertEqual(result.additional_needed_usd, 100)

    def test_requested_accounts_shortfall(self):
        result = funded_capacity(tier_index=0, unencumbered_cash_usd=100,
                                 protected_reserve_usd=0, requested_new_accounts=3)
        self.assertEqual(result.additional_needed_usd, 200)

    def test_negative_commitments_forbidden(self):
        with self.assertRaises(ValueError):
            funded_capacity(tier_index=0, unencumbered_cash_usd=1000,
                            protected_reserve_usd=0, already_committed_usd=-1)

    def test_boolean_counts_are_not_accepted(self):
        with self.assertRaises(ValueError):
            estimate_cohort(applicants=True, trx_usd_assumption=".3", pass_rate_percent=0)
        with self.assertRaises(ValueError):
            funded_capacity(tier_index=0, unencumbered_cash_usd=1000,
                            protected_reserve_usd=0, requested_new_accounts=True)

    def test_trading_breakeven_3_pct_wins_and_3_pct_losses(self):
        result = trading_breakeven_win_rate(win_percent=3, loss_percent=3)
        self.assertAlmostEqual(result, Decimal("76.92307692307692307692307692"))

    def test_most_wins_are_not_profitable_when_profit_share_is_small(self):
        result = trading_breakeven_win_rate(win_percent=3, loss_percent=3,
                                             company_share_percent=10)
        self.assertGreater(result, Decimal("90"))

    def test_zero_loss_breakeven_is_zero(self):
        self.assertEqual(trading_breakeven_win_rate(win_percent=3, loss_percent=0), 0)

    def test_no_winning_margin_requires_all_winning_periods(self):
        self.assertEqual(trading_breakeven_win_rate(win_percent=0, loss_percent=3), 100)

    def test_no_win_and_no_loss_is_undefined(self):
        with self.assertRaises(ValueError):
            trading_breakeven_win_rate(win_percent=0, loss_percent=0)

    def test_invalid_profit_share_forbidden(self):
        with self.assertRaises(ValueError):
            trading_breakeven_win_rate(win_percent=3, loss_percent=3,
                                        company_share_percent=110)

    def gate(self, **overrides):
        values = dict(treasury_verified=True, legal_approved=True, broker_approved=True,
                      kyc_approved=True, customer_contract_approved=True,
                      available_cash_usd=150, tier_index=0, payout_reserve_usd=50)
        values.update(overrides)
        return conservative_realization_gate(**values)

    def test_all_readiness_conditions_required(self):
        self.assertTrue(self.gate()["eligible_for_human_review"])
        for name in ("treasury_verified", "legal_approved", "broker_approved",
                     "kyc_approved", "customer_contract_approved"):
            with self.subTest(name=name):
                decision = self.gate(**{name: False})
                self.assertFalse(decision["eligible_for_human_review"])
                self.assertFalse(decision["checks"][name])

    def test_readiness_claims_are_exact_booleans_only(self):
        self.assertFalse(self.gate(legal_approved=1)["eligible_for_human_review"])
        self.assertFalse(self.gate(broker_approved="yes")["eligible_for_human_review"])

    def test_insufficient_cash_blocks_human_review(self):
        decision = self.gate(available_cash_usd=100)
        self.assertFalse(decision["eligible_for_human_review"])
        self.assertEqual(decision["shortfall_usd"], Decimal("50"))

    def test_readiness_is_not_live_payment_or_trade_authorization(self):
        decision = self.gate()
        self.assertFalse(decision["live_trading_enabled"])
        self.assertFalse(decision["payment_collection_enabled"])


if __name__ == "__main__":
    unittest.main()
