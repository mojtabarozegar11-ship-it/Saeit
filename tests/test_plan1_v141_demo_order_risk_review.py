"""No-side-effect risk-stage bridge tests for proposed MOJ PROP Plan1 demo."""
import unittest
from dataclasses import replace
from datetime import timedelta

from prop_firm.plan1_v141_simulated_challenge_engine import (
    replay_simulated_challenge,
)
from prop_firm.plan1_v141_demo_order_risk_review import review_v141_demo_order
from prop_firm.xauusd_v13_preflight import (
    DRAFT_CONTRACT_VERSION, GoldOrderSnapshot,
)
from tests.test_plan1_v141_simulated_challenge_engine import (
    START, at, good_snapshot, good_social,
)

def stage_one():
    s=good_snapshot()
    return replace(
        s,phase_one_accepted_at=None,phase_two_started_at=None,
        phase_two_completed_at=None,as_of=at(1,23),
        closed_fills=s.closed_fills[:4],equity_marks=s.equity_marks[:2],
    )


def stage_two():
    s=good_snapshot()
    return replace(
        s,phase_two_completed_at=None,as_of=at(12,23),
        closed_fills=s.closed_fills[:29],equity_marks=s.equity_marks[:16],
    )


def candidate(*, phase=1, challenge=None, **kw):
    s = stage_one() if phase == 1 else stage_two()
    result=replay_simulated_challenge(snapshot=s) if challenge is None else challenge
    current = result.phase_one if phase==1 else result.phase_two
    assessment=at(1 if phase==1 else 12,23)
    data=dict(
        product="MOJ-PROP-01",contract_version=DRAFT_CONTRACT_VERSION,
        symbol="XAUUSD",account_currency="USD",initial_capital="100",
        equity=str(current.latest_verified_equity_usd),
        day_open_equity=str(current.latest_verified_day_open_usd),
        existing_open_remaining_stop_risk="0",side="buy",
        mid_price_per_oz="4000",stop_price_per_oz="3998.10",
        lot_quantity="0.01",minimum_lot="0.01",lot_step="0.01",
        ounces_per_lot="100",min_stop_distance_per_oz="0.2",
        full_spread_per_oz="0.3",slippage_reserve_per_oz="0.2",
        roundtrip_fees_usd="0.1",margin_required_usd="25",
        free_margin_usd="75",quote_at=assessment,assessed_at=assessment,
        broker_snapshot_claimed=True,complete_open_positions_claimed=True,
        symbol_spec_claimed=True,stop_claimed=True,
    )
    data.update(kw)
    return result,GoldOrderSnapshot(**data)


def review(phase=1, *, challenge=None, order=None):
    if challenge is None or order is None:
        current, proposed=candidate(phase=phase)
        if challenge is None:challenge=current
        if order is None:order=proposed
    return review_v141_demo_order(challenge=challenge,intended_phase=phase,order=order)


