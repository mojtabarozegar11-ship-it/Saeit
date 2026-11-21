"""New English MOJ PROP scorer parity: 50% best-day and 100% earned profit.

All test inputs are synthetic and in-process. No live invoice, settlement,
broker, customer record, outgoing email or social publication is performed.
Legacy version is explicit; it never becomes the default for new customers.
"""
from decimal import Decimal as D
from django.test import SimpleTestCase

from prop_firm.rules import (
    POLICY,
    _consistency_reasons,
    assess_challenge,
    assess_risk,
    authorize_order,
    calculate_payout,
)
from prop_firm.social_policy import (
    BLOCKED_OWNER_PROFILE,
    LEGACY_CONTRACT_VERSION,
    NEW_CONTRACT_VERSION,
    valid_platform_post_url,
)
from prop_firm.simulation_policy import SIMULATION_POLICY
from prop_firm.starter30_paid_admission import paid_admission_defects


class CurrentVerifiedScoringRulesTests(SimpleTestCase):
    def test_latest_approved_policy_is_virtual_60_day_and_50_100_split(self):
        self.assertEqual(POLICY.version, NEW_CONTRACT_VERSION)
        self.assertEqual(POLICY.version, SIMULATION_POLICY.contract_version)
        self.assertEqual(POLICY.best_day_share_pct, D("50"))
        self.assertEqual(POLICY.trader_profit_share_pct, D("100"))
        self.assertEqual(POLICY.company_profit_share_pct, D("0"))
        self.assertEqual(POLICY.completion_deadline_days, 60)
        self.assertEqual(POLICY.max_daily_loss_pct, D("6"))
        self.assertEqual(POLICY.order_risk_pct, D("3"))
        self.assertEqual(POLICY.aggregate_risk_pct, D("4"))
        self.assertEqual(POLICY.account_mode, "simulated")
        self.assertEqual(POLICY.payout_mode, "real_performance_reward")
        self.assertFalse(POLICY.real_orders_enabled)

    def test_profit_100_entitles_trader_100_company_zero_new_version(self):
        result = calculate_payout(
            cumulative_realized_net_profit="100",
            previously_allocated_profit="0",
        )
        self.assertEqual(result.eligible_profit_usd, D("100.00"))
        self.assertEqual(result.trader_usd, D("100.00"))
        self.assertEqual(result.company_usd, D("0.00"))
        self.assertEqual(result.new_allocated_high_water_usd, D("100.00"))

    def test_high_water_loss_recovery_prevents_double_allocation(self):
        result = calculate_payout(
            cumulative_realized_net_profit="80",
            previously_allocated_profit="100",
        )
        self.assertEqual(result.eligible_profit_usd, D("0.00"))
        self.assertEqual(result.trader_usd, D("0.00"))
        self.assertEqual(result.new_allocated_high_water_usd, D("100.00"))
        advanced = calculate_payout(
            cumulative_realized_net_profit="120.50",
            previously_allocated_profit="100",
        )
        self.assertEqual(advanced.eligible_profit_usd, D("20.50"))
        self.assertEqual(advanced.trader_usd, D("20.50"))
        self.assertEqual(advanced.company_usd, D("0.00"))

    def test_legacy_70_30_is_preserved_only_when_legacy_version_explicit(self):
        past = calculate_payout(
            cumulative_realized_net_profit="100",
            previously_allocated_profit="0",
            contract_version=LEGACY_CONTRACT_VERSION,
        )
        self.assertEqual(past.trader_usd, D("70.00"))
        self.assertEqual(past.company_usd, D("30.00"))
        current = calculate_payout(
            cumulative_realized_net_profit="100",
            previously_allocated_profit="0",
            contract_version=NEW_CONTRACT_VERSION,
        )
        self.assertEqual(current.trader_usd, D("100.00"))
        self.assertEqual(current.company_usd, D("0.00"))

    def test_unknown_contract_is_rejected_not_silently_legacy(self):
        with self.assertRaisesRegex(ValueError, "Unknown immutable"):
            calculate_payout(
                cumulative_realized_net_profit="100",
                previously_allocated_profit="0",
                contract_version="unknown",
            )
        with self.assertRaisesRegex(ValueError, "Unknown immutable"):
            _consistency_reasons(
                verified_profit=D("100"),
                max_profitable_day=D("40"),
                contract_version="unknown",
            )

    def test_best_day_40pct_passes_new_50pct_but_not_legacy_32pct(self):
        self.assertEqual(
            _consistency_reasons(
                verified_profit=D("100"), max_profitable_day=D("40"),
                contract_version=NEW_CONTRACT_VERSION,
            ), (),
        )
        self.assertEqual(
            _consistency_reasons(
                verified_profit=D("100"), max_profitable_day=D("40"),
                contract_version=LEGACY_CONTRACT_VERSION,
            ), ("profit_consistency_not_met",),
        )
        self.assertIn(
            "profit_consistency_not_met",
            _consistency_reasons(
                verified_profit=D("100"), max_profitable_day=D("50.01"),
            ),
        )

    def test_challenge_phase_one_evaluates_new_vs_historical_best_day(self):
        state = assess_risk(
            account_capital="1000", equity="1050", day_open_equity="1000",
        )
        params = dict(
            phase=1, account_capital="1000", realized_net_profit="100",
            trading_days=6, max_profitable_day="40", risk=state,
            evidence_verified=True,
        )
        self.assertTrue(assess_challenge(**params).passed)
        old = assess_challenge(**params, contract_version=LEGACY_CONTRACT_VERSION)
        self.assertFalse(old.passed)
        self.assertIn("profit_consistency_not_met", old.reasons)

    def test_breach_at_daily_loss_floor_is_rejected(self):
        result = assess_risk(
            account_capital="1000", equity="940", day_open_equity="1000",
        )
        self.assertFalse(result.allowed)
        self.assertIn("daily_loss_floor_reached", result.reasons)

    def test_real_execution_remains_disabled_despite_qualified_simulator(self):
        params = dict(
            account_capital="1000", equity="1000", day_open_equity="1000",
            risk_at_stop="20", open_risk_before="10", broker_minimum_risk="0",
            verified_stop=True, authoritative_snapshot=True,
        )
        sim = authorize_order(**params, mode="challenge")
        self.assertTrue(sim.allowed)
        live = authorize_order(**params, mode="real", execution_authorized=True)
        self.assertFalse(live.allowed)
        self.assertIn("real_execution_disabled", live.reasons)

    def test_new_commercial_contract_source_checks_pass_without_cash_attestation(self):
        self.assertEqual(paid_admission_defects(check_attestations=False), ())
        # This is not an owner reserve/payment attestation and never permits
        # a live invoice on its own.
        self.assertTrue(paid_admission_defects(check_attestations=True))

    def test_never_post_to_owner_restricted_instagram_handle(self):
        self.assertEqual(BLOCKED_OWNER_PROFILE, "dr.mojtaba.rozegar")
        self.assertFalse(
            valid_platform_post_url(
                "https://www.instagram.com/dr.mojtaba.rozegar/p/any",
                "instagram",
            )
        )
        self.assertFalse(
            valid_platform_post_url(
                "https://www.instagram.com/p/foo?q=bar", "instagram",
            )
        )
