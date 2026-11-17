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
    calculate_v141_receipt_sha256,
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
        last_phase_one_evidence_sha256=accepted.phase_one_frozen_evidence_sha256,
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


    def test_36_genesis_cannot_claim_stage_one_already_passed(self):
        x=good_previous(engine_state="SIMULATED_STAGE_ONE_MATH_PASSED_WAITING_TRANSITION")
        with self.assertRaises(JournalTransitionRejected):
            policy(state=x)

    def test_37_persisted_unknown_engine_state_fails_closed(self):
        x=good_previous(sequence=1,engine_state="UNVERIFIED_MAGIC_PASS",
                        last_assessment_utc=at(1),previous_receipt_sha256=PREVIOUS)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=x,sequence=2)

    def test_38_stage_one_pass_state_requires_historical_acceptance(self):
        s=replace(previous_phase_one_passed(),last_phase_one_accepted_utc=None)
        x=replay_simulated_challenge(snapshot=good_snapshot())
        with self.assertRaises(JournalTransitionRejected):
            policy(state=s,calculated=x,sequence=2)

    def test_39_stage_two_in_progress_requires_historical_start(self):
        s=replace(previous_phase_one_passed(),engine_state="SIMULATED_STAGE_TWO_IN_REVIEW",
                  last_phase_two_started_utc=None)
        x=replay_simulated_challenge(snapshot=good_snapshot())
        with self.assertRaises(JournalTransitionRejected):
            policy(state=s,calculated=x,sequence=2)


    def test_40_stage_one_evidence_frozen_at_acceptance(self):
        calc=replay_simulated_challenge(snapshot=phase1_only())
        x=policy(calculated=calc)
        self.assertEqual(x.phase_one_evidence_sha256,calc.phase_one_frozen_evidence_sha256)
        self.assertRegex(x.phase_one_evidence_sha256,r"^[0-9a-f]{64}$")

    def test_41_stage_one_digest_unchanged_by_stage_two_progress(self):
        early=replay_simulated_challenge(snapshot=phase1_only())
        full=replay_simulated_challenge(snapshot=good_snapshot())
        self.assertEqual(early.phase_one_frozen_evidence_sha256,
                         full.phase_one_frozen_evidence_sha256)

    def test_42_stage_one_silent_profit_reallocation_detected_even_if_total_same(self):
        early=previous_phase_one_passed()
        snap=good_snapshot()
        original=snap.closed_fills
        altered=(replace(original[0],gross_realized_usd="0.41"),
                 replace(original[1],gross_realized_usd="0.39"))+original[2:]
        result=replay_simulated_challenge(snapshot=replace(snap,closed_fills=altered))
        self.assertTrue(result.phase_one.mathematical_pass)
        self.assertNotEqual(result.phase_one_frozen_evidence_sha256,
                            early.last_phase_one_evidence_sha256)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=early,calculated=result,sequence=2)

    def test_43_changed_historical_intraday_equity_detected(self):
        snap=good_snapshot()
        old=snap.equity_marks
        modified=old[:3]+(replace(old[3],equity_usd="103.201"),)+old[4:]
        result=replay_simulated_challenge(snapshot=replace(snap,equity_marks=modified))
        self.assertTrue(result.phase_one.mathematical_pass)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_phase_one_passed(),calculated=result,sequence=2)

    def test_44_stage_two_trades_do_not_rehash_accepted_stage_one(self):
        snap=good_snapshot()
        alt=snap.closed_fills[:-1]+(replace(snap.closed_fills[-1],
                                              gross_realized_usd="0.24"),)
        aligned_marks=snap.equity_marks[:-1]+(
            replace(snap.equity_marks[-1],equity_usd="106.24"),)
        result=replay_simulated_challenge(snapshot=replace(
            snap,closed_fills=alt,equity_marks=aligned_marks))
        prior=previous_phase_one_passed()
        self.assertEqual(result.phase_one_frozen_evidence_sha256,
                         prior.last_phase_one_evidence_sha256)
        x=policy(state=prior,calculated=result,sequence=2)
        self.assertEqual(x.phase_one_evidence_sha256,prior.last_phase_one_evidence_sha256)

    def test_45_accepted_phase_one_with_failed_profit_target_rejected(self):
        snap=phase1_only()
        changed=tuple(replace(f,gross_realized_usd="0.30") for f in snap.closed_fills)
        calc=replay_simulated_challenge(snapshot=replace(snap,closed_fills=changed))
        self.assertFalse(calc.phase_one.mathematical_pass)
        with self.assertRaises(JournalTransitionRejected):
            policy(calculated=calc)

    def test_46_stage_one_unreconciled_fill_blocks_acceptance_even_with_profit(self):
        snap=phase1_only()
        rows=(replace(snap.closed_fills[0],reconciliation_status="pending"),
              )+snap.closed_fills[1:]
        calc=replay_simulated_challenge(snapshot=replace(snap,closed_fills=rows))
        self.assertTrue(calc.phase_one.mathematical_pass)
        self.assertIn("unreconciled_close_event",calc.blockers)
        with self.assertRaises(JournalTransitionRejected):
            policy(calculated=calc)

    def test_47_prior_accepted_stage_requires_persisted_frozen_digest(self):
        invalid=replace(previous_phase_one_passed(),last_phase_one_evidence_sha256="")
        with self.assertRaises(JournalTransitionRejected):
            policy(state=invalid,calculated=replay_simulated_challenge(snapshot=good_snapshot()),sequence=2)

    def test_48_genesis_cannot_carry_forged_prior_stage_one_digest(self):
        invalid=good_previous(last_phase_one_evidence_sha256="a"*64)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=invalid)

    def test_49_injected_frozen_digest_must_match_persisted_history(self):
        calc=replay_simulated_challenge(snapshot=good_snapshot())
        corrupted=replace(calc,phase_one_frozen_evidence_sha256="c"*64)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_phase_one_passed(),calculated=corrupted,sequence=2)

    def test_50_unaccepted_stage_one_must_not_have_frozen_digest(self):
        calc=replay_simulated_challenge(snapshot=open_phase1())
        self.assertIsNone(calc.phase_one_frozen_evidence_sha256)
        with self.assertRaises(JournalTransitionRejected):
            policy(calculated=replace(calc,phase_one_frozen_evidence_sha256="b"*64))


    def test_51_prior_unaccepted_stage_cannot_carry_frozen_hash(self):
        old=good_previous(
            sequence=1,engine_state="SIMULATED_STAGE_ONE_IN_REVIEW",
            last_assessment_utc=at(1),previous_receipt_sha256=PREVIOUS,
            last_phase_one_evidence_sha256="c"*64,
        )
        with self.assertRaises(JournalTransitionRejected):
            policy(state=old,sequence=2)

    def test_52_prior_stage_in_review_cannot_claim_acceptance(self):
        old=replace(previous_phase_one_passed(),engine_state="SIMULATED_STAGE_ONE_IN_REVIEW")
        with self.assertRaises(JournalTransitionRejected):
            policy(state=old,calculated=replay_simulated_challenge(snapshot=good_snapshot()),sequence=2)