class V141DemoPretradeTests(unittest.TestCase):
    def test_01_stage_one_risk_math_can_pass(self):
        x=review(1)
        self.assertTrue(x.math_admissible)
        self.assertEqual(x.order_risk_usd,2.5)

    def test_02_stage_two_risk_math_can_pass_after_first(self):
        x=review(2)
        self.assertTrue(x.math_admissible)

    def test_03_no_demo_order_submitted_by_review(self):
        x=review(1)
        self.assertFalse(x.demo_order_submitted)

    def test_04_real_order_never_submitted(self):
        self.assertFalse(review(1).real_broker_order_submitted)

    def test_05_no_trading_authority_even_if_risk_math_passes(self):
        x=review(1)
        self.assertFalse(x.trading_enabled)
        self.assertFalse(x.checkout_enabled)
        self.assertFalse(x.capital_or_payout_authorized)

    def test_06_no_independent_broker_feed_assumed(self):
        x=review(1)
        self.assertFalse(x.trusted_broker_or_simulator_authenticated)
        self.assertFalse(x.complete_open_positions_independently_reconciled)

    def test_07_wrong_stage_blocks_review(self):
        x=review(2,challenge=replay_simulated_challenge(snapshot=stage_one()),
                 order=candidate(phase=2)[1])
        self.assertFalse(x.math_admissible)
        self.assertIn("stage_not_currently_open_for_demo_risk_review",x.blockers)

    def test_08_stage_one_closes_after_completed_phases(self):
        completed=replay_simulated_challenge(snapshot=good_snapshot())
        x=review(1,challenge=completed,order=candidate()[1])
        self.assertIn("stage_not_currently_open_for_demo_risk_review",x.blockers)

    def test_09_stale_replay_equity_fails(self):
        s=replace(stage_one(),as_of=at(2,0))
        status=replay_simulated_challenge(snapshot=s)
        _,order=candidate(phase=1,assessed_at=at(2,0),quote_at=at(2,0))
        x=review(1,challenge=status,order=order)
        self.assertIn("stale_or_future_equity_mark",x.blockers)

    def test_10_mismatched_equity_rejected(self):
        status,order=candidate(equity="150")
        x=review(1,challenge=status,order=order)
        self.assertIn("order_equity_not_bound_to_latest_challenge_mark",x.blockers)

    def test_11_mismatched_day_open_equity_rejected(self):
        status,order=candidate(day_open_equity="110")
        x=review(1,challenge=status,order=order)
        self.assertIn("order_equity_not_bound_to_latest_challenge_mark",x.blockers)

    def test_12_risk_above_3_usd_rejected(self):
        status,order=candidate(stop_price_per_oz="3997")
        x=review(1,challenge=status,order=order)
        self.assertIn("trade_exceeds_3pct",x.blockers)

    def test_13_total_risk_over_8_usd_rejected(self):
        status,order=candidate(existing_open_remaining_stop_risk="8")
        x=review(1,challenge=status,order=order)
        self.assertIn("open_positions_exceed_8pct",x.blockers)

    def test_14_stop_headroom_considers_4_percent_daily_floor(self):
        status,order=candidate(existing_open_remaining_stop_risk="3")
        x=review(1,challenge=status,order=order)
        self.assertIn("projected_stops_breach_drawdown_limit",x.blockers)

    def test_15_quote_over_5_minutes_stale(self):
        status,order=candidate(quote_at=at(1,23)-timedelta(minutes=6))
        self.assertIn("stale_or_future_quote",review(1,challenge=status,order=order).blockers)

    def test_16_incorrect_buyer_sku_rejected(self):
        status,order=candidate(product="MOJPROP-STARTER30")
        with self.assertRaises(ValueError):
            review(1,challenge=status,order=order)

    def test_17_incorrect_contract_revision_rejected(self):
        status,order=candidate(contract_version="2026-11-15/v1.2")
        with self.assertRaises(ValueError):
            review(1,challenge=status,order=order)

    def test_18_old_stale_challenge_digest_rejected(self):
        status,order=candidate()
        with self.assertRaises(ValueError):
            review(1,challenge=replace(status,terms_sha256="0"*64),order=order)

    def test_19_claim_of_broker_authenticity_not_accepted(self):
        status,order=candidate()
        with self.assertRaises(ValueError):
            review(1,challenge=replace(status,source_authenticity_independently_proven=True),order=order)

    def test_20_wrong_order_stage_type_rejected(self):
        status,order=candidate()
        with self.assertRaises(ValueError):
            review_v141_demo_order(challenge=status,intended_phase=True,order=order)

    def test_21_no_trx_or_enrollment_on_new_candidate(self):
        x=review(1)
        self.assertFalse(x.customer_enrollment_authorized)
        self.assertFalse(x.checkout_enabled)

    def test_22_margin_shortfall_rejected(self):
        status,order=candidate(free_margin_usd="5")
        self.assertIn("insufficient_verified_free_margin",review(1,challenge=status,order=order).blockers)

    def test_23_subminimum_lot_rejected(self):
        status,order=candidate(lot_quantity="0.005")
        self.assertIn("broker_lot_step_rejected",review(1,challenge=status,order=order)

    def test_24_order_clock_must_match_replayed_snapshot(self):
        status,order=candidate(assessed_at=at(1,23)+timedelta(minutes=1),
                               quote_at=at(1,23)+timedelta(minutes=1))
        self.assertIn("assessed_at_does_not_match_challenge_snapshot",
                      review(1,challenge=status,order=order).blockers)

if __name__=="__main__":
    unittest.main()
