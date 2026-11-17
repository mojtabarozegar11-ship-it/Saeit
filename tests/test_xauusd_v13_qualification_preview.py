"""Zero-side-effect v1.3 XAUUSD qualification preview regression cases."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from decimal import Decimal
from unittest.mock import patch
from prop_firm.xauusd_v13_draft_terms import draft_gold_terms_v13
from prop_firm.xauusd_v13_qualification_preview import (
    PhaseProof, review_xauusd_v13_qualification,
)
from prop_firm.xauusd_v13_preflight import DRAFT_CONTRACT_VERSION

START=datetime(2026,11,17,12,tzinfo=timezone.utc)
P1=PhaseProof(1,"9.6","3",6,True,True)
P2=PhaseProof(2,"6","1.8",6,True,True)


def executions(n=50, *, distinct=True, source="review.simulator", verified=True):
    events=[]
    for i in range(n):
        external=str(i if distinct else i//2)
        events.append(SimpleNamespace(
            closed_at=START+timedelta(days=1+i//6),
            external_position_id="position-"+external,
            data_source=source,
            reconciliation_status="verified" if verified else "pending",
            execution_origin="manual",
        ))
    return events


def review(p1=P1,p2=P2,events=None,**kwargs):
    return review_xauusd_v13_qualification(
        first=p1,second=p2,
        reconciled_executions=executions() if events is None else events,
        evaluation_started_at=kwargs.pop("evaluation_started_at",START),
        immutable_ledger_complete=kwargs.pop("immutable_ledger_complete",True),
        independent_ledger_source_verified=kwargs.pop("independent_ledger_source_verified",True),
        **kwargs,
    )


class GoldQualificationPreviewTests(unittest.TestCase):
    def test_fifty_distinct_closes_math_only(self):
        r=review()
        self.assertEqual(r.reviewed_closed_positions,50)
        self.assertTrue(r.entire_challenge_math_pass)
        self.assertFalse(r.paid_enrollment_authorized)
        self.assertFalse(r.broker_account_authorized)
        self.assertFalse(r.real_orders_authorized)

    def test_unique_contract_version(self):
        self.assertEqual(review().contract_version,DRAFT_CONTRACT_VERSION)

    def test_never_requires_social_posts(self):
        self.assertFalse(review().social_post_evidence_required)

    def test_fifty_minus_one_fails(self):
        self.assertIn("minimum_50_unique_closed_positions_total_not_met",
                      review(events=executions(49)).reasons)

    def test_replayed_closes_not_double_counted(self):
        r=review(events=executions(60,distinct=False))
        self.assertEqual(r.reviewed_closed_positions,30)
        self.assertFalse(r.entire_challenge_math_pass)

    def test_cross_stage_replayed_position_rejected(self):
        a=executions(30)
        b=executions(30)
        for e in b:
            e.closed_at+=timedelta(days=8)
        r=review(events=a+b)
        self.assertEqual(r.reviewed_closed_positions,30)
        self.assertFalse(r.entire_challenge_math_pass)

    def test_same_position_id_cross_source_requires_private_reconciliation(self):
        rows=executions(25)
        rows += executions(25, source="second.reviewed.simulator")
        verdict=review(events=rows)
        self.assertEqual(verdict.reviewed_closed_positions,50)
        self.assertIn("cross_source_duplicate_position_review_required",verdict.reasons)
        self.assertFalse(verdict.entire_challenge_math_pass)
        self.assertFalse(verdict.real_orders_authorized)

    def test_distinct_position_ids_across_sources_still_count_only_as_draft(self):
        rows=executions(25)
        second=executions(25, source="second.reviewed.simulator")
        for i,row in enumerate(second):
            row.external_position_id="second-position-"+str(i)
        verdict=review(events=rows+second)
        self.assertEqual(verdict.reviewed_closed_positions,50)
        self.assertNotIn("cross_source_duplicate_position_review_required",verdict.reasons)
        self.assertFalse(verdict.real_orders_authorized)

    def test_phase_one_profit_shortfall(self):
        self.assertIn("phase_1_profit_target_not_met",
                      review(p1=replace(P1,realized_net_profit_usd="9.59")).reasons)

    def test_phase_two_profit_shortfall(self):
        self.assertIn("phase_2_profit_target_not_met",
                      review(p2=replace(P2,realized_net_profit_usd="5.99")).reasons)

    def test_phase_one_fewer_than_six_days(self):
        self.assertIn("phase_1_minimum_trading_days_not_met",
                      review(p1=replace(P1,verified_trading_days=5)).reasons)

    def test_phase_two_fewer_than_six_days(self):
        self.assertIn("phase_2_minimum_trading_days_not_met",
                      review(p2=replace(P2,verified_trading_days=5)).reasons)

    def test_consistency_over_thirty_two_percent_fails(self):
        self.assertIn("phase_2_consistency_not_met",
                      review(p2=replace(P2,max_profitable_day_usd="1.93")).reasons)

    def test_consistency_equal_thirty_two_percent_allows(self):
        r=review(p2=replace(P2,max_profitable_day_usd="1.92"))
        self.assertTrue(r.entire_challenge_math_pass)

    def test_phase_consistency_bound_to_signed_draft_policy(self):
        terms=draft_gold_terms_v13()
        with patch("prop_firm.xauusd_v13_qualification_preview.draft_gold_terms_v13",
                   return_value=replace(terms,max_profitable_day_share_pct=Decimal("40"))):
            # Under 40% cap, a 33% day no longer violates the review math.
            result=review(p2=replace(P2,max_profitable_day_usd="2.0"))
            self.assertNotIn("phase_2_consistency_not_met",result.reasons)

    def test_phase_profit_targets_bound_to_draft_policy(self):
        terms=draft_gold_terms_v13()
        with patch("prop_firm.xauusd_v13_qualification_preview.draft_gold_terms_v13",
                   return_value=replace(terms,stage_two_profit_target_pct=Decimal("7"))):
            result=review()
            self.assertIn("phase_2_profit_target_not_met",result.reasons)

    def test_phase_one_unverified(self):
        self.assertIn("phase_1_independent_proof_absent",
                      review(p1=replace(P1,phase_evidence_verified=False)).reasons)

    def test_phase_two_unverified(self):
        self.assertIn("phase_2_independent_proof_absent",
                      review(p2=replace(P2,phase_evidence_verified=False)).reasons)

    def test_phase_one_risk_unverified(self):
        self.assertIn("phase_1_risk_proof_absent",
                      review(p1=replace(P1,risk_limits_independently_reviewed=False)).reasons)

    def test_phase_two_risk_unverified(self):
        self.assertIn("phase_2_risk_proof_absent",
                      review(p2=replace(P2,risk_limits_independently_reviewed=False)).reasons)

    def test_ledger_incomplete_blocks(self):
        self.assertIn("immutable_closed_trade_ledger_incomplete",
                      review(immutable_ledger_complete=False).reasons)

    def test_ledger_origin_unverified_blocks(self):
        self.assertIn("independent_ledger_origin_unverified",
                      review(independent_ledger_source_verified=False).reasons)

    def test_pending_execution_not_counted(self):
        r=review(events=executions(55,verified=False))
        self.assertEqual(r.reviewed_closed_positions,0)

    def test_outside_28_day_window(self):
        rows=executions()
        rows[0].closed_at=START+timedelta(days=29)
        self.assertEqual(review(events=rows).reviewed_closed_positions,49)

    def test_empty_ledger_rejected(self):
        self.assertIn("minimum_50_unique_closed_positions_total_not_met",
                      review(events=[]).reasons)

    def test_non_ledger_input_rejected(self):
        with self.assertRaises(ValueError):
            review(events="buyer says 50 trades")

    def test_unbounded_ledger_rejected(self):
        with self.assertRaises(ValueError):
            review(events=executions(1001))

    def test_invalid_phase_identity(self):
        with self.assertRaises(ValueError):
            review(p1=replace(P1,phase=2))

    def test_boolean_days_invalid(self):
        with self.assertRaises(ValueError):
            review(p2=replace(P2,verified_trading_days=True))

    def test_floating_pnl_rejected(self):
        with self.assertRaises(ValueError):
            review(p2=replace(P2,realized_net_profit_usd=6.0))

    def test_caller_cannot_self_approve_legal_terms(self):
        with self.assertRaises(ValueError):
            review(legal_terms_approved=True)

    def test_no_funding_even_on_pass(self):
        r=review()
        self.assertTrue(r.entire_challenge_math_pass)
        self.assertFalse(r.funds_independently_verified)
        self.assertFalse(r.signed_customer_contract_proven)
        self.assertFalse(r.terms_fully_reconciled)
        self.assertFalse(r.payouts_authorized)


if __name__=="__main__":
    unittest.main()