def previous_stage_two_math_done():
    calc=replay_simulated_challenge(snapshot=good_snapshot())
    return replace(
        previous_phase_one_passed(), sequence=2,
        engine_state="TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK",
        last_assessment_utc=NOW, last_phase_two_started_utc=PHASE2,
        last_phase_two_completed_utc=COMPLETED,
        last_phase_two_evidence_sha256=calc.phase_two_frozen_evidence_sha256,
        previous_receipt_sha256=PREVIOUS,
    )


class FinishedStageTwoEvidenceGuards(unittest.TestCase):
    def test_53_completed_stage_two_has_unique_frozen_digest(self):
        x=replay_simulated_challenge(snapshot=good_snapshot())
        self.assertRegex(x.phase_two_frozen_evidence_sha256,r"^[a-f0-9]{64}$")
        self.assertNotEqual(x.phase_two_frozen_evidence_sha256,x.phase_one_frozen_evidence_sha256)

    def test_54_uncompleted_phase_two_has_no_frozen_digest(self):
        snap=replace(good_snapshot(),phase_two_completed_at=None)
        self.assertIsNone(replay_simulated_challenge(snapshot=snap).phase_two_frozen_evidence_sha256)

    def test_55_stage_two_completion_produces_signed_receipt_digest(self):
        calc=replay_simulated_challenge(snapshot=good_snapshot())
        x=policy(state=previous_phase_one_passed(),calculated=calc,sequence=2)
        self.assertEqual(x.phase_two_evidence_sha256,calc.phase_two_frozen_evidence_sha256)

    def test_56_proven_previous_stage_two_history_can_be_reverified(self):
        snap=replace(good_snapshot(),as_of=NOW+timedelta(days=1))
        x=policy(state=previous_stage_two_math_done(),
                 calculated=replay_simulated_challenge(snapshot=snap),sequence=3)
        self.assertEqual(x.resulting_engine_state,"TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK")

    def test_57_stage_two_postcompletion_profit_reallocation_is_blocked(self):
        snap=good_snapshot()
        fs=list(snap.closed_fills)
        fs[25]=replace(fs[25],gross_realized_usd="0.26")
        fs[26]=replace(fs[26],gross_realized_usd="0.24")
        result=replay_simulated_challenge(snapshot=replace(
            snap,as_of=NOW+timedelta(days=1),closed_fills=tuple(fs)))
        self.assertTrue(result.phase_math_complete)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_stage_two_math_done(),calculated=result,sequence=3)

    def test_58_stage_two_postcompletion_equity_history_rewrite_is_blocked(self):
        snap=good_snapshot()
        marks=list(snap.equity_marks)
        marks[15]=replace(marks[15],equity_usd="100.99")
        calc=replay_simulated_challenge(snapshot=replace(
            snap,as_of=NOW+timedelta(days=1),equity_marks=tuple(marks)))
        self.assertTrue(calc.phase_two.mathematical_pass)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_stage_two_math_done(),calculated=calc,sequence=3)

    def test_59_stage_two_completion_with_fewer_than_fifty_total_closes_is_rejected(self):
        snap=good_snapshot()
        fs=snap.closed_fills[:-1]
        calc=replay_simulated_challenge(snapshot=replace(snap,closed_fills=fs))
        self.assertFalse(calc.phase_math_complete)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_phase_one_passed(),calculated=calc,sequence=2)

    def test_60_stage_two_unreconciled_close_blocks_final_approval(self):
        snap=good_snapshot()
        fs=snap.closed_fills[:25]+(replace(
            snap.closed_fills[25],reconciliation_status="pending"),)+snap.closed_fills[26:]
        calc=replay_simulated_challenge(snapshot=replace(snap,closed_fills=fs))
        self.assertIn("unreconciled_close_event",calc.blockers)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_phase_one_passed(),calculated=calc,sequence=2)

    def test_61_false_stage_two_frozen_hash_in_calculation_is_rejected(self):
        calc=replay_simulated_challenge(snapshot=replace(
            good_snapshot(),as_of=NOW+timedelta(days=1)))
        calc=replace(calc,phase_two_frozen_evidence_sha256="b"*64)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_stage_two_math_done(),calculated=calc,sequence=3)

    def test_62_persisted_complete_stage_two_without_fingerprint_is_invalid(self):
        old=replace(previous_stage_two_math_done(),last_phase_two_evidence_sha256="")
        calc=replay_simulated_challenge(snapshot=replace(
            good_snapshot(),as_of=NOW+timedelta(days=1)))
        with self.assertRaises(JournalTransitionRejected):
            policy(state=old,calculated=calc,sequence=3)

    def test_63_genesis_cannot_forge_stage_two_evidence(self):
        with self.assertRaises(JournalTransitionRejected):
            policy(state=good_previous(last_phase_two_evidence_sha256="c"*64))

    def test_64_uncompleted_stage_two_cannot_forge_final_digest(self):
        snap=replace(good_snapshot(),phase_two_completed_at=None)
        calc=replay_simulated_challenge(snapshot=snap)
        with self.assertRaises(JournalTransitionRejected):
            policy(state=previous_phase_one_passed(),
                   calculated=replace(calc,phase_two_frozen_evidence_sha256="c"*64),
                   sequence=2)



