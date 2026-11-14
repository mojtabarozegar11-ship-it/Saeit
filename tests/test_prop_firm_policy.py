"""Regression tests for prop v1.1; standard-library only."""
import unittest
from decimal import Decimal as D
from prop_firm.rules import (
    POLICY, LEVELS, dec, assess_risk, assess_challenge, assess_promotion,
    calculate_payout, authorize_funding, authorize_order,
)

class PropFirmPolicyTests(unittest.TestCase):
    def risk(self, capital=100, equity=100, open_equity=100):
        return assess_risk(account_capital=capital, equity=equity, day_open_equity=open_equity)

    def challenge(self, **overrides):
        kwargs = dict(phase=1, account_capital=100, realized_net_profit="9.6",
                      trading_days=6, max_profitable_day=3, risk=self.risk(equity="110",
                      open_equity="110"), evidence_verified=True, social_posts_verified=True,
                      verified_cumulative_trades=50)
        kwargs.update(overrides)
        return assess_challenge(**kwargs)

    def test_product_contract(self):
        self.assertEqual(POLICY.entry_trx, D("30"))
        self.assertEqual(POLICY.canonical_bot, "mojtaba.bot.ai")
        self.assertEqual(POLICY.promotion_cycle_days, 30)
        self.assertEqual(POLICY.completion_deadline_days,28)
        self.assertEqual(POLICY.inactivity_notice_days + POLICY.inactivity_grace_days,28)

    def test_14_levels_and_confirmed_level_eleven(self):
        self.assertEqual((len(LEVELS), LEVELS[10], LEVELS[-1], sum(LEVELS)),
                         (14, D("50000"), D("100000"), D("381000")))

    def test_no_external_side_effect_flags(self):
        self.assertFalse(POLICY.real_orders_enabled)
        self.assertFalse(POLICY.trx_checkout_enabled)

    def test_float_nan_infinity_bool_rejected(self):
        for v in (0.1, True, "NaN", "Infinity", "bad"):
            with self.subTest(v=v), self.assertRaises(ValueError):
                dec(v)

    def test_daily_equity_floor_inclusive(self):
        self.assertIn("daily_loss_floor_reached",self.risk(equity=96).reasons)
        self.assertTrue(self.risk(equity="96.01").allowed)

    def test_total_equity_floor(self):
        self.assertIn("total_loss_floor_reached",self.risk(equity=92, open_equity=95).reasons)

    def test_challenge_first_phase_exact_target(self):
        self.assertTrue(self.challenge().passed)
        self.assertEqual(self.challenge().goal_usd,D("9.6"))

    def test_challenge_second_phase_requires_prior_stage(self):
        without=self.challenge(phase=2,realized_net_profit=6,max_profitable_day="1.8")
        self.assertFalse(without.passed)
        self.assertIn("phase_one_pass_required", without.reasons)
        with_prior=self.challenge(phase=2,realized_net_profit=6,
                                  max_profitable_day="1.8",prior_phase_passed=True)
        self.assertTrue(with_prior.passed)

    def test_no_unverified_challenge_pass(self):
        result=self.challenge(evidence_verified=False)
        self.assertFalse(result.passed)
        self.assertIn("reconciled_evidence_required",result.reasons)

    def test_minimum_challenge_days(self):
        self.assertIn("minimum_trading_days_not_met",self.challenge(trading_days=5).reasons)

    def test_consistency_restriction(self):
        self.assertIn("profit_consistency_not_met",
                      self.challenge(max_profitable_day="3.1").reasons)

    def test_challenge_refuses_failed_risk_decision_even_if_reasons_empty(self):
        from prop_firm.rules import RiskDecision
        blocked = RiskDecision(False, (), D("96"), D("92"))
        result = self.challenge(risk=blocked)
        self.assertFalse(result.passed)
        self.assertIn("risk_assessment_not_allowed", result.reasons)

    def test_promotion_refuses_failed_risk_without_reason_text(self):
        from prop_firm.rules import RiskDecision
        blocked = RiskDecision(False, (), D("96"), D("92"))
        result = assess_promotion(
            level_index=0, realized_monthly_profit="4",
            trading_days=12, max_profitable_day="1",
            risk=blocked, evidence_verified=True,
            funding_for_next_level=True,
        )
        self.assertFalse(result.eligible)
        self.assertIn("risk_assessment_not_allowed", result.reasons)

    def test_challenge_loss_breach_cannot_be_overridden_by_profit(self):
        self.assertFalse(self.challenge(risk=self.risk(equity=95)).passed)

    def test_promotion_exact_one_level_and_funding_gate(self):
        blocked=assess_promotion(level_index=0,realized_monthly_profit=4,
            trading_days=12,max_profitable_day=1,risk=self.risk(equity=104,open_equity=104),
            evidence_verified=True)
        self.assertFalse(blocked.eligible)
        self.assertEqual(blocked.next_level,D("200"))
        allowed=assess_promotion(level_index=0,realized_monthly_profit=4,
            trading_days=12,max_profitable_day=1,risk=self.risk(equity=104,open_equity=104),
            evidence_verified=True,funding_for_next_level=True)
        self.assertTrue(allowed.eligible)

    def test_no_level_beyond_100000(self):
        result=assess_promotion(level_index=13,realized_monthly_profit=4000,
            trading_days=12,max_profitable_day=1000,
            risk=self.risk(capital=100000,equity=104000,open_equity=104000),
            evidence_verified=True,funding_for_next_level=True)
        self.assertFalse(result.eligible)
        self.assertEqual(result.next_level,D("100000"))

    def test_70_30_settlement_and_loss_carryforward(self):
        first=calculate_payout(cumulative_realized_net_profit=50,previously_allocated_profit=0)
        self.assertEqual((first.trader_usd,first.company_usd),(D("35.00"),D("15.00")))
        down=calculate_payout(cumulative_realized_net_profit=20,
                              previously_allocated_profit=first.new_allocated_high_water_usd)
        self.assertEqual(down.eligible_profit_usd,0)
        recovered=calculate_payout(cumulative_realized_net_profit=70,
                              previously_allocated_profit=first.new_allocated_high_water_usd)
        self.assertEqual((recovered.eligible_profit_usd,recovered.trader_usd,recovered.company_usd),
                         (D("20.00"),D("14.00"),D("6.00")))
        fractional=calculate_payout(cumulative_realized_net_profit="0.03",previously_allocated_profit=0)
        self.assertEqual(fractional.trader_usd+fractional.company_usd,D("0.03"))

    def test_funding_blocked_without_cash_and_compliance(self):
        blocked=authorize_funding(requested_capital=100,unencumbered_cash=100,payout_reserve=10)
        self.assertFalse(blocked.authorized)
        self.assertIn("unencumbered_capital_insufficient",blocked.reasons)
        confirmed=authorize_funding(requested_capital=100,unencumbered_cash=110,
            payout_reserve=10,legal_approved=True,broker_approved=True,
            kyc_approved=True,contracts_signed=True)
        self.assertTrue(confirmed.authorized)

    def test_funding_rejects_capital_not_listed_in_fourteen_tiers(self):
        for capital in ("1", "99.99", "150", "100001"):
            with self.subTest(capital=capital):
                decision = authorize_funding(
                    requested_capital=capital,
                    unencumbered_cash="1000000", payout_reserve="100",
                    legal_approved=True, broker_approved=True,
                    kyc_approved=True, contracts_signed=True,
                )
                self.assertFalse(decision.authorized)
                self.assertIn("unsupported_capital_tier", decision.reasons)

    def test_order_rejects_arbitrary_nonexistent_funded_tier(self):
        decision = authorize_order(
            account_capital="150", equity="150",
            day_open_equity="150", risk_at_stop="0.4",
            open_risk_before=0, broker_minimum_risk="0.2",
            verified_stop=True, authoritative_snapshot=True,
            mode="challenge",
        )
        self.assertFalse(decision.allowed)
        self.assertIn("unsupported_capital_tier", decision.reasons)

    def test_real_orders_hard_disabled_even_with_external_claims(self):
        result=authorize_order(account_capital=100,equity=100,day_open_equity=100,
             risk_at_stop="0.4",open_risk_before=0,broker_minimum_risk="0.2",
             verified_stop=True,authoritative_snapshot=True,mode="real",
             execution_authorized=True)
        self.assertFalse(result.allowed)
        self.assertIn("real_execution_disabled",result.reasons)

    def test_broker_lot_infeasible_and_aggregate_limit(self):
        kwargs=dict(account_capital=100,equity=100,day_open_equity=100,
            risk_at_stop="0.8",open_risk_before=0,broker_minimum_risk="1.1",
            verified_stop=True,authoritative_snapshot=True,mode="challenge")
        self.assertIn("broker_minimum_lot_not_feasible",authorize_order(**kwargs).reasons)
        kwargs.update(risk_at_stop="0.7",broker_minimum_risk="0.1",open_risk_before="1.0")
        self.assertIn("aggregate_risk_limit",authorize_order(**kwargs).reasons)

    def test_missing_stop_and_snapshot_block(self):
        decision=authorize_order(account_capital=100,equity=100,day_open_equity=100,
            risk_at_stop="0.4",open_risk_before=0,broker_minimum_risk="0.2",mode="challenge")
        self.assertIn("stop_loss_required",decision.reasons)
        self.assertIn("authoritative_broker_snapshot_required",decision.reasons)

    def test_invalid_phase_level_and_negative_cash(self):
        with self.assertRaises(ValueError):
            self.challenge(phase=3)
        with self.assertRaises(ValueError):
            assess_promotion(level_index=14,realized_monthly_profit=4,trading_days=12,
                max_profitable_day=1,risk=self.risk(),evidence_verified=True)
        with self.assertRaises(ValueError):
            authorize_funding(requested_capital=100,unencumbered_cash=-1,payout_reserve=0)


    def test_challenge_requires_literal_verified_evidence(self):
        for untrusted in ("yes", "true", 1, ["approved"], object()):
            with self.subTest(untrusted=repr(untrusted)):
                decision = self.challenge(evidence_verified=untrusted)
                self.assertFalse(decision.passed)
                self.assertIn("reconciled_evidence_required", decision.reasons)

    def test_phase_two_prior_success_must_be_literal_boolean(self):
        for untrusted in ("yes", 1, ["pass"]):
            with self.subTest(value=repr(untrusted)):
                result = self.challenge(
                    phase=2, realized_net_profit="6", max_profitable_day="1.8",
                    prior_phase_passed=untrusted,
                )
                self.assertIn("phase_one_pass_required", result.reasons)

    def test_promotion_funding_and_broker_evidence_fail_on_truthy_fakes(self):
        kwargs = dict(
            level_index=0, realized_monthly_profit="4",
            trading_days=12, max_profitable_day="1",
            risk=self.risk(equity=104, open_equity=104),
            evidence_verified=True, funding_for_next_level=True,
        )
        for field in ("evidence_verified", "funding_for_next_level"):
            for untrusted in ("yes", 1, ["approved"]):
                with self.subTest(field=field, value=repr(untrusted)):
                    result = assess_promotion(**{**kwargs, field: untrusted})
                    self.assertFalse(result.eligible)
                    self.assertIn(
                        "reconciled_evidence_required" if field == "evidence_verified"
                        else "next_level_funding_not_confirmed", result.reasons,
                    )

    def test_funding_requires_four_literal_true_attestations(self):
        kwargs = dict(
            requested_capital=100, unencumbered_cash=200, payout_reserve=20,
            legal_approved=True, broker_approved=True,
            kyc_approved=True, contracts_signed=True,
        )
        for field in ("legal_approved", "broker_approved",
                      "kyc_approved", "contracts_signed"):
            for value in ("approved", 1, {"pass": True}):
                with self.subTest(field=field, value=repr(value)):
                    self.assertFalse(
                        authorize_funding(**{**kwargs, field: value}).authorized,
                    )

    def test_challenge_orders_require_literal_stop_and_broker_snapshot(self):
        kwargs = dict(
            account_capital=100, equity=100, day_open_equity=100,
            risk_at_stop="0.4", open_risk_before=0, broker_minimum_risk="0.2",
            verified_stop=True, authoritative_snapshot=True, mode="challenge",
        )
        self.assertTrue(authorize_order(**kwargs).allowed)
        for field, reason in (
            ("verified_stop", "stop_loss_required"),
            ("authoritative_snapshot", "authoritative_broker_snapshot_required"),
        ):
            for value in ("yes", 1, {"status": "approved"}):
                with self.subTest(field=field, value=repr(value)):
                    decision = authorize_order(**{**kwargs, field: value})
                    self.assertFalse(decision.allowed)
                    self.assertIn(reason, decision.reasons)

    def test_new_cohort_requires_both_social_platforms_at_final_stage(self):
        # Contract v1.2 allows stage one to pass before the two original
        # posts have reached 28 days. Final stage-two qualification does not.
        final = dict(phase=2, realized_net_profit="6", max_profitable_day="1.8",
                     prior_phase_passed=True, verified_cumulative_trades=50)
        decision = self.challenge(social_posts_verified=False, **final)
        self.assertFalse(decision.passed)
        self.assertIn("social_single_post_each_platform_unverified", decision.reasons)
        self.assertTrue(self.challenge(social_posts_verified=True, **final).passed)

    def test_social_truthy_fakes_do_not_approve_final_stage(self):
        final = dict(phase=2, realized_net_profit="6", max_profitable_day="1.8",
                     prior_phase_passed=True, verified_cumulative_trades=50)
        for forged in (1, "yes", {"done": True}, ["ig", "fb"]):
            with self.subTest(forged=repr(forged)):
                result = self.challenge(social_posts_verified=forged, **final)
                self.assertFalse(result.passed)
                self.assertIn("social_single_post_each_platform_unverified", result.reasons)

    def test_phase_two_still_requires_social_review(self):
        result = self.challenge(
            phase=2, realized_net_profit="6", max_profitable_day="1.8",
            prior_phase_passed=True, social_posts_verified=False,
        )
        self.assertIn("social_single_post_each_platform_unverified", result.reasons)

    def test_legacy_v11_contract_is_not_retroactively_penalized(self):
        result = self.challenge(
            social_posts_verified=False,
            contract_version="2026-11-14/v1.1",
        )
        self.assertTrue(result.passed)

    def test_unknown_contract_version_fails_closed(self):
        with self.assertRaises(ValueError):
            self.challenge(contract_version="v1.0-user-supplied")

    def test_fifty_trades_required_across_both_stages_at_final_pass(self):
        self.assertEqual(POLICY.min_closed_trades_per_challenge, 50)
        self.assertTrue(POLICY.trader_bots_allowed)
        phase_one=self.challenge(phase=1, verified_cumulative_trades=0,
                                 social_posts_verified=False)
        self.assertTrue(phase_one.passed)  # no 28-day post block on stage one
        kwargs=dict(phase=2, realized_net_profit="6", max_profitable_day="1.8",
                    prior_phase_passed=True)
        self.assertFalse(self.challenge(verified_cumulative_trades=49, **kwargs).passed)
        self.assertIn("minimum_50_distinct_closed_trades_not_met",
                      self.challenge(verified_cumulative_trades=49, **kwargs).reasons)
        self.assertTrue(self.challenge(verified_cumulative_trades=50, **kwargs).passed)
        self.assertTrue(self.challenge(verified_cumulative_trades=51, **kwargs).passed)

    def test_noninteger_fifty_trade_claim_rejected(self):
        kwargs=dict(phase=2, realized_net_profit="6", max_profitable_day="1.8",
                    prior_phase_passed=True)
        for invalid in (True, 49.5, "50", -1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.challenge(verified_cumulative_trades=invalid, **kwargs)

    def test_legacy_contract_unchanged_by_new_fifty_trade_gate(self):
        x=self.challenge(phase=2, realized_net_profit="6", max_profitable_day="1.8",
            prior_phase_passed=True, verified_cumulative_trades=0,
            contract_version="2026-11-14/v1.1",social_posts_verified=False)
        self.assertTrue(x.passed)

    def test_bot_permission_does_not_enable_real_broker_orders(self):
        self.assertTrue(POLICY.trader_bots_allowed)
        self.assertFalse(POLICY.real_orders_enabled)
        self.assertFalse(POLICY.trx_checkout_enabled)


if __name__ == "__main__":
    unittest.main()
