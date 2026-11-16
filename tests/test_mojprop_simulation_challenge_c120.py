"""Actual C120 phase engine contract tests: no broker, TRX, invoices or hosting."""
import hashlib
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.mojprop_simulation_challenge import (
    MAX_SNAPSHOTS, ChallengeInputError, ChallengePolicy, EquitySnapshot,
    evaluate_simulated_phase,
)


def policy(**kw):
    defaults = dict(
        starting_equity=Decimal("10000.00"),
        phase1_profit_target_bps=800,
        phase2_profit_target_bps=500,
        max_daily_loss_bps=500,
        max_overall_loss_bps=1000,
        minimum_trading_days=5,
        overall_drawdown_mode="static_initial",
    )
    defaults.update(kw)
    return ChallengePolicy(**defaults)


START = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def snap(i, amount="10000.00", *, phase=1, balance=None, trades=1, at=None):
    return EquitySnapshot(
        event_id=f"snapshot-{i:05d}",
        phase=phase,
        observed_at=at if at is not None else START + timedelta(days=i),
        balance=Decimal(amount if balance is None else balance),
        equity=Decimal(amount),
        trades_executed=trades,
    )


class TwoStageMojPropSimulationContractTests(unittest.TestCase):
    def test_01_phase_one_target_met_requires_review_never_official_pass(self):
        rows = [snap(i, str(10000 + 200*(i+1))) for i in range(5)]
        out = evaluate_simulated_phase(policy(), rows, phase=1)
        self.assertEqual(out["status"], "simulation_target_met_review_required")
        self.assertEqual(out["observed_trading_days"], 5)
        self.assertTrue(out["profit_target_observed"])
        for key in ("official_challenge_passed", "funded_account_provisioning_allowed",
                    "payout_allowed", "payment_collected"):
            self.assertIs(out[key], False)
        self.assertTrue(out["requires_independent_broker_evidence"])
        self.assertEqual(out["data_provenance"], "self_reported_not_broker_verified")

    def test_02_phase_two_uses_its_own_target_not_phase_one(self):
        rows = [snap(i, str(10000 + 100*(i+1)), phase=2) for i in range(5)]
        out = evaluate_simulated_phase(policy(), rows, phase=2)
        self.assertEqual(out["target_equity"], "10500.00")
        self.assertEqual(out["status"], "simulation_target_met_review_required")
        self.assertFalse(out["official_challenge_passed"])

    def test_03_profit_without_five_actual_trade_days_is_not_enough(self):
        rows = [snap(i, "11000.00", trades=1 if i == 0 else 0) for i in range(5)]
        out = evaluate_simulated_phase(policy(), rows, phase=1)
        self.assertEqual(out["observed_trading_days"], 1)
        self.assertFalse(out["trading_days_met"])
        self.assertEqual(out["status"], "simulation_in_progress")

    def test_04_empty_journal_is_not_a_pass_and_has_zero_money(self):
        out = evaluate_simulated_phase(policy(), [], phase=1)
        self.assertEqual(out["status"], "simulation_in_progress")
        self.assertEqual(out["snapshot_count"], 0)
        self.assertEqual(out["observed_trading_days"], 0)
        self.assertFalse(out["payment_collected"])

    def test_05_observed_daily_equity_drawdown_breaches_even_if_balance_stays_high(self):
        rows = [snap(0, "10000.00"),
                snap(1, "9400.00", balance="10000.00")]
        out = evaluate_simulated_phase(policy(), rows, phase=1)
        self.assertEqual(out["status"], "observed_simulation_rule_breach")
        self.assertEqual(out["first_observed_breach"], "observed_daily_drawdown_breach")
        self.assertFalse(out["official_challenge_passed"])

    def test_06_overall_loss_breach_cannot_be_reversed_by_later_profit(self):
        rows = [snap(0, "8800.00"), snap(1, "10500.00"),
                snap(2, "10700.00"), snap(3, "10800.00"), snap(4, "10900.00")]
        out = evaluate_simulated_phase(policy(), rows, phase=1)
        self.assertEqual(out["first_observed_breach"], "observed_overall_drawdown_breach")
        self.assertEqual(out["status"], "observed_simulation_rule_breach")
        self.assertTrue(out["profit_target_observed"])

    def test_07_trailing_peak_and_static_initial_distinct(self):
        rows = [snap(0, "12000.00"), snap(1, "10500.00")]
        static = evaluate_simulated_phase(
            policy(max_daily_loss_bps=4000, minimum_trading_days=1), rows, phase=1
        )
        trailing = evaluate_simulated_phase(
            policy(max_daily_loss_bps=4000, minimum_trading_days=1,
                   overall_drawdown_mode="trailing_peak"), rows, phase=1
        )
        self.assertEqual(static["status"], "simulation_in_progress")
        self.assertEqual(trailing["first_observed_breach"],
                         "observed_overall_drawdown_breach")

    def test_08_exact_daily_floor_is_not_a_breach_but_one_cent_under_is(self):
        rows = [snap(0, "10000.00"), snap(1, "9500.00")]
        exact = evaluate_simulated_phase(policy(), rows, phase=1)
        self.assertIsNone(exact["first_observed_breach"])
        under = evaluate_simulated_phase(
            policy(), [snap(0, "10000.00"), snap(1, "9499.99")], phase=1
        )
        self.assertEqual(under["first_observed_breach"],
                         "observed_daily_drawdown_breach")

    def test_09_same_utc_calendar_day_does_not_fake_two_trading_days(self):
        rows = [snap(0, trades=1), snap(1, trades=1, at=START+timedelta(hours=1))]
        out = evaluate_simulated_phase(policy(minimum_trading_days=2), rows, phase=1)
        self.assertEqual(out["observed_trading_days"], 1)

    def test_10_utc_normalization_keeps_digest_identical_for_same_instant(self):
        from datetime import timezone as tz
        a = snap(0)
        b = replace(a, observed_at=a.observed_at.astimezone(tz(timedelta(hours=2))))
        self.assertEqual(
            evaluate_simulated_phase(policy(), [a], phase=1)["observations_sha256"],
            evaluate_simulated_phase(policy(), [b], phase=1)["observations_sha256"],
        )

    def test_11_event_payload_edit_changes_audit_digest(self):
        before = evaluate_simulated_phase(policy(), [snap(0, "10000.00")], phase=1)
        after = evaluate_simulated_phase(policy(), [snap(0, "10000.01")], phase=1)
        self.assertNotEqual(before["observations_sha256"], after["observations_sha256"])
        self.assertEqual(len(before["observations_sha256"]), 64)

    def test_12_out_of_order_snapshots_denied_not_sorted_implicitly(self):
        with self.assertRaisesRegex(ChallengeInputError, "nonmonotonic"):
            evaluate_simulated_phase(policy(), [snap(1), snap(0)], phase=1)

    def test_13_duplicate_event_identifier_denied(self):
        with self.assertRaisesRegex(ChallengeInputError, "duplicate_event_id"):
            evaluate_simulated_phase(policy(), [snap(0), replace(snap(1), event_id="snapshot-00000")], phase=1)

    def test_14_phase_two_cannot_replay_phase_one_records(self):
        with self.assertRaisesRegex(ChallengeInputError, "invalid_snapshot_phase"):
            evaluate_simulated_phase(policy(), [snap(0, phase=1)], phase=2)


    def test_16_daily_drawdown_percent_uses_each_day_open_not_original_capital(self):
        rows = [snap(0, "20000.00"), snap(1, "19000.00")]
        out = evaluate_simulated_phase(policy(), rows, phase=1)
        self.assertEqual(out["worst_observed_daily_loss_bps"], "500.00")
        self.assertIsNone(out["first_observed_breach"])

    def test_17_one_cent_below_higher_daily_reference_is_breach(self):
        rows = [snap(0, "20000.00"), snap(1, "18999.99")]
        out = evaluate_simulated_phase(policy(), rows, phase=1)
        self.assertEqual(out["first_observed_breach"],
                         "observed_daily_drawdown_breach")
        self.assertTrue(Decimal(out["worst_observed_daily_loss_bps"]) > 500)

    def test_18_missing_ticks_never_count_as_verified_continuous_risk(self):
        rows = [snap(0, "10000.00"), snap(1, "11100.00")]
        out = evaluate_simulated_phase(policy(minimum_trading_days=1), rows, phase=1)
        self.assertIs(out["between_snapshot_breaches_verified"], False)
        self.assertIs(out["requires_independent_broker_evidence"], True)
        self.assertIs(out["official_challenge_passed"], False)

    def test_19_rule_revision_changes_report_digest_without_changing_snapshot_proof(self):
        original = evaluate_simulated_phase(policy(), [snap(0)], phase=1)
        revised = evaluate_simulated_phase(
            policy(phase1_profit_target_bps=900), [snap(0)], phase=1
        )
        self.assertNotEqual(original["rules_sha256"], revised["rules_sha256"])
        self.assertEqual(original["observations_sha256"], revised["observations_sha256"])
        self.assertEqual(original["rules_provenance"],
                         "illustrative_not_verified_customer_contract")

    def test_20_one_rule_identity_shared_across_both_educational_stages(self):
        one = evaluate_simulated_phase(policy(), [snap(0)], phase=1)
        two = evaluate_simulated_phase(
            policy(), [snap(0, phase=2)], phase=2
        )
        self.assertEqual(one["rules_sha256"], two["rules_sha256"])
        self.assertNotEqual(one["observations_sha256"], two["observations_sha256"])

    def test_15_target_requires_multiple_actual_trade_days_not_record_count(self):
        rows = [snap(i, "11000.00", at=START+timedelta(minutes=i)) for i in range(5)]
        out = evaluate_simulated_phase(policy(), rows, phase=1)
        self.assertEqual(out["status"], "simulation_in_progress")
