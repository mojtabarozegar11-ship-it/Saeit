"""Synthetic, offline-only tests for versioned day/phase boundaries."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from prop_firm.xauusd_v13_phase_day_audit import audit_xauusd_v13_phase_days

T = datetime(2026, 11, 1, 0, tzinfo=timezone.utc)
PASS = T + timedelta(days=12)
PHASE_TWO = T + timedelta(days=12, minutes=1)


def item(i, phase=1, source="sim-a", status="verified"):
    day = (i // 3) + (1 if phase == 1 else 13)
    return SimpleNamespace(phase=phase, reconciliation_status=status,
                           closed_at=T + timedelta(days=day, hours=2),
                           data_source=source,
                           external_position_id=f"{phase}:{i}")


def sample():
    # 25 trades across 9 days in stage 1, 25 across 9 days in stage 2.
    return [item(i, 1) for i in range(25)] + [item(i, 2) for i in range(25)]


def review(rows=None, **kw):
    return audit_xauusd_v13_phase_days(
        closed_events=sample() if rows is None else rows,
        evaluation_started_at=kw.get("start", T),
        phase_one_passed_at=kw.get("first_pass", PASS),
        phase_two_started_at=kw.get("second_start", PHASE_TWO),
    )


class TimelineTests(unittest.TestCase):
    def test_50_verified_closes_across_2_stages_mathematically_pass(self):
        r = review()
        self.assertEqual((r.phase_one_utc_days, r.phase_two_utc_days), (9, 9))
        self.assertEqual(r.distinct_verified_closed_positions, 50)
        self.assertTrue(r.timeline_mathematically_coherent)

    def test_no_funding_or_orders_even_if_math_passes(self):
        r = review()
        self.assertFalse(r.customer_funding_authorized)
        self.assertFalse(r.live_order_authorized)
        self.assertFalse(r.invoice_authorized)
        self.assertFalse(r.signed_customer_contract_verified)
        self.assertFalse(r.event_source_independently_authenticated)
        self.assertFalse(r.broker_session_calendar_independently_verified)

    def test_49_closed_positions_fail(self):
        self.assertIn("fewer_than_fifty_distinct_verified_closes", review(rows=sample()[:-1]).blockers)

    def test_six_utc_days_per_phase_required(self):
        rows = [item(i, 1) for i in range(25)] + [item(i, 2) for i in range(25)]
        for i in range(25,50):
            rows[i].closed_at=T+timedelta(days=13, hours=2)
        self.assertIn("phase_two_less_than_six_utc_days", review(rows=rows).blockers)

    def test_duplicate_fill_same_position_not_counted(self):
        rows=sample()
        rows[0].external_position_id=rows[1].external_position_id
        self.assertEqual(review(rows=rows).distinct_verified_closed_positions,49)

    def test_reused_position_across_phases_blocks(self):
        rows=sample()
        rows[-1].external_position_id=rows[0].external_position_id
        self.assertIn("verified_position_reused_across_phases", review(rows=rows).blockers)

    def test_unverified_close_does_not_count(self):
        rows=sample();rows[-1].reconciliation_status="pending"
        self.assertEqual(review(rows=rows).distinct_verified_closed_positions,49)

    def test_wrong_phase_identity_blocks(self):
        rows=sample();rows[-1].phase="2"
        self.assertIn("verified_close_missing_valid_phase", review(rows=rows).blockers)

    def test_phase_two_close_before_phase_two_start_blocks(self):
        rows=sample();rows[-1].closed_at=T+timedelta(days=4)
        self.assertIn("verified_close_in_wrong_phase_window", review(rows=rows).blockers)

    def test_phase_one_close_after_pass_blocks(self):
        rows=sample();rows[0].closed_at=T+timedelta(days=13)
        self.assertIn("verified_close_in_wrong_phase_window", review(rows=rows).blockers)

    def test_out_of_window_close_blocks(self):
        rows=sample();rows[-1].closed_at=T+timedelta(days=28)
        self.assertIn("verified_close_outside_evaluation_window", review(rows=rows).blockers)

    def test_missing_identity_blocks(self):
        rows=sample();rows[0].external_position_id=""
        self.assertIn("verified_close_missing_stable_identity", review(rows=rows).blockers)

    def test_wrong_phase_order_raises(self):
        with self.assertRaises(ValueError): review(second_start=T+timedelta(days=11))

    def test_naive_start_rejected(self):
        with self.assertRaises(ValueError): review(start=T.replace(tzinfo=None))

    def test_non_ledger_input_rejected(self):
        with self.assertRaises(ValueError): review(rows="not an immutable ledger")

    def test_bounded_ledger(self):
        with self.assertRaises(ValueError): review(rows=[sample()[0]]*1001)

    def test_verified_close_missing_timestamp_raises(self):
        rows=sample();rows[0].closed_at=None
        with self.assertRaises(ValueError): review(rows=rows)

    def test_does_not_accept_boolean_phase(self):
        rows=sample();rows[0].phase=True
        self.assertIn("verified_close_missing_valid_phase", review(rows=rows).blockers)

    def test_utc_day_boundary_separate_calendar_days(self):
        rows=sample()
        rows[0].closed_at=T+timedelta(days=1, hours=23)
        rows[1].closed_at=T+timedelta(days=2, hours=1)
        self.assertTrue(review(rows=rows).timeline_mathematically_coherent)

    def test_multiple_sources_distinct_identifiers_review_only(self):
        rows=sample()
        for e in rows[25:]: e.data_source="sim-b"
        self.assertTrue(review(rows=rows).timeline_mathematically_coherent)
        self.assertFalse(review(rows=rows).event_source_independently_authenticated)

if __name__ == '__main__':
    unittest.main()
