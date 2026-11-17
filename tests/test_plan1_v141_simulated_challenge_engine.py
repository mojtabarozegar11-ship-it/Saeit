"""Real Python 3.11 offline regression tests for MOJ-PROP-01 DEMO engine.

The generator below creates synthetic data *only in tests*.
No sample is a broker execution, paid customer or source attestation.
"""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from prop_firm.plan1_v141_simulated_challenge_engine import (
    EngineSnapshot, SimulatedClosedFill, SimulatedEquityMark,
    replay_simulated_challenge,
)
from prop_firm.plan1_v14_social_or_50_terms import review_prospective_terms
from prop_firm.plan1_v14_social_or_28d_review import Social28DayReview

START = datetime(2026,11,1,0,tzinfo=timezone.utc)
APPROVED = START + timedelta(days=9)
PHASE2 = START + timedelta(days=11)
COMPLETED = START + timedelta(days=21)
NOW = START + timedelta(days=22)
D = Decimal


def at(day, hour=0):
    return START + timedelta(days=day, hours=hour)


def fill(phase, i, *, pnl=None):
    day=(1 if phase==1 else 12)+i//4
    value="0.40" if phase==1 else "0.25"
    return SimulatedClosedFill(
        phase=phase,data_source="verified.demo.source",
        external_event_id=f"fill-{phase}-{i}",
        external_position_id=f"position-{phase}-{i}",
        symbol="XAUUSD",closed_at=at(day,12),
        gross_realized_usd=value if pnl is None else pnl,
        total_fees_usd="0",
        position_fully_closed=True,reconciliation_status="verified",
        evidence_sha256="a"*64)


def marks(phase):
    base=1 if phase==1 else 12
    increment=D("0.40") if phase==1 else D("0.25")
    output=[]
    units=0
    for index in range(7):
        day=base+index
        today=min(4,25-units)
        before=D("100")+increment*units
        after=before+increment*today
        for role,hour,equity,opening in (
            ("open",0,before,True),("last",23,after,False)):
            output.append(SimulatedEquityMark(
                phase=phase,data_source="verified.demo.source",
                external_event_id=f"equity-{phase}-{day}-{role}",
                observed_at=at(day,hour),equity_usd=str(equity),
                is_utc_day_open=opening,reconciliation_status="verified",
                evidence_sha256="b"*64))
        units+=today
    return output


def good_snapshot():
    t=review_prospective_terms()
    return EngineSnapshot(
        challenge_ref="CHALLENGE-ABCDEFGHIJKLMNOP",
        accepted_terms_sha256=t.contract_candidate_sha256,
        evaluation_started_at=START,
        phase_one_accepted_at=APPROVED,
        phase_two_started_at=PHASE2,
        phase_two_completed_at=COMPLETED,
        as_of=NOW,
        closed_fills=tuple(fill(1,i) for i in range(25))
                     +tuple(fill(2,i) for i in range(25)),
        equity_marks=tuple(marks(1)+marks(2)),
    )


def good_social():
    return Social28DayReview(
        candidate_platform="instagram",observed_hours=672,
        observations=29,reasons=(),timeline_mathematically_consistent=True,
    )


def replay(s=None,social=None):
    return replay_simulated_challenge(
        snapshot=good_snapshot() if s is None else s,social=social,
    )


