"""C120 actual offline JSON adapter tests; no customer data or HTTP."""
import json
import unittest
from copy import deepcopy

from services.mojprop_simulation_challenge import ChallengeInputError
from scripts.mojprop_simulation_challenge_cli import (
    MAX_STDIN_BYTES, assess_json_bytes,
)


def valid():
    return {
        "schema": "mojprop.simulated.input.v1",
        "policy": {
            "starting_equity": "10000.00",
            "phase1_profit_target_bps": 800,
            "phase2_profit_target_bps": 500,
            "max_daily_loss_bps": 500,
            "max_overall_loss_bps": 1000,
            "minimum_trading_days": 5,
            "overall_drawdown_mode": "static_initial",
        },
        "phase1": [
            {"event_id": f"phase1-event-{i:04d}", "phase": 1,
             "observed_at": f"2026-10-{i+1:02d}T12:00:00Z",
             "balance": f"{10200 + i*200}.00",
             "equity": f"{10200 + i*200}.00", "trades_executed": 1}
            for i in range(5)
        ],
        "phase2": [
            {"event_id": f"phase2-event-{i:04d}", "phase": 2,
             "observed_at": f"2026-11-{i+1:02d}T12:00:00Z",
             "balance": f"{10100 + i*100}.00",
             "equity": f"{10100 + i*100}.00", "trades_executed": 1}
            for i in range(5)
        ],
    }


def run(obj):
    return assess_json_bytes(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


class MojPropChallengeCliC120Tests(unittest.TestCase):
    def test_01_valid_two_phase_file_produces_a_real_deterministic_educational_report(self):
        one = run(valid())
        two = run(valid())
        self.assertEqual(one, two)
        self.assertEqual(one["phase1"]["status"],
                         "simulation_target_met_review_required")
        self.assertEqual(one["phase2"]["status"],
                         "simulation_target_met_review_required")
        self.assertFalse(one["funded_account_provisioning_allowed"])
        self.assertFalse(one["payment_collected"])
        self.assertFalse(one["payout_allowed"])

    def test_02_duplicate_json_policy_field_fails_closed(self):
        payload = json.dumps(valid()).replace(
            '"minimum_trading_days": 5',
            '"minimum_trading_days": 5, "minimum_trading_days": 1',
            1,
        )
        # json.dumps default separator has spaces; ensure a duplicate was made.
        self.assertEqual(payload.count('"minimum_trading_days"'), 2)
        with self.assertRaises(ChallengeInputError):
            assess_json_bytes(payload.encode())

    def test_03_extra_buyer_email_is_never_part_of_private_input_schema(self):
        doc = valid()
        doc["buyer_email"] = "buyer@example.org"
        with self.assertRaisesRegex(ChallengeInputError, "invalid_root_contract"):
            run(doc)

    def test_04_unknown_paid_or_broker_field_is_not_silently_accepted(self):
        doc = valid()
        doc["phase1"][0]["is_broker_verified"] = True
        with self.assertRaisesRegex(ChallengeInputError, "invalid_event_contract"):
            run(doc)

    def test_05_float_string_coercion_for_amounts_denied(self):
        doc = valid()
        doc["phase1"][0]["balance"] = 12000.01
        with self.assertRaises(ChallengeInputError):
            run(doc)

    def test_06_string_based_bps_and_boolean_day_counts_denied(self):
        for key, value in (("phase1_profit_target_bps", "800"),
                           ("minimum_trading_days", True)):
            doc = valid()
            doc["policy"][key] = value
            with self.subTest(key=key), self.assertRaises(ChallengeInputError):
                run(doc)

    def test_07_invalid_timestamp_or_naive_clock_denied(self):
        for ts in ("2026-10-01T12:00:00", "yesterday", "2026-02-30T12:00:00Z"):
            doc = valid()
            doc["phase1"][0]["observed_at"] = ts
            with self.subTest(ts=ts), self.assertRaises(ChallengeInputError):
                run(doc)

    def test_08_nonfinite_json_number_denied(self):
        data = json.dumps(valid()).replace(
            '"phase1_profit_target_bps": 800',
            '"phase1_profit_target_bps": NaN',
            1,
        )
        with self.assertRaises(ChallengeInputError):
            assess_json_bytes(data.encode())

    def test_09_size_ceiling_prevents_large_input_before_json_parse(self):
        with self.assertRaisesRegex(ChallengeInputError, "invalid_input_size"):
            assess_json_bytes(b"[" + b"x" * MAX_STDIN_BYTES + b"]")

    def test_10_empty_or_wrongly_typed_input_never_becomes_pass(self):
        for data in (b"", b"null", b"[]", b"{}", "not-bytes", None, b"not JSON"):
            with self.subTest(value=repr(data)[:20]), self.assertRaises(ChallengeInputError):
                assess_json_bytes(data)

    def test_11_no_hidden_auto_broker_entitlement_via_submitted_claimed_status(self):
        doc = valid()
        doc["phase2"][0]["status"] = "PASSED"
        with self.assertRaises(ChallengeInputError):
            run(doc)

    def test_12_unknown_drawdown_rule_rejected_before_evaluation(self):
        doc = valid()
        doc["policy"]["overall_drawdown_mode"] = "ignore-drawdown"
        with self.assertRaises(ChallengeInputError):
            run(doc)

    def test_13_second_phase_without_first_simulated_completion_denied(self):
        doc = valid()
        doc["phase1"] = []
        with self.assertRaisesRegex(ChallengeInputError, "phase2_requires_phase1"):
            run(doc)

    def test_15_zero_or_negative_ledger_mark_is_a_loss_not_hidden_parser_failure(self):
        for amount in ("0.00", "-10.00"):
            doc = valid()
            doc["phase1"][0]["equity"] = amount
            # A phase-1 breach must not unlock, or even evaluate, phase 2.
            # Check the observed loss classification with no phase-2 attempt.
            doc["phase2"] = []
            with self.subTest(amount=amount):
                result = run(doc)
                self.assertEqual(result["phase1"]["status"],
                                 "observed_simulation_rule_breach")
                self.assertEqual(result["phase1"]["latest_observed_equity"],
                                 "11000.00")
                self.assertFalse(result["funded_account_provisioning_allowed"])
                self.assertIsNone(result["phase2"])

    def test_17_phase2_is_denied_after_nonpositive_phase1_equity_breach(self):
        for amount in ("0.00", "-10.00"):
            doc = valid()
            doc["phase1"][0]["equity"] = amount
            with self.subTest(amount=amount):
                with self.assertRaisesRegex(
                    ChallengeInputError, "phase2_requires_phase1_simulation_target"
                ):
                    run(doc)

    def test_16_negative_initial_capital_is_not_an_allowed_challenge(self):
        doc = valid()
        doc["policy"]["starting_equity"] = "-10000.00"
        with self.assertRaises(ChallengeInputError):
            run(doc)

    def test_14_filled_training_template_cannot_be_mislabelled_as_two_phase_json(self):
        doc = valid()
        doc["schema"] = "mojprop.starter30.journal.v1"
        with self.assertRaisesRegex(ChallengeInputError, "unreviewed_schema"):
            run(doc)
