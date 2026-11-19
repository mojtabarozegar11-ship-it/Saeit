"""Regression tests for the owner-directed simulation model."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from decimal import Decimal as D

from prop_firm.economics import simulated_cohort_economics
from prop_firm.plans import (
    CHALLENGE_PLANS,
    DEFAULT_PLAN_CODE,
    plan_public_summary,
)
from prop_firm.rules import LEVELS, POLICY, authorize_order
from prop_firm.simulation_policy import (
    SIMULATION_POLICY,
    estimate_reward_reserve,
)
from prop_firm.trade_count import count_challenge_trades


class SimulationPolicyTests(unittest.TestCase):
    def test_owner_simulation_baseline_is_canonical(self):
        self.assertEqual(SIMULATION_POLICY.account_mode, "simulated")
        self.assertEqual(SIMULATION_POLICY.starting_balance_usd, D("1000"))
        self.assertEqual(SIMULATION_POLICY.challenge_window_days, 60)
        self.assertEqual(SIMULATION_POLICY.daily_loss_limit_pct, D("6"))
        self.assertEqual(SIMULATION_POLICY.max_risk_per_trade_pct, D("3"))
        self.assertEqual(SIMULATION_POLICY.max_open_risk_pct, D("4"))
        self.assertFalse(SIMULATION_POLICY.virtual_principal_withdrawable)

    def test_consistency_proposal_is_not_canonical(self):
        self.assertEqual(SIMULATION_POLICY.canonical_best_day_share_pct, D("32"))
        self.assertEqual(SIMULATION_POLICY.proposed_best_day_share_pct, D("50"))
        self.assertEqual(POLICY.best_day_share_pct, D("32"))

    def test_ladder_starts_at_1000_and_ends_at_100000(self):
        self.assertEqual(LEVELS[0], D("1000"))
        self.assertEqual(LEVELS[-1], D("100000"))
        self.assertEqual(len(LEVELS), 14)

    def test_plan_one_has_retry_price_and_simulation_metadata(self):
        plan = CHALLENGE_PLANS[0]
        self.assertEqual(plan.code, DEFAULT_PLAN_CODE)
        self.assertEqual(plan.entry_fee_trx, D("30"))
        self.assertEqual(plan.retry_fee_trx, D("18"))
        self.assertEqual(plan.retry_discount_pct, D("40"))
        self.assertEqual(plan.starting_capital_usd, D("1000"))
        self.assertEqual(plan.duration_days, 60)
        self.assertEqual(plan.account_mode, "simulated")
        self.assertFalse(plan.virtual_principal_withdrawable)

    def test_higher_plans_remain_on_hold(self):
        self.assertTrue(all(plan.temporary_owner_hold for plan in CHALLENGE_PLANS[1:]))

    def test_public_summary_discloses_virtual_principal(self):
        summary = plan_public_summary(CHALLENGE_PLANS[0])
        self.assertEqual(summary["account_mode"], "simulated")
        self.assertEqual(summary["retry_fee_trx"], "18")
        self.assertFalse(summary["virtual_principal_withdrawable"])
        self.assertFalse(summary["real_funding_guaranteed"])

    def test_reward_reserve_rounds_claimants_up(self):
        result = estimate_reward_reserve(
            applicants=10,
            pass_rate_pct=D("14"),
            reward_claim_rate_pct=D("50"),
            average_reward_usd=D("25"),
            retry_applicants=2,
        )
        self.assertEqual(result.pass_count, 2)
        self.assertEqual(result.reward_claimants, 1)
        self.assertEqual(result.reward_reserve_usd, D("25"))
        self.assertEqual(result.total_revenue_trx, D("336"))

    def test_reward_reserve_never_uses_virtual_principal(self):
        result = simulated_cohort_economics(
            applicants=100,
            retry_applicants=20,
            trx_usd_assumption=D("0.30"),
            pass_rate_percent=D("14"),
            reward_claim_rate_percent=D("50"),
            average_reward_usd=D("20"),
        )
        self.assertEqual(result.virtual_principal_requirement_usd, D("0"))
        self.assertGreater(result.reward_reserve_usd, D("0"))

    def test_reward_reserve_rejects_rate_over_100(self):
        with self.assertRaises(ValueError):
            estimate_reward_reserve(
                applicants=1,
                pass_rate_pct=D("101"),
                reward_claim_rate_pct=D("50"),
                average_reward_usd=D("1"),
            )

    def test_reward_reserve_rejects_negative_reward(self):
        with self.assertRaises(ValueError):
            estimate_reward_reserve(
                applicants=1,
                pass_rate_pct=D("10"),
                reward_claim_rate_pct=D("50"),
                average_reward_usd=D("-1"),
            )

    def test_challenge_window_is_sixty_days_for_trade_count(self):
        paid = datetime(2026, 1, 1, tzinfo=timezone.utc)
        inside = SimpleNamespace(
            closed_at=paid + timedelta(days=59),
            reconciliation_status="verified",
            external_position_id="P-1",
            data_source="simulator-v1",
            execution_origin="manual",
        )
        result = count_challenge_trades((inside,), paid_at=paid)
        self.assertEqual(result.valid_closed_positions, 1)
        self.assertTrue(result.sufficient is False)

    def test_trade_at_day_sixty_is_out_of_window(self):
        paid = datetime(2026, 1, 1, tzinfo=timezone.utc)
        outside = SimpleNamespace(
            closed_at=paid + timedelta(days=60),
            reconciliation_status="verified",
            external_position_id="P-2",
            data_source="simulator-v1",
            execution_origin="manual",
        )
        result = count_challenge_trades((outside,), paid_at=paid)
        self.assertEqual(result.valid_closed_positions, 0)
        self.assertEqual(result.uncountable_events, 1)

    def test_duplicate_positions_count_once(self):
        paid = datetime(2026, 1, 1, tzinfo=timezone.utc)
        event = dict(
            closed_at=paid + timedelta(days=1),
            reconciliation_status="verified",
            external_position_id="P-3",
            data_source="simulator-v1",
            execution_origin="bot",
        )
        result = count_challenge_trades(
            (SimpleNamespace(**event), SimpleNamespace(**event)),
            paid_at=paid,
        )
        self.assertEqual(result.valid_closed_positions, 1)
        self.assertEqual(result.bot_positions, 1)

    def test_simulated_order_risk_uses_three_percent_and_four_percent(self):
        result = authorize_order(
            account_capital=D("1000"),
            equity=D("1000"),
            day_open_equity=D("1000"),
            risk_at_stop=D("20"),
            open_risk_before=D("10"),
            broker_minimum_risk=D("1"),
            verified_stop=True,
            authoritative_snapshot=True,
            mode="challenge",
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.daily_equity_floor, D("940"))

    def test_aggregate_open_risk_is_four_percent(self):
        result = authorize_order(
            account_capital=D("1000"),
            equity=D("1000"),
            day_open_equity=D("1000"),
            risk_at_stop=D("35"),
            open_risk_before=D("10"),
            broker_minimum_risk=D("1"),
            verified_stop=True,
            authoritative_snapshot=True,
            mode="challenge",
        )
        self.assertFalse(result.allowed)
        self.assertIn("aggregate_risk_limit", result.reasons)

    def test_real_execution_remains_disabled(self):
        result = authorize_order(
            account_capital=D("1000"),
            equity=D("1000"),
            day_open_equity=D("1000"),
            risk_at_stop=D("20"),
            open_risk_before=D("0"),
            broker_minimum_risk=D("1"),
            verified_stop=True,
            authoritative_snapshot=True,
            mode="real",
            execution_authorized=True,
        )
        self.assertFalse(result.allowed)
        self.assertIn("real_execution_disabled", result.reasons)

    def test_reward_reserve_is_included_in_net_model(self):
        result = simulated_cohort_economics(
            applicants=100,
            retry_applicants=0,
            trx_usd_assumption=D("0.30"),
            pass_rate_percent=D("14"),
            reward_claim_rate_percent=D("100"),
            average_reward_usd=D("10"),
            operating_cost_usd=D("5"),
        )
        self.assertEqual(result.reward_reserve_usd, D("20"))
        self.assertEqual(result.operating_cost_usd, D("5"))
        self.assertEqual(result.virtual_principal_requirement_usd, D("0"))


if __name__ == "__main__":
    unittest.main()
