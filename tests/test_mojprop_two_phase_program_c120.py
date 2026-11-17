"""C120 program stage sequencing: zero actual broker, token, payment or payout."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.mojprop_simulation_challenge import (
    ChallengeInputError, ChallengePolicy, EquitySnapshot,
    evaluate_two_phase_simulation,
)

POLICY = ChallengePolicy(
    starting_equity=Decimal("10000.00"),
    phase1_profit_target_bps=800, phase2_profit_target_bps=500,
    max_daily_loss_bps=500, max_overall_loss_bps=1000,
    minimum_trading_days=5,
)


def rows(phase, *, amount="11000.00", offset=None):
    if offset is None:
        offset = 31 if phase == 2 else 0  # stage two begins the next month
    return [
        EquitySnapshot(
            event_id=f"phase{phase}-event-{i:04d}",
            phase=phase,
            observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc)
                        + timedelta(days=i+offset),
            balance=Decimal(amount), equity=Decimal(amount),
            trades_executed=1,
        ) for i in range(5)
    ]


class TwoPhaseAccessIsNeverFundedC120(unittest.TestCase):
    def test_01_completed_self_reported_phases_still_not_funded(self):
        program = evaluate_two_phase_simulation(
            POLICY, rows(1), rows(2, amount="10500.00")
        )
        self.assertEqual(
            program["phase1"]["status"], "simulation_target_met_review_required"
        )
        self.assertEqual(
            program["phase2"]["status"], "simulation_target_met_review_required"
        )
        self.assertEqual(program["phase2_note"],
                         "simulation_target_met_but_no_authoritative_evidence")
        for flag in ("official_program_passed",
                     "funded_account_provisioning_allowed",
                     "payment_collected", "payout_allowed"):
            self.assertIs(program[flag], False)

    def test_02_no_phase_one_result_throws_if_buyer_claims_phase_two(self):
        with self.assertRaisesRegex(ChallengeInputError, "phase2_requires_phase1"):
            evaluate_two_phase_simulation(
                POLICY, [], rows(2, amount="10800.00")
            )

    def test_03_breached_phase_one_cannot_unlock_phase_two(self):
        first = [replace(rows(1)[0], balance=Decimal("8000.00"),
                         equity=Decimal("8000.00"))] + rows(1)[1:]
        with self.assertRaisesRegex(ChallengeInputError, "phase2_requires_phase1"):
            evaluate_two_phase_simulation(POLICY, first, rows(2))

    def test_04_unfinished_phase_one_does_not_start_phase_two(self):
        program = evaluate_two_phase_simulation(POLICY, rows(1, amount="10300.00"))
        self.assertIsNone(program["phase2"])
        self.assertEqual(program["phase2_note"], "not_started_phase1_rules_unmet")

    def test_05_phase_two_partial_progress_has_no_automatic_pass(self):
        program = evaluate_two_phase_simulation(POLICY, rows(1), rows(2)[:2])
        self.assertEqual(program["phase2"]["status"], "simulation_in_progress")
        self.assertFalse(program["official_program_passed"])

    def test_06_phase_two_cannot_reuse_phase_one_journal_records(self):
        with self.assertRaisesRegex(ChallengeInputError, "invalid_snapshot_phase"):
            evaluate_two_phase_simulation(POLICY, rows(1), rows(1))

    def test_07_phase_two_collection_is_bounded_explicit_container(self):
        for invalid in (None, {"snapshots": []}, "[]", True, iter(rows(2))):
            with self.subTest(type=type(invalid).__name__):
                with self.assertRaisesRegex(ChallengeInputError, "invalid_phase2_collection"):
                    evaluate_two_phase_simulation(POLICY, rows(1), invalid)


    def test_09_phase_two_cannot_be_backdated_before_phase_one_finishes(self):
        with self.assertRaisesRegex(ChallengeInputError, "phase2_observations_overlap"):
            evaluate_two_phase_simulation(
                POLICY, rows(1), rows(2, amount="10500.00", offset=-32)
            )

    def test_10_a_same_instant_cross_phase_snapshot_is_denied(self):
        phase1 = rows(1)
        final = phase1[-1].observed_at
        phase2 = rows(2, amount="10500.00")
        phase2[0] = replace(phase2[0], observed_at=final)
        # Keep the remaining phase2 observations after the first one.
        with self.assertRaisesRegex(ChallengeInputError, "phase2_observations_overlap"):
            evaluate_two_phase_simulation(POLICY, phase1, phase2)

    def test_08_phase_two_uses_own_target_and_fresh_initial_equity(self):
        program = evaluate_two_phase_simulation(
            POLICY, rows(1, amount="11000.00"), rows(2, amount="10499.99")
        )
        self.assertEqual(program["phase1"]["target_equity"], "10800.00")
        self.assertEqual(program["phase2"]["target_equity"], "10500.00")
        self.assertEqual(program["phase2"]["status"], "simulation_in_progress")
        self.assertTrue(program["phase2_uses_fresh_initial_equity"])
        self.assertTrue(program["verified_contract_and_provider_required"])
