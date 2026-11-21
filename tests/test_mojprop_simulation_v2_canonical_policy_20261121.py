"""Source-only regression: owner-approved English MOJ PROP simulation-v2.

Does not open a customer account, trigger TRON, send mail, or use production DB.
All tests operate on immutable Decimal policy and simulated risk calculations.
"""
from decimal import Decimal
import unittest

from prop_firm.rules import (
    POLICY, LEVELS, assess_risk, assess_challenge, calculate_payout, authorize_order,
)
from prop_firm.plans import CHALLENGE_PLANS, ALL_PLANS_SELLABLE
from prop_firm.policy_integrity import policy_integrity_report
from prop_firm.simulation_policy import SIMULATION_POLICY
from prop_firm.social_policy import (
    LEGACY_CONTRACT_VERSION, PREVIOUS_CONTRACT_VERSION, NEW_CONTRACT_VERSION,
)


class OwnerApprovedSimulationV2Tests(unittest.TestCase):
    def test_contract_version_and_simulated_only(self):
        self.assertEqual(NEW_CONTRACT_VERSION, "2026-11-21/simulation-v2")
        self.assertEqual(SIMULATION_POLICY.contract_version, NEW_CONTRACT_VERSION)
        self.assertEqual(POLICY.version, NEW_CONTRACT_VERSION)
        self.assertEqual(POLICY.account_mode, "simulated")
        self.assertFalse(POLICY.real_orders_enabled)
        self.assertFalse(POLICY.virtual_principal_withdrawable)
        self.assertFalse(POLICY.customer_deposit_required)

    def test_challenge_risk_and_duration(self):
        self.assertEqual(SIMULATION_POLICY.starting_balance_usd, Decimal("1000"))
        self.assertEqual(POLICY.completion_deadline_days, 60)
        self.assertEqual(POLICY.max_daily_loss_pct, Decimal("6"))
        self.assertEqual(POLICY.max_total_loss_pct, Decimal("8"))
        self.assertEqual(POLICY.order_risk_pct, Decimal("3"))
        self.assertEqual(POLICY.aggregate_risk_pct, Decimal("4"))
        self.assertEqual(POLICY.best_day_share_pct, Decimal("50"))

    def test_only_plan_one_can_be_considered_and_no_checkout_enablement(self):
        self.assertEqual(LEVELS[0], Decimal("1000"))
        self.assertEqual(len(LEVELS), 14)
        self.assertEqual(len(CHALLENGE_PLANS), 10)
        self.assertEqual(CHALLENGE_PLANS[0].starting_capital_usd, Decimal("1000"))
        self.assertEqual(CHALLENGE_PLANS[0].entry_fee_trx, Decimal("30"))
        self.assertEqual(CHALLENGE_PLANS[0].retry_fee_trx, Decimal("18"))
        self.assertTrue(CHALLENGE_PLANS[0].business_active_owner_declared)
        self.assertFalse(CHALLENGE_PLANS[0].checkout_enabled)
        self.assertFalse(ALL_PLANS_SELLABLE)
        self.assertTrue(all(p.temporary_owner_hold for p in CHALLENGE_PLANS[1:]))

    def test_integrity_preflight_is_no_longer_obsolete_v1_contract(self):
        result = policy_integrity_report()
        self.assertEqual(result["checked_invariants"], 23)
        self.assertEqual(result["defects"], [])
        self.assertEqual(result["canonical_contract_id"], NEW_CONTRACT_VERSION)
        self.assertFalse(result["payment_or_trading_authorized"])

    def test_best_day_exactly_half_can_pass_but_more_fails(self):
        risk = assess_risk(account_capital="1000", equity="1100", day_open_equity="1000")
        self.assertTrue(risk.allowed)
        kwargs = dict(
            phase=1, account_capital="1000", realized_net_profit="100",
            trading_days=6, risk=risk, evidence_verified=True,
        )
        accepted = assess_challenge(max_profitable_day="50", **kwargs)
        rejected = assess_challenge(max_profitable_day="50.01", **kwargs)
        self.assertTrue(accepted.passed)
        self.assertFalse(rejected.passed)
        self.assertIn("profit_consistency_not_met", rejected.reasons)

    def test_owner_approved_profit_request_rules_are_only_policy_not_transfer(self):
        self.assertEqual(SIMULATION_POLICY.first_profit_request_after_days, 14)
        self.assertEqual(SIMULATION_POLICY.subsequent_profit_request_interval_days, 14)
        self.assertEqual(SIMULATION_POLICY.minimum_profit_request_usd, Decimal("10"))
        self.assertTrue(SIMULATION_POLICY.company_pays_payout_network_fees)
        self.assertTrue(SIMULATION_POLICY.refund_initial_entry_on_first_successful_profit_payout)
        self.assertEqual(SIMULATION_POLICY.payout_mode, "real_performance_reward")

    def test_invoice_new_terms_match_exact_simulation_v2(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "prop_firm/starter30_live.py").read_text()
        self.assertIn("TERMS_REF = SIMULATION_POLICY.contract_version", source)
        self.assertIn("payment.invoice_owner.contract_version != TERMS_REF", source)
        self.assertIn("payment.terms_acceptance_ref != TERMS_REF", source)
        self.assertIn("previous.invoice_owner.contract_version != TERMS_REF", source)
        self.assertIn("if policy_drift_defects():", source)

    def test_new_customer_receives_all_verified_qualifying_profit(self):
        result = calculate_payout(
            cumulative_realized_net_profit="123.45",
            previously_allocated_profit="23.45",
            contract_version=NEW_CONTRACT_VERSION,
        )
        self.assertEqual(result.eligible_profit_usd, Decimal("100.00"))
        self.assertEqual(result.trader_usd, Decimal("100.00"))
        self.assertEqual(result.company_usd, Decimal("0.00"))

    def test_historical_versions_still_calculate_legacy_share(self):
        for historical in (LEGACY_CONTRACT_VERSION, PREVIOUS_CONTRACT_VERSION):
            with self.subTest(historical=historical):
                payout = calculate_payout(
                    cumulative_realized_net_profit="100",
                    previously_allocated_profit="0",
                    contract_version=historical,
                )
                self.assertEqual(payout.trader_usd, Decimal("70.00"))
                self.assertEqual(payout.company_usd, Decimal("30.00"))

    def test_unknown_payout_version_refused(self):
        with self.assertRaises(ValueError):
            calculate_payout(
                cumulative_realized_net_profit="100",
                previously_allocated_profit="0",
                contract_version="unapproved",
            )

    def test_real_execution_still_refused(self):
        decision = authorize_order(
            account_capital="1000", equity="1100", day_open_equity="1000",
            risk_at_stop="10", open_risk_before="0", broker_minimum_risk="0",
            verified_stop=True, authoritative_snapshot=True,
            mode="real", execution_authorized=True,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("real_execution_disabled", decision.reasons)


if __name__ == "__main__":
    unittest.main()
