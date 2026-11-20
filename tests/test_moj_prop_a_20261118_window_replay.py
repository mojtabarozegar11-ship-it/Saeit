"""A-cycle regression: independently VERIFIED contradictory close chronology.

Synthetic ledger fixtures are strictly isolated. None are broker attestations,
paid buyers, trades, payments or proof of a running simulator. No ORM writes.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from prop_firm.trade_count import count_challenge_trades

PAID = datetime(2026, 11, 1, tzinfo=timezone.utc)
END = PAID + timedelta(days=28)


def close(n, *, position=None, source="trusted-simulator", at=None,
          status="verified", origin="manual"):
    return SimpleNamespace(
        external_event_id=f"isolated-{n}",
        external_position_id=f"position-{n}" if position is None else position,
        data_source=source,
        closed_at=PAID + timedelta(days=2) if at is None else at,
        reconciliation_status=status,
        execution_origin=origin,
    )


def cohort(extra=(), count=49):
    return [close(n) for n in range(count)] + list(extra)


class VerifiedCloseBoundaryConflictTests(SimpleTestCase):
    def count(self, rows):
        return count_challenge_trades(rows, paid_at=PAID)

    def test_01_exact_fifty_uncontested_in_window_still_pass(self):
        result = self.count(cohort(count=50))
        self.assertTrue(result.sufficient)
        self.assertEqual(result.valid_closed_positions, 50)

    def test_02_same_position_close_on_deadline_poisoned(self):
        rows = cohort([close(50, position="candidate"), close(51, position="candidate", at=END)])
        self.assertEqual(self.count(rows).valid_closed_positions, 49)
        self.assertFalse(self.count(rows).sufficient)

    def test_03_reverse_order_on_deadline_still_poisoned(self):
        rows = cohort([close(51, position="candidate", at=END), close(50, position="candidate")])
        self.assertEqual(self.count(rows).valid_closed_positions, 49)

    def test_04_same_position_close_before_purchase_poisoned(self):
        rows = cohort([close(50, position="candidate"),
                       close(51, position="candidate", at=PAID - timedelta(microseconds=1))])
        self.assertFalse(self.count(rows).sufficient)

    def test_05_reverse_order_before_purchase_still_poisoned(self):
        rows = cohort([close(51, position="candidate", at=PAID - timedelta(seconds=1)),
                       close(50, position="candidate")])
        self.assertEqual(self.count(rows).valid_closed_positions, 49)

    def test_06_close_exactly_at_purchase_allowed_without_conflict(self):
        self.assertEqual(self.count([close(1, at=PAID)]).valid_closed_positions, 1)

    def test_07_close_exactly_at_deadline_alone_not_counted(self):
        result = self.count([close(1, at=END)])
        self.assertEqual(result.valid_closed_positions, 0)
        self.assertEqual(result.uncountable_events, 1)

    def test_08_close_microsecond_before_deadline_allowed(self):
        self.assertEqual(self.count([close(1, at=END - timedelta(microseconds=1))]).valid_closed_positions, 1)

    def test_09_same_origin_two_partial_fills_in_window_count_once(self):
        result = self.count([close(1, position="p"), close(2, position="p")])
        self.assertEqual(result.valid_closed_positions, 1)
        self.assertEqual(result.uncountable_events, 0)

    def test_10_other_provider_same_position_stays_independent(self):
        rows = [close(1, position="p", source="broker-a"),
                close(2, position="p", source="broker-b"),
                close(3, position="p", source="broker-a", at=END)]
        result = self.count(rows)
        self.assertEqual(result.valid_closed_positions, 1)

    def test_11_unrelated_late_position_does_not_poison_valid_one(self):
        rows = [close(1, position="p"), close(2, position="different", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 1)

    def test_12_late_record_without_position_does_not_poison_valid_one(self):
        rows = [close(1, position="p"), close(2, position="", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 1)

    def test_13_late_record_without_source_does_not_poison_valid_one(self):
        rows = [close(1, position="p"), close(2, position="p", source="", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 1)

    def test_14_pending_late_row_cannot_poison_verified_position(self):
        rows = [close(1, position="p"), close(2, position="p", status="pending", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 1)

    def test_15_rejected_late_row_cannot_poison_verified_position(self):
        rows = [close(1, position="p"), close(2, position="p", status="rejected", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 1)

    def test_16_existing_origin_conflict_still_poisoned(self):
        rows = [close(1, position="p", origin="manual"),
                close(2, position="p", origin="bot")]
        self.assertEqual(self.count(rows).valid_closed_positions, 0)

    def test_17_origin_and_window_conflicts_remain_rejected(self):
        rows = [close(1, position="p", origin="manual"),
                close(2, position="p", origin="bot"),
                close(3, position="p", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 0)

    def test_18_multiple_late_closes_cannot_restore_position(self):
        rows = [close(1, position="p"), close(2, position="p", at=END),
                close(3, position="p", at=END + timedelta(days=1))]
        result = self.count(rows)
        self.assertEqual(result.valid_closed_positions, 0)
        self.assertFalse(result.sufficient)

    def test_19_two_early_partial_closes_and_late_close_fail_closed(self):
        rows = [close(1, position="p"), close(2, position="p"),
                close(3, position="p", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 0)

    def test_20_normalized_provider_id_cannot_bypass_poison(self):
        rows = [close(1, position="p", source="provider"),
                close(2, position=" p ", source=" provider ", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 0)

    def test_21_non_utc_timezone_exact_deadline_is_excluded(self):
        local_deadline = END.astimezone(timezone(timedelta(hours=3)))
        rows = [close(1, position="p"), close(2, position="p", at=local_deadline)]
        self.assertEqual(self.count(rows).valid_closed_positions, 0)

    def test_22_unknown_origin_does_not_exempt_window_checks(self):
        rows = [close(1, position="p", origin="unknown"),
                close(2, position="p", origin="unknown", at=END)]
        self.assertEqual(self.count(rows).valid_closed_positions, 0)

    def test_23_cannot_lower_50_trades_policy_by_parameter(self):
        with self.assertRaises(ValueError):
            count_challenge_trades([], paid_at=PAID, required=49)

    def test_24_invalid_verified_record_without_in_window_sibling(self):
        result = self.count([close(1, at=PAID - timedelta(days=1))])
        self.assertEqual(result.valid_closed_positions, 0)
        self.assertEqual(result.uncountable_events, 1)

    def test_25_window_conflict_cannot_create_fiftieth_trade(self):
        rows = cohort([close(50, position="candidate"),
                       close(51, position="candidate", at=END)], count=49)
        result = self.count(rows)
        self.assertEqual(result.valid_closed_positions, 49)
        self.assertEqual(result.manual_positions, 49)
        self.assertFalse(result.sufficient)
