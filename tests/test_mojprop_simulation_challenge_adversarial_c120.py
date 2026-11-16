"""C120 strict-input and adversarial simulation safety, never fake broker evidence."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.mojprop_simulation_challenge import (
    ChallengeInputError, ChallengePolicy, EquitySnapshot,
    MAX_SNAPSHOTS, evaluate_simulated_phase,
)

P = ChallengePolicy(
    starting_equity=Decimal("10000.00"),
    phase1_profit_target_bps=800,
    phase2_profit_target_bps=500,
    max_daily_loss_bps=500,
    max_overall_loss_bps=1000,
    minimum_trading_days=5,
)
S = EquitySnapshot(
    event_id="event-000001",
    phase=1,
    observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    balance=Decimal("10000.00"),
    equity=Decimal("10000.00"),
    trades_executed=1,
)


class StrictChallengeInputC120Tests(unittest.TestCase):
    def evaluate(self, pol=P, records=(S,), phase=1):
        return evaluate_simulated_phase(pol, records, phase=phase)

    def test_01_float_string_bool_and_nan_balance_never_count_as_money(self):
        for value in ("10000.00", 10000.0, True, None,
                      Decimal("NaN"), Decimal("Infinity"),
                      Decimal("-Infinity"), Decimal("1.001"),
                      Decimal("1000000000000.01")):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(records=[replace(S, balance=value)])

    def test_02_equity_requires_exact_bounded_decimal(self):
        for value in ("20000", 20000.0, False, Decimal("NaN"),
                      Decimal("1.000001"), Decimal("1000000000001.00")):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(records=[replace(S, equity=value)])

    def test_03_starting_capital_must_not_be_float_string_or_unbounded(self):
        for value in (True, 10000, 10000.0, "10000", Decimal("NaN"),
                      Decimal("-1"), Decimal("0"), Decimal("1000000000001.00")):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(replace(P, starting_equity=value))

    def test_04_risk_and_target_bps_must_not_be_bool_float_zero_or_above_100pct(self):
        for field in ("phase1_profit_target_bps", "phase2_profit_target_bps",
                      "max_daily_loss_bps", "max_overall_loss_bps"):
            for value in (True, 0, -1, 10001, 1.1, "500", None):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ChallengeInputError):
                        self.evaluate(replace(P, **{field: value}))

    def test_05_minimum_trading_days_cannot_be_fake_bool_or_unsupported(self):
        for value in (True, False, -1, 0, 366, 5.0, "5", None):
            with self.subTest(value=value):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(replace(P, minimum_trading_days=value))

    def test_06_drawdown_rule_must_be_explicit_and_reviewed(self):
        for value in ("", "unlimited", "funded", "average", False, None):
            with self.subTest(value=value):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(replace(P, overall_drawdown_mode=value))

    def test_07_naive_clock_and_non_datetime_are_rejected(self):
        for value in (datetime(2026, 10, 1), "2026-10-01T00:00:00Z", None, True):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(records=[replace(S, observed_at=value)])

    def test_08_trade_count_must_not_be_malicious_or_ambiguous(self):
        for value in (-1, 100001, "1", 1.1, True, False, None):
            with self.subTest(value=value):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(records=[replace(S, trades_executed=value)])

    def test_09_event_id_cannot_include_html_crlf_or_excessive_bytes(self):
        for value in ("", "short", "a\nb-event", "<script>evil</script>",
                      "سود", "a"*81, True, None):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(records=[replace(S, event_id=value)])

    def test_10_snapshot_phase_and_requested_phase_reject_bool(self):
        for value in (True, False, 0, 3, "1", None):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(phase=value)
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(records=[replace(S, phase=value)])

    def test_11_no_dicts_or_client_supplied_objects_accepted_as_authoritative(self):
        for items in ({"events": []}, "events", [S.__dict__], [None],
                      [object()], iter((S,))):
            with self.subTest(type=type(items).__name__):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(records=items)

    def test_12_large_collection_preflight_happens_before_per_item_validation(self):
        with self.assertRaisesRegex(ChallengeInputError, "invalid_snapshot_collection"):
            self.evaluate(records=[S] * (MAX_SNAPSHOTS + 1))

    def test_13_invalid_policy_object_rejected_even_with_empty_journal(self):
        for value in (None, {"starting_equity": "10000"}, object(), True):
            with self.subTest(type=type(value).__name__):
                with self.assertRaises(ChallengeInputError):
                    self.evaluate(value, records=[])

    def test_14_sampled_positive_outcome_still_denies_live_funding_and_payout(self):
        five = [replace(S, event_id=f"event-{i:06d}",
                        observed_at=S.observed_at+timedelta(days=i),
                        balance=Decimal("11000.00"),
                        equity=Decimal("11000.00")) for i in range(5)]
        result = self.evaluate(records=five)
        self.assertEqual(result["status"], "simulation_target_met_review_required")
        self.assertIs(result["official_challenge_passed"], False)
        self.assertIs(result["funded_account_provisioning_allowed"], False)
        self.assertIs(result["payout_allowed"], False)
        self.assertIs(result["payment_collected"], False)

    def test_15_immutable_original_input_objects_not_mutated_by_risk_evaluation(self):
        evidence = [S]
        before = (S, P)
        self.evaluate(records=evidence)
        self.assertEqual((evidence[0], P), before)
