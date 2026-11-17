"""Behavioral monotone/phase-transition journal tests; no Django backend.

These exercise the PURE policy used inside the Django transaction-locked
receipt writer. Passing does not certify DB schema, broker identity or sale.
"""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from prop_firm.plan1_v141_replay_journal_policy import (
    PreviousReplayState, JournalTransitionRejected,
    decide_next_signed_replay_receipt,
)
from prop_firm.plan1_v141_simulated_challenge_engine import replay_simulated_challenge
from prop_firm.plan1_v14_social_or_50_terms import review_prospective_terms
from tests.test_plan1_v141_simulated_challenge_engine import (
    START, APPROVED, PHASE2, COMPLETED, NOW, at, good_snapshot, good_social,
)

SHA="a"*64
PREVIOUS="b"*64


def phase1_only():
    s=good_snapshot()
    return replace(
        s, phase_two_started_at=None, phase_two_completed_at=None,
        as_of=at(10,0), closed_fills=s.closed_fills[:25],
        equity_marks=s.equity_marks[:14],
    )


def open_phase1():
    s=phase1_only()
    return replace(s, phase_one_accepted_at=None,
                   as_of=at(2,0),
                   closed_fills=s.closed_fills[:4],
                   equity_marks=s.equity_marks[:4])


def good_previous(**overrides):
    t=review_prospective_terms()
    fields=dict(
        challenge_ref=good_snapshot().challenge_ref,
        contract_sha256=t.contract_candidate_sha256,
        sequence=0, engine_state="PENDING_SIGNED_SIMULATOR_FEED",
        last_assessment_utc=None,
        last_phase_one_accepted_utc=None,
        last_phase_two_started_utc=None,
        last_phase_two_completed_utc=None,
        previous_receipt_sha256="",
    )
    fields.update(overrides)
    return PreviousReplayState(**fields)


def policy(*, state=None, calculated=None, digest=SHA, sequence=1):
    return decide_next_signed_replay_receipt(
        previous=good_previous() if state is None else state,
        calculated=replay_simulated_challenge(snapshot=open_phase1()) if calculated is None else calculated,
        manifest_sha256=digest, requested_sequence=sequence,
    )


def previous_phase_one_passed():
    accepted=replay_simulated_challenge(snapshot=phase1_only())
    return good_previous(
        sequence=1,engine_state="SIMULATED_STAGE_ONE_MATH_PASSED_WAITING_TRANSITION",
        last_assessment_utc=at(10,0),
        last_phase_one_accepted_utc=APPROVED,
        previous_receipt_sha256=PREVIOUS,
    )


