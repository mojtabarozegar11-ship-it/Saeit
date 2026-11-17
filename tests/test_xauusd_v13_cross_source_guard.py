"""Pure, no-broker cross-source closed-position replay regression checks."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from prop_firm.xauusd_v13_cross_source_guard import assess_closed_position_source_conflicts

T=datetime(2026,11,17,12,tzinfo=timezone.utc)

def event(pos="pos-1",src="demo.one",when=None,status="verified"):
    return SimpleNamespace(
        external_position_id=pos,data_source=src,
        closed_at=when if when is not None else T+timedelta(days=1),
        reconciliation_status=status,
    )

def audit(events):
    return assess_closed_position_source_conflicts(events,evaluation_started_at=T)

class CrossSourceReplayTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(audit([]).collisions,0)

    def test_single_source(self):
        self.assertEqual(audit([event()]).collisions,0)

    def test_same_source_replay_does_not_create_cross_source_conflict(self):
        self.assertEqual(audit([event(),event()]).collisions,0)

    def test_cross_source_same_id_requires_review(self):
        self.assertEqual(audit([event(),event(src="demo.two")]).collisions,1)

    def test_cross_source_different_ids(self):
        self.assertEqual(audit([event(),event(pos="pos-2",src="demo.two")]).collisions,0)

    def test_three_sources_same_id_count_one_conflict(self):
        self.assertEqual(audit([event(),event(src="demo.two"),event(src="demo.three")]).collisions,1)

    def test_pending_not_an_independent_close(self):
        self.assertEqual(audit([event(),event(src="demo.two",status="pending")]).collisions,0)

    def test_out_of_window_ignored(self):
        rows=[event(),event(src="demo.two",when=T+timedelta(days=29))]
        self.assertEqual(audit(rows).collisions,0)

    def test_unbounded_ledger_blocks(self):
        with self.assertRaises(ValueError): audit([event()]*1001)

    def test_naive_close_blocks(self):
        with self.assertRaises(ValueError): audit([event(when=T.replace(tzinfo=None))])

    def test_no_payment_or_trading_authority(self):
        result=audit([event()])
        self.assertFalse(result.checkout_authorized)
        self.assertFalse(result.live_order_authorized)
        self.assertFalse(result.independently_authenticated)

    def test_naive_start_blocks(self):
        with self.assertRaises(ValueError):
            assess_closed_position_source_conflicts(
                [event()],evaluation_started_at=T.replace(tzinfo=None),
            )

if __name__=="__main__":
    unittest.main()