class TwoStageEngineTests(unittest.TestCase):
    def test_01_real_math_replay_both_stages_pass(self):
        x=replay(social=good_social())
        self.assertTrue(x.phase_one.mathematical_pass)
        self.assertTrue(x.phase_two.mathematical_pass)
        self.assertTrue(x.phase_math_complete)
        self.assertTrue(x.combined_math_complete)

    def test_02_exact_trade_count_is_50_total(self):
        x=replay()
        self.assertEqual(x.combined_unique_closed_positions,50)
        self.assertEqual((x.phase_one.verified_closed_positions,x.phase_two.verified_closed_positions),(25,25))

    def test_03_seven_utc_days_in_each_stage(self):
        x=replay()
        self.assertEqual(x.phase_one.verified_utc_trading_days,7)
        self.assertEqual(x.phase_two.verified_utc_trading_days,7)

    def test_04_phase_profit_realized_from_actual_fills(self):
        x=replay()
        self.assertEqual(x.phase_one.realized_net_usd,D("10"))
        self.assertEqual(x.phase_two.realized_net_usd,D("6.25"))

    def test_05_goals_are_9_6_and_6(self):
        x=replay()
        self.assertEqual(x.phase_one.target_net_usd,D("9.6"))
        self.assertEqual(x.phase_two.target_net_usd,D("6"))

    def test_06_consistency_best_day_from_positions(self):
        x=replay()
        self.assertEqual(x.phase_one.best_realized_day_usd,D("1.60"))
        self.assertEqual(x.phase_two.best_realized_day_usd,D("1.00"))

    def test_07_social_separate_clock_not_mandatory_for_phase_math(self):
        x=replay()
        self.assertTrue(x.phase_math_complete)
        self.assertFalse(x.social_math_complete)
        self.assertEqual(x.state,"TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK")

    def test_08_social_either_facebook_works(self):
        s=replace(good_social(),candidate_platform="facebook")
        self.assertTrue(replay(social=s).combined_math_complete)

    def test_09_five_social_hours_short_fails(self):
        s=replace(good_social(),observed_hours=671)
        self.assertFalse(replay(social=s).combined_math_complete)

    def test_10_social_source_approval_not_fabricated(self):
        x=replay(social=good_social())
        self.assertFalse(x.social_post_independently_verified)
        self.assertFalse(x.merchant_and_customer_law_approved)

    def test_11_no_invoice_even_if_all_math_passes(self):
        x=replay(social=good_social())
        self.assertFalse(x.fee_collection_authorized)
        self.assertFalse(x.paid_enrollment_authorized)

    def test_12_no_broker_or_payout_even_if_math_passes(self):
        x=replay(social=good_social())
        self.assertFalse(x.real_broker_orders_authorized)
        self.assertFalse(x.payout_authorized)
        self.assertFalse(x.company_real_funding_verified)

    def test_13_all_math_success_is_explicit_review_not_real_pass(self):
        self.assertEqual(replay(social=good_social()).state,
                         "BOTH_MATH_REVIEWS_PASSED_EXTERNAL_PROOF_REQUIRED")

    def test_14_immutable_replay_digest_independent_of_event_order(self):
        s=good_snapshot()
        switched=replace(s,closed_fills=tuple(reversed(s.closed_fills)),
                         equity_marks=tuple(reversed(s.equity_marks)))
        self.assertEqual(replay(s).snapshot_sha256,replay(switched).snapshot_sha256)

    def test_15_duplicate_identical_fill_cannot_inflate_profit(self):
        s=good_snapshot()
        a=replay(s)
        x=replay(replace(s,closed_fills=s.closed_fills+(s.closed_fills[0],)))
        self.assertEqual(x.combined_unique_closed_positions,a.combined_unique_closed_positions)
        self.assertEqual(x.phase_one.realized_net_usd,a.phase_one.realized_net_usd)
        self.assertEqual(x.replayed_duplicate_event_count,1)

    def test_16_duplicate_identical_equity_mark_ignored(self):
        s=good_snapshot()
        x=replay(replace(s,equity_marks=s.equity_marks+(s.equity_marks[0],)))
        self.assertTrue(x.phase_math_complete)
        self.assertEqual(x.replayed_duplicate_event_count,1)

    def test_17_conflicting_duplicate_event_id_blocks(self):
        s=good_snapshot()
        broken=replace(s.closed_fills[0],gross_realized_usd="42")
        x=replay(replace(s,closed_fills=s.closed_fills+(broken,)))
        self.assertIn("conflicting_duplicate_event_id",x.blockers)
        self.assertFalse(x.phase_math_complete)

    def test_18_conflicting_duplicate_equity_mark_blocks(self):
        s=good_snapshot()
        broken=replace(s.equity_marks[0],equity_usd="94")
        x=replay(replace(s,equity_marks=s.equity_marks+(broken,)))
        self.assertIn("conflicting_duplicate_equity_id",x.blockers)

    def test_19_partial_fills_count_as_one_closed_position(self):
        s=good_snapshot()
        first=s.closed_fills[0]
        partial=replace(first,external_event_id="partial-1",
                        closed_at=at(1,11),gross_realized_usd="0.15",
                        position_fully_closed=False)
        final=replace(first,external_event_id="partial-2",
                      gross_realized_usd="0.25",position_fully_closed=True)
        rows=(partial,final)+s.closed_fills[1:]
        x=replay(replace(s,closed_fills=rows))
        self.assertEqual(x.combined_unique_closed_positions,50)
        self.assertTrue(x.phase_math_complete)

    def test_20_partial_position_without_final_cannot_count(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],position_fully_closed=False),)+s.closed_fills[1:]
        x=replay(replace(s,closed_fills=rows))
        self.assertEqual(x.combined_unique_closed_positions,49)
        self.assertIn("fewer_than_fifty_distinct_fully_closed_positions_total",x.blockers)

    def test_21_two_final_events_same_position_block(self):
        s=good_snapshot()
        first=s.closed_fills[0]
        extra=replace(first,external_event_id="second-close-final",closed_at=at(1,13))
        x=replay(replace(s,closed_fills=s.closed_fills+(extra,)))
        self.assertIn("phase_1_position_not_fully_closed_or_final_out_of_order",x.phase_one.blockers)

    def test_22_unverified_fill_blocks(self):
        s=good_snapshot()
        x=replay(replace(s,closed_fills=(replace(s.closed_fills[0],reconciliation_status="pending"),)+s.closed_fills[1:]))
        self.assertIn("unreconciled_close_event",x.blockers)

    def test_23_unverified_equity_mark_blocks(self):
        s=good_snapshot()
        x=replay(replace(s,equity_marks=(replace(s.equity_marks[0],reconciliation_status="pending"),)+s.equity_marks[1:]))
        self.assertIn("unreconciled_equity_observation",x.blockers)

    def test_24_4_percent_day_loss_equity_breach_sticky(self):
        s=good_snapshot()
        mark=replace(s.equity_marks[14],external_event_id="intraday-loss",
                     observed_at=at(12,10),equity_usd="95.9",
                     is_utc_day_open=False)
        x=replay(replace(s,equity_marks=s.equity_marks+(mark,)))
        self.assertIn("phase_2_daily_drawdown_breached",x.phase_two.blockers)
        self.assertEqual(x.state,"SIMULATED_RISK_BREACHED")

    def test_25_8_percent_total_loss_equity_breach(self):
        s=good_snapshot()
        mark=replace(s.equity_marks[14],external_event_id="total-loss",
                     observed_at=at(12,10),equity_usd="92",
                     is_utc_day_open=False)
        x=replay(replace(s,equity_marks=s.equity_marks+(mark,)))
        self.assertIn("phase_2_total_drawdown_breached",x.phase_two.blockers)

    def test_26_equal_daily_loss_floor_is_breach(self):
        s=good_snapshot()
        mark=replace(s.equity_marks[0],external_event_id="floor-touch",
                     observed_at=at(1,10),equity_usd="96",
                     is_utc_day_open=False)
        x=replay(replace(s,equity_marks=s.equity_marks+(mark,)))
        self.assertTrue(x.phase_one.risk_breached)
        self.assertIn("phase_1_daily_drawdown_breached",x.phase_one.blockers)

    def test_27_missing_day_open_equity_blocks(self):
        s=good_snapshot()
        rows=tuple(mark for mark in s.equity_marks if mark.external_event_id!="equity-1-1-open")
        x=replay(replace(s,equity_marks=rows))
        self.assertIn("phase_1_missing_or_late_day_open_equity",x.phase_one.blockers)

    def test_28_missing_equity_day_blocks(self):
        s=good_snapshot()
        rows=tuple(mark for mark in s.equity_marks if not mark.external_event_id.startswith("equity-1-1-"))
        x=replay(replace(s,equity_marks=rows))
        self.assertIn("phase_1_missing_equity_for_trading_day",x.phase_one.blockers)

    def test_29_trade_less_than_6_distinct_days_blocks(self):
        s=good_snapshot()
        rows=tuple(replace(row,closed_at=at(1+i//5,12))
                   for i,row in enumerate(s.closed_fills[:25]))+s.closed_fills[25:]
        x=replay(replace(s,closed_fills=rows))
        self.assertIn("phase_1_fewer_than_six_utc_trading_days",x.phase_one.blockers)

    def test_30_profit_goal_stage_one_blocks(self):
        s=good_snapshot()
        rows=tuple(replace(row,gross_realized_usd="0.30") for row in s.closed_fills[:25])+s.closed_fills[25:]
        x=replay(replace(s,closed_fills=rows))
        self.assertIn("phase_1_profit_target_not_met",x.phase_one.blockers)

    def test_31_profit_goal_stage_two_blocks(self):
        s=good_snapshot()
        rows=s.closed_fills[:25]+tuple(replace(row,gross_realized_usd="0.20") for row in s.closed_fills[25:])
        x=replay(replace(s,closed_fills=rows))
        self.assertIn("phase_2_profit_target_not_met",x.phase_two.blockers)

    def test_32_32_percent_consistency_blocks(self):
        s=good_snapshot()
        rows=tuple(replace(row,closed_at=at(1,12+i%2))
                   if i<12 else row for i,row in enumerate(s.closed_fills[:25]))+s.closed_fills[25:]
        x=replay(replace(s,closed_fills=rows))
        self.assertIn("phase_1_best_day_consistency_exceeded",x.phase_one.blockers)

    def test_33_after_deadline_uncompleted_expires(self):
        s=good_snapshot()
        s=replace(s,as_of=START+timedelta(days=29),phase_one_accepted_at=None,
                  phase_two_started_at=None,phase_two_completed_at=None,
                  closed_fills=(),equity_marks=())
        self.assertEqual(replay(s).state,"SIMULATED_EVALUATION_EXPIRED")

    def test_34_after_deadline_completed_math_can_wait_social(self):
        s=replace(good_snapshot(),as_of=START+timedelta(days=35))
        self.assertEqual(replay(s).state,"TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK")

    def test_35_phase2_requires_phase1_acceptance(self):
        with self.assertRaises(ValueError):replay(replace(good_snapshot(),phase_one_accepted_at=None))

    def test_36_phase2_cannot_precede_phase1(self):
        with self.assertRaises(ValueError):replay(replace(good_snapshot(),phase_two_started_at=at(8)))

    def test_37_phase2_completion_cannot_precede_start(self):
        with self.assertRaises(ValueError):replay(replace(good_snapshot(),phase_two_completed_at=at(10)))

    def test_38_phase_transition_after_28_day_deadline_rejected(self):
        with self.assertRaises(ValueError):replay(replace(good_snapshot(),phase_two_completed_at=at(28)))

    def test_39_phase_two_early_close_blocks(self):
        s=good_snapshot()
        rows=s.closed_fills[:-1]+(replace(s.closed_fills[-1],closed_at=at(2,12)),)
        x=replay(replace(s,closed_fills=rows))
        self.assertIn("close_outside_sequential_phase_window",x.blockers)

    def test_40_first_phase_close_after_transition_blocks(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],closed_at=at(12,13)),)+s.closed_fills[1:]
        x=replay(replace(s,closed_fills=rows))
        self.assertIn("close_outside_sequential_phase_window",x.blockers)

    def test_41_unknown_symbol_blocks(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],symbol="EURUSD"),)+s.closed_fills[1:]
        self.assertIn("unsupported_non_xauusd_close",replay(replace(s,closed_fills=rows)).blockers)

    def test_42_cross_source_same_position_id_blocks(self):
        s=good_snapshot()
        rows=s.closed_fills[:-1]+(replace(s.closed_fills[-1],
             external_position_id="position-1-0",data_source="new.source"),)
        self.assertIn("cross_source_position_id_conflict",replay(replace(s,closed_fills=rows)).blockers)

    def test_43_same_position_id_reused_across_phases_blocks(self):
        s=good_snapshot()
        rows=s.closed_fills[:-1]+(replace(s.closed_fills[-1],external_position_id="position-1-0"),)
        self.assertIn("position_reused_between_simulated_phases",replay(replace(s,closed_fills=rows)).blockers)

    def test_44_negative_fee_rejected(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],total_fees_usd="-0.01"),)+s.closed_fills[1:]
        with self.assertRaises(ValueError):replay(replace(s,closed_fills=rows))

    def test_45_floating_point_financial_value_rejected(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],gross_realized_usd=0.4),)+s.closed_fills[1:]
        with self.assertRaises(ValueError):replay(replace(s,closed_fills=rows))

    def test_46_nan_money_rejected(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],gross_realized_usd="NaN"),)+s.closed_fills[1:]
        with self.assertRaises(ValueError):replay(replace(s,closed_fills=rows))

    def test_47_zero_evidence_hash_rejected(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],evidence_sha256="0"*64),)+s.closed_fills[1:]
        with self.assertRaises(ValueError):replay(replace(s,closed_fills=rows))

    def test_48_stale_buyer_terms_rejected(self):
        with self.assertRaises(ValueError):
            replay(replace(good_snapshot(),accepted_terms_sha256="a"*64))

    def test_49_wrong_product_reference_rejected(self):
        with self.assertRaises(ValueError):
            replay(replace(good_snapshot(),challenge_ref="STARTER30-ABCDEFGHIJKLMNOP"))

    def test_50_mutable_list_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            replay(replace(good_snapshot(),closed_fills=list(good_snapshot().closed_fills)))

    def test_51_unbounded_ledger_rejected(self):
        s=good_snapshot()
        with self.assertRaises(ValueError):
            replay(replace(s,closed_fills=s.closed_fills*101))

    def test_52_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            replay(replace(good_snapshot(),as_of=NOW.replace(tzinfo=None)))

    def test_53_asof_before_start_rejected(self):
        with self.assertRaises(ValueError):
            replay(replace(good_snapshot(),as_of=START-timedelta(seconds=1)))

    def test_54_mark_in_future_blocks(self):
        s=good_snapshot()
        m=replace(s.equity_marks[0],observed_at=NOW+timedelta(days=1),external_event_id="future")
        self.assertIn("equity_outside_evaluation_or_future",replay(replace(s,equity_marks=s.equity_marks+(m,))).blockers)

    def test_55_close_after_deadline_blocks(self):
        s=good_snapshot()
        rows=s.closed_fills[:-1]+(replace(s.closed_fills[-1],closed_at=START+timedelta(days=28)),)
        self.assertIn("close_outside_evaluation_or_future",replay(replace(s,closed_fills=rows)).blockers)

    def test_56_missing_complete_phase_one_proof_blocks_math(self):
        s=good_snapshot()
        rows=tuple(row for row in s.closed_fills if row.phase!=1)
        x=replay(replace(s,closed_fills=rows))
        self.assertFalse(x.phase_math_complete)
        self.assertIn("phase_two_started_without_phase_one_mathematical_pass",x.blockers)

    def test_57_untrusted_claims_never_turn_into_external_authenticity(self):
        x=replay(social=good_social())
        self.assertFalse(x.source_authenticity_independently_proven)
        self.assertFalse(x.ledger_completeness_independently_proven)
        self.assertFalse(x.broker_session_calendar_independently_proven)

    def test_58_snapshots_have_an_exact_sha256(self):
        self.assertRegex(replay().snapshot_sha256,r"^[0-9a-f]{64}$")

    def test_59_challenge_id_affects_replay_digest(self):
        s=good_snapshot()
        x=replay(s)
        y=replay(replace(s,challenge_ref="CHALLENGE-ZYXWVUTSRQPONMLK"))
        self.assertNotEqual(x.snapshot_sha256,y.snapshot_sha256)

    def test_60_no_social_post_mutates_challenge_state(self):
        x=replay()
        self.assertEqual(x.combined_unique_closed_positions,50)
        self.assertFalse(x.combined_math_complete)


    def test_61_phase_one_initial_capital_must_be_100(self):
        s=good_snapshot()
        marks2=(replace(s.equity_marks[0],equity_usd="99"),)+s.equity_marks[1:]
        x=replay(replace(s,equity_marks=marks2))
        self.assertIn("phase_1_initial_equity_not_equal_to_plan_capital",x.phase_one.blockers)
        self.assertFalse(x.phase_math_complete)

    def test_62_phase_two_initial_capital_resets_to_100(self):
        s=good_snapshot()
        marks2=s.equity_marks[:14]+(replace(s.equity_marks[14],equity_usd="110"),)+s.equity_marks[15:]
        x=replay(replace(s,equity_marks=marks2))
        self.assertIn("phase_2_initial_equity_not_equal_to_plan_capital",x.phase_two.blockers)

    def test_63_terminal_equity_must_equal_initial_plus_verified_net(self):
        s=good_snapshot()
        rows=s.equity_marks[:13]+(replace(s.equity_marks[13],equity_usd="115"),)+s.equity_marks[14:]
        x=replay(replace(s,equity_marks=rows))
        self.assertIn("phase_1_terminal_equity_pnl_mismatch",x.phase_one.blockers)

    def test_64_terminal_mark_must_not_precede_final_close(self):
        s=good_snapshot()
        rows=s.equity_marks[:-1]+(replace(s.equity_marks[-1],observed_at=at(18,11)),)
        x=replay(replace(s,equity_marks=rows))
        self.assertIn("phase_2_terminal_equity_mark_predates_last_close",x.phase_two.blockers)

    def test_65_equity_source_must_equal_execution_source(self):
        s=good_snapshot()
        rows=s.equity_marks[:14]+(replace(s.equity_marks[14],data_source="alt.demo.feed"),)+s.equity_marks[15:]
        x=replay(replace(s,equity_marks=rows))
        self.assertIn("phase_2_execution_equity_source_mismatch",x.phase_two.blockers)

    def test_66_multiple_close_sources_in_same_phase_fail(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],data_source="second.demo.source"),)+s.closed_fills[1:]
        x=replay(replace(s,closed_fills=rows))
        self.assertIn("phase_1_execution_equity_source_mismatch",x.phase_one.blockers)

    def test_67_fees_reduce_profit_and_require_equity_reconciliation(self):
        s=good_snapshot()
        rows=(replace(s.closed_fills[0],total_fees_usd="0.01"),)+s.closed_fills[1:]
        x=replay(replace(s,closed_fills=rows))
        self.assertEqual(x.phase_one.realized_net_usd,D("9.99"))
        self.assertIn("phase_1_terminal_equity_pnl_mismatch",x.phase_one.blockers)

    def test_68_even_complete_trades_cannot_pass_without_equity_marks(self):
        s=good_snapshot()
        x=replay(replace(s,equity_marks=()))
        self.assertIn("phase_1_equity_history_missing",x.phase_one.blockers)
        self.assertIn("phase_2_equity_history_missing",x.phase_two.blockers)
        self.assertFalse(x.phase_math_complete)


    def test_69_first_stage_digest_is_bound_to_accepted_evidence(self):
        s=good_snapshot()
        x=replay(s)
        self.assertRegex(x.phase_one_frozen_evidence_sha256,r"^[0-9a-f]{64}$")
        self.assertNotEqual(x.phase_one_frozen_evidence_sha256,x.snapshot_sha256)

    def test_70_first_stage_fingerprint_stable_as_assessment_time_advances(self):
        s=good_snapshot()
        original=replay(s)
        later=replay(replace(s,as_of=NOW+timedelta(days=1)))
        self.assertNotEqual(original.snapshot_sha256,later.snapshot_sha256)
        self.assertEqual(original.phase_one_frozen_evidence_sha256,
                         later.phase_one_frozen_evidence_sha256)

    def test_71_first_stage_unaccepted_has_no_frozen_fingerprint(self):
        s=good_snapshot()
        early=replace(s,phase_one_accepted_at=None,
                      phase_two_started_at=None,phase_two_completed_at=None,
                      as_of=at(1,23),closed_fills=s.closed_fills[:4],
                      equity_marks=s.equity_marks[:2])
        self.assertIsNone(replay(early).phase_one_frozen_evidence_sha256)


    def test_72_final_stage_digest_stable_when_assessment_advances(self):
        snap=good_snapshot()
        a=replay(snap)
        b=replay(replace(snap,as_of=NOW+timedelta(days=1)))
        self.assertEqual(a.phase_two_frozen_evidence_sha256,
                         b.phase_two_frozen_evidence_sha256)

    def test_73_final_stage_digest_changes_with_equity_history(self):
        snap=good_snapshot()
        marks=list(snap.equity_marks)
        marks[15]=replace(marks[15],equity_usd="100.99")
        b=replay(replace(snap,equity_marks=tuple(marks)))
        self.assertNotEqual(replay(snap).phase_two_frozen_evidence_sha256,
                            b.phase_two_frozen_evidence_sha256)


if __name__=="__main__":
    unittest.main()