def receipt_data(**overrides):
    x=policy()
    fields=dict(
        challenge_ref=good_snapshot().challenge_ref,
        sequence=x.new_sequence,
        manifest_sha256=x.manifest_sha256,
        replay_sha256=x.replay_sha256,
        previous_receipt_sha256=x.previous_receipt_sha256,
        reported_engine_state=x.resulting_engine_state,
        as_of_utc=x.assessment_utc,
    )
    fields.update(overrides)
    return fields


class StoredReceiptDigestRecomputationTests(unittest.TestCase):
    def test_65_stored_record_digest_matches_new_policy_receipt(self):
        self.assertEqual(calculate_v141_receipt_sha256(**receipt_data()),
                         policy().receipt_sha256)

    def test_66_record_historical_time_tamper_changes_digest(self):
        x=receipt_data()
        x["as_of_utc"]=x["as_of_utc"]+timedelta(seconds=1)
        self.assertNotEqual(calculate_v141_receipt_sha256(**x),policy().receipt_sha256)

    def test_67_record_historical_state_tamper_changes_digest(self):
        x=receipt_data(reported_engine_state="SIMULATED_STAGE_TWO_IN_REVIEW")
        self.assertNotEqual(calculate_v141_receipt_sha256(**x),policy().receipt_sha256)

    def test_68_record_previous_hash_tamper_changes_digest(self):
        x=receipt_data(previous_receipt_sha256="a"*64)
        self.assertNotEqual(calculate_v141_receipt_sha256(**x),policy().receipt_sha256)

    def test_69_record_manifest_sha_tamper_changes_digest(self):
        x=receipt_data(manifest_sha256="c"*64)
        self.assertNotEqual(calculate_v141_receipt_sha256(**x),policy().receipt_sha256)

    def test_70_record_sequence_tamper_changes_digest(self):
        x=receipt_data(sequence=2)
        self.assertNotEqual(calculate_v141_receipt_sha256(**x),policy().receipt_sha256)

    def test_71_corrupt_historical_digest_format_rejected(self):
        with self.assertRaises(JournalTransitionRejected):
            calculate_v141_receipt_sha256(**receipt_data(replay_sha256="bad"))

    def test_72_incorrect_history_state_enum_rejected(self):
        with self.assertRaises(JournalTransitionRejected):
            calculate_v141_receipt_sha256(**receipt_data(reported_engine_state="PAID"))

    def test_73_naive_database_assessment_rejected(self):
        with self.assertRaises(JournalTransitionRejected):
            calculate_v141_receipt_sha256(**receipt_data(
                as_of_utc=NOW.replace(tzinfo=None)))

    def test_74_boolean_database_sequence_rejected(self):
        with self.assertRaises(JournalTransitionRejected):
            calculate_v141_receipt_sha256(**receipt_data(sequence=True))



if __name__=="__main__":
    unittest.main()
