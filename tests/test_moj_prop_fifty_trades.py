"""Count 50 distinct reconciled closed positions across the same 28-day cohort."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from django.test import SimpleTestCase

from prop_firm.trade_count import count_challenge_trades

START=datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)


def e(n, *, source="broker-ci", position=None, origin="manual", status="verified",
      closed_at=None, **fields):
    data=dict(
        data_source=source,
        external_position_id=position if position is not None else f"position-{n}",
        external_event_id=f"close-{n}",
        execution_origin=origin,
        reconciliation_status=status,
        closed_at=closed_at or START+timedelta(days=2),
    )
    data.update(fields)
    return SimpleNamespace(**data)


class VerifiedFiftyTradesTests(SimpleTestCase):
    def inspect(self, trades, **kwargs):
        return count_challenge_trades(trades, paid_at=START, **kwargs)

    def test_exactly_fifty_closed_positions_suffice(self):
        data=self.inspect([e(i) for i in range(50)])
        self.assertTrue(data.sufficient)
        self.assertEqual(data.valid_closed_positions,50)

    def test_fortynine_positions_fail(self):
        data=self.inspect([e(i) for i in range(49)])
        self.assertFalse(data.sufficient)
        self.assertEqual(data.required,50)

    def test_manual_and_bot_closed_positions_both_count(self):
        items=[e(i,origin="manual" if i%2==0 else "bot") for i in range(50)]
        d=self.inspect(items)
        self.assertEqual(d.manual_positions,25)
        self.assertEqual(d.bot_positions,25)
        self.assertTrue(d.sufficient)

    def test_partial_fills_same_position_count_once(self):
        items=[e(i,position="one-position") for i in range(50)]
        d=self.inspect(items)
        self.assertEqual(d.valid_closed_positions,1)
        self.assertFalse(d.sufficient)

    def test_cross_phase_duplicate_position_id_counts_once(self):
        rows=[e(i) for i in range(25)]+[e(i+25,position=f"position-{i}") for i in range(25)]
        self.assertEqual(self.inspect(rows).valid_closed_positions,25)

    def test_source_and_position_form_provider_scoped_identity(self):
        rows=[e(1,source="broker-a",position="trade1"),
              e(2,source="broker-b",position="trade1")]
        self.assertEqual(self.inspect(rows).valid_closed_positions,2)

    def test_unverified_pending_and_rejected_records_do_not_count(self):
        rows=[e(i) for i in range(48)]+[
            e(48,status="pending"),e(49,status="rejected")
        ]
        d=self.inspect(rows)
        self.assertEqual(d.valid_closed_positions,48)
        self.assertEqual(d.uncountable_events,2)

    def test_unbound_historical_execution_is_not_a_closed_position(self):
        rows=[e(i) for i in range(49)]+[e(49,position="")]
        d=self.inspect(rows)
        self.assertFalse(d.sufficient)

    def test_entry_order_or_unclosed_event_with_no_close_time_excluded(self):
        rows=[e(i) for i in range(49)]+[e(49,closed_at=None)]
        rows[-1].closed_at=None
        self.assertEqual(self.inspect(rows).valid_closed_positions,49)

    def test_after_day_twenty_eight_is_excluded(self):
        rows=[e(i) for i in range(49)]+[e(49,closed_at=START+timedelta(days=28))]
        self.assertEqual(self.inspect(rows).valid_closed_positions,49)

    def test_closes_one_second_before_deadline_count(self):
        data=self.inspect([e(i) for i in range(49)]+[
            e(49,closed_at=START+timedelta(days=28)-timedelta(seconds=1))
        ])
        self.assertTrue(data.sufficient)

    def test_before_paid_invoice_is_excluded(self):
        rows=[e(i) for i in range(49)]+[e(49,closed_at=START-timedelta(seconds=1))]
        self.assertFalse(self.inspect(rows).sufficient)

    def test_unknown_origin_can_still_count_a_real_verified_trade(self):
        data=self.inspect([e(i,origin="unknown") for i in range(50)])
        self.assertEqual(data.unknown_origin_positions,50)
        self.assertTrue(data.sufficient)

    def test_c141_verified_one_position_cannot_override_minimum_to_one(self):
        with self.assertRaisesRegex(ValueError, "below the canonical policy"):
            self.inspect([e(0)], required=1)

    def test_c141_verified_fortynine_cannot_override_minimum_to_fortynine(self):
        with self.assertRaisesRegex(ValueError, "below the canonical policy"):
            self.inspect([e(i) for i in range(49)], required=49)

    def test_c141_higher_threshold_can_still_be_enforced(self):
        self.assertFalse(self.inspect([e(i) for i in range(50)], required=51).sufficient)
        self.assertTrue(self.inspect([e(i) for i in range(51)], required=51).sufficient)

    def test_c141_minimum_matches_published_owner_policy(self):
        from prop_firm.rules import POLICY
        self.assertEqual(self.inspect([]).required, POLICY.min_closed_trades_per_challenge)
        self.assertEqual(POLICY.min_closed_trades_per_challenge, 50)

    def test_imprecise_or_invalid_required_count_rejected(self):
        for value in (False, "50", 0, -1, 49.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.inspect([],required=value)

    def test_non_utc_naive_trade_close_rejected(self):
        with self.assertRaises(ValueError):
            self.inspect([e(0,closed_at=datetime(2026,10,2))])

    def test_zero_unreconciled_sales_do_not_unlock_phase(self):
        self.assertFalse(self.inspect([]).sufficient)