class SignedReplayJournalPolicyTests(unittest.TestCase):
    def test_01_first_signed_checkpoint_can_be_journaled(self):
        x=policy()
        self.assertEqual(x.new_sequence,1)
        self.assertEqual(x.resulting_engine_state,"SIMULATED_STAGE_ONE_IN_REVIEW")

    def test_02_first_genesis_receipt_has_zero_previous(self):
        self.assertEqual(policy().previous_receipt_sha256,"0"*64)

    def test_03_exact_receipt_digest_is_sha256(self):
        self.assertRegex(policy().receipt_sha256,r"^[0-9a-f]{64}$")

    def test_04_equal_replay_inputs_have_same_receipt_hash(self):
        self.assertEqual(policy().receipt_sha256,policy().receipt_sha256)

    def test_05_sequence_influences_hash(self):
        x=policy()
        state=good_previous(sequence=1,engine_state="SIMULATED_STAGE_ONE_IN_REVIEW",
                            last_assessment_utc=at(1),previous_receipt_sha256=PREVIOUS)
        y=policy(state=state,sequence=2)
        self.assertNotEqual(x.receipt_sha256,y.receipt_sha256)

    def test_06_changing_manifest_bytes_digest_changes_receipt(self):
        self.assertNotEqual(policy(digest="a"*64).receipt_sha256,
                            policy(digest="c"*64).receipt_sha256)

    def test_07_paid_enrollment_never_authorized(self):
        self.assertFalse(policy().paid_enrollment_authorized)

    def test_08_broker_and_payout_never_authorized(self):
        self.assertFalse(policy().broker_order_authorized)
        self.assertFalse(policy().payout_authorized)

    def test_09_receipt_remains_mathematical_only(self):
        self.assertTrue(policy().mathematical_only)

    def test_10_second_sequence_requires_last_assessment_and_hash(self):
        s=good_previous(sequence=1,engine_state="SIMULATED_STAGE_ONE_IN_REVIEW")
        with self.assertRaises(JournalTransitionRejected):policy(state=s,sequence=2)

    def test_11_missing_or_false_previous_receipt_rejected(self):
        s=good_previous(sequence=1,engine_state="SIMULATED_STAGE_ONE_IN_REVIEW",
                        last_assessment_utc=at(1),previous_receipt_sha256="bad")
        with self.assertRaises(JournalTransitionRejected):policy(state=s,sequence=2)

    def test_12_sequence_gap_rejected(self):
        with self.assertRaises(JournalTransitionRejected):policy(sequence=3)

    def test_13_duplicate_sequence_rejected(self):
        s=good_previous(sequence=1,engine_state="SIMULATED_STAGE_ONE_IN_REVIEW",
                        last_assessment_utc=at(1),previous_receipt_sha256=PREVIOUS)
        with self.assertRaises(JournalTransitionRejected):policy(state=s,sequence=1)

    def test_14_bool_sequence_rejected(self):
        with self.assertRaises(JournalTransitionRejected):policy(sequence=True)

    def test_15_old_contract_digest_rejected(self):
        s=good_previous(contract_sha256="0"*64)
        with self.assertRaises(JournalTransitionRejected):policy(state=s)

    def test_16_other_challenge_ref_rejected(self):
        s=good_previous(challenge_ref="CHALLENGE-ZYXWVUTSRQPONMLK")
        with self.assertRaises(JournalTransitionRejected):policy(state=s)

    def test_17_wrong_draft_version_rejected(self):
        calc=replay_simulated_challenge(snapshot=open_phase1())
        with self.assertRaises(JournalTransitionRejected):
            policy(calculated=replace(calc,contract_version="2026-11-15/v1.2"))

    def test_18_bad_manifest_hash_rejected(self):
        with self.assertRaises(JournalTransitionRejected):policy(digest="invalid")

    def test_19_terminal_breach_rejects_future_sequence(self):
        s=good_previous(sequence=1,engine_state="SIMULATED_RISK_BREACHED",
                        last_assessment_utc=at(1),previous_receipt_sha256=PREVIOUS)
        with self.assertRaises(JournalTransitionRejected):policy(state=s,sequence=2)

    def test_20_terminal_expiry_rejects_future_sequence(self):
        s=good_previous(sequence=1,engine_state="SIMULATED_EVALUATION_EXPIRED",
                        last_assessment_utc=at(1),previous_receipt_sha256=PREVIOUS)
        with self.assertRaises(JournalTransitionRejected):policy(state=s,sequence=2)

    def test_21_terminal_full_math_rejects_future_sequence(self):
        s=good_previous(sequence=1,engine_state="BOTH_MATH_REVIEWS_PASSED_EXTERNAL_PROOF_REQUIRED",
                        last_assessment_utc=at(1),previous_receipt_sha256=PREVIOUS)
        with self.assertRaises(JournalTransitionRejected):policy(state=s,sequence=2)

    def test_22_older_assessment_than_last_rejected(self):
        s=good_previous(sequence=1,engine_state="SIMULATED_STAGE_ONE_IN_REVIEW",
                        last_assessment_utc=at(3),previous_receipt_sha256=PREVIOUS)
        with self.assertRaises(JournalTransitionRejected):policy(state=s,sequence=2)

    def test_23_equal_assessment_rejected(self):
        s=good_previous(sequence=1,engine_state="SIMULATED_STAGE_ONE_IN_REVIEW",
                        last_assessment_utc=at(2),previous_receipt_sha256=PREVIOUS)
        with self.assertRaises(JournalTransitionRejected):policy(state=s,sequence=2)

    def test_24_stage_one_acceptance_transition_is_recorded(self):
        calc=replay_simulated_challenge(snapshot=phase1_only())
        x=policy(calculated=calc)
        self.assertEqual(x.phase_one_accepted_utc,APPROVED)

    def test_25_stage_two_without_previous_successful_checkpoint_rejected(self):
        calc=replay_simulated_challenge(snapshot=good_snapshot())
        with self.assertRaises(JournalTransitionRejected):policy(calculated=calc)

    def test_26_stage_two_allowed_only_after_separate_success_checkpoint(self):
        calc=replay_simulated_challenge(snapshot=good_snapshot())
        x=policy(state=previous_phase_one_passed(),calculated=calc,sequence=2)
        self.assertEqual(x.phase_two_started_utc,PHASE2)
        self.assertEqual(x.phase_two_completed_utc,COMPLETED)

    def test_27_stage_one_accepted_timestamp_cannot_change(self):
        calc=replay_simulated_challenge(snapshot=good_snapshot())
        s=replace(previous_phase_one_passed(),
                  last_phase_one_accepted_utc=APPROVED-timedelta(seconds=1))
        with self.assertRaises(JournalTransitionRejected):
            policy(state=s,calculated=calc,sequence=2)

    def test_28_stage_one_accepted_timestamp_cannot_be_deleted(self):
        calc=replay_simulated_challenge(snapshot=open_phase1())
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_phase_one_passed(),calculated=calc,sequence=2)

    def test_29_stage_two_started_timestamp_cannot_change(self):
        calc=replay_simulated_challenge(snapshot=good_snapshot())
        s=replace(previous_phase_one_passed(),engine_state="SIMULATED_STAGE_TWO_IN_REVIEW",
                  last_phase_two_started_utc=PHASE2-timedelta(minutes=1))
        with self.assertRaises(JournalTransitionRejected):
            policy(state=s,calculated=calc,sequence=2)

    def test_30_final_stage_timestamp_cannot_change(self):
        calc=replay_simulated_challenge(snapshot=good_snapshot())
        s=replace(previous_phase_one_passed(),engine_state="SIMULATED_STAGE_TWO_IN_REVIEW",
                  last_phase_two_started_utc=PHASE2,
                  last_phase_two_completed_utc=COMPLETED-timedelta(minutes=1))
        with self.assertRaises(JournalTransitionRejected):
            policy(state=s,calculated=calc,sequence=2)

    def test_31_finished_phase_two_without_stage_two_start_rejected(self):
        calc=replay_simulated_challenge(snapshot=good_snapshot())
        altered=replace(calc,phase_two_started_at_utc=None)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_phase_one_passed(),calculated=altered,sequence=2)

    def test_32_payment_flag_injected_into_calculation_rejected(self):
        calc=replay_simulated_challenge(snapshot=open_phase1())
        with self.assertRaises(JournalTransitionRejected):
            policy(calculated=replace(calc,paid_enrollment_authorized=True))

    def test_33_real_order_flag_injected_into_calculation_rejected(self):
        calc=replay_simulated_challenge(snapshot=open_phase1())
        with self.assertRaises(JournalTransitionRejected):
            policy(calculated=replace(calc,real_broker_orders_authorized=True))

    def test_34_unknown_foreign_result_type_rejected(self):
        with self.assertRaises(JournalTransitionRejected):
            policy(calculated={"passed":True})

    def test_35_genesis_with_previous_receipt_is_inconsistent(self):
        s=good_previous(previous_receipt_sha256="c"*64)
        with self.assertRaises(JournalTransitionRejected):policy(state=s)


if __name__=="__main__":
    unittest.main()
