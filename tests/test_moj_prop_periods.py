"""Conservative thirty-day profit period eligibility regression."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from prop_firm.periods import most_recent_completed_period, completed_period_by_number, period_statistics

START = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def event(*, days, dollars, hours=0):
    return SimpleNamespace(closed_at=START + timedelta(days=days, hours=hours),
                           net_realized_usd=Decimal(str(dollars)))


class MojPropPeriodsTests(unittest.TestCase):
    def period(self, days):
        return most_recent_completed_period(opened_at=START,
                                            as_of=START + timedelta(days=days))

    def test_29_day_account_has_no_complete_period(self):
        self.assertIsNone(self.period(29))

    def test_at_day_30_period_one_is_complete(self):
        p = self.period(30)
        self.assertEqual((p.number, p.start, p.end),
                         (1, START, START + timedelta(days=30)))

    def test_day_59_still_uses_period_one(self):
        self.assertEqual(self.period(59).number, 1)

    def test_day_60_uses_period_two_only(self):
        p = self.period(60)
        self.assertEqual((p.number, p.start, p.end),
                         (2, START + timedelta(days=30), START + timedelta(days=60)))

    def test_both_endpoints_are_utc_dates(self):
        p = most_recent_completed_period(
            opened_at=START.replace(tzinfo=timezone(timedelta(hours=3))),
            as_of=START + timedelta(days=40))
        self.assertEqual(p.start.tzinfo, timezone.utc)
        self.assertEqual(p.end.tzinfo, timezone.utc)

    def test_outside_current_period_trades_do_not_count(self):
        p = self.period(60)
        data = [event(days=2, dollars=90), event(days=31, dollars=2),
                event(days=59, dollars=3)]
        result = period_statistics(data, p)
        self.assertEqual(result["net"], Decimal("5"))
        self.assertEqual(result["trading_days"], 2)
        self.assertEqual(result["best_day"], Decimal("3"))

    def test_trades_at_exact_period_end_belong_to_next_cycle(self):
        p = self.period(30)
        result = period_statistics([event(days=29, dollars=1),
                                    event(days=30, dollars=10)], p)
        self.assertEqual(result["net"], 1)

    def test_loss_day_offsets_profit_and_counts_as_trading_day(self):
        p = self.period(30)
        result = period_statistics([event(days=2, dollars=10),
                                    event(days=3, dollars=-9)], p)
        self.assertEqual(result["net"], 1)
        self.assertEqual(result["best_day"], 10)
        self.assertEqual(result["trading_days"], 2)

    def test_same_day_executions_count_as_one_day(self):
        p = self.period(30)
        result = period_statistics([event(days=2, dollars=2),
                                    event(days=2, dollars=3, hours=4)], p)
        self.assertEqual(result["trading_days"], 1)
        self.assertEqual(result["best_day"], 5)

    def test_missing_open_date_is_never_eligible(self):
        self.assertIsNone(most_recent_completed_period(opened_at=None, as_of=START))

    def test_naive_timestamp_is_never_eligible(self):
        self.assertIsNone(most_recent_completed_period(
            opened_at=START.replace(tzinfo=None), as_of=START + timedelta(days=31)))

    def test_period_stats_do_not_invent_data_without_period(self):
        self.assertIsNone(period_statistics([event(days=3, dollars=12)], None))

    def test_future_open_date_is_never_eligible(self):
        self.assertIsNone(most_recent_completed_period(
            opened_at=START + timedelta(days=31), as_of=START))

    def test_empty_completed_cycle_is_zero_and_no_trades(self):
        result = period_statistics([], self.period(30))
        self.assertEqual(result["net"], 0)
        self.assertEqual(result["trading_days"], 0)


if __name__ == "__main__":
    unittest.main()


    def test_first_completed_month_can_be_reconciled_much_later(self):
        period = completed_period_by_number(
            opened_at=START, as_of=START + timedelta(days=100), period_number=1
        )
        self.assertEqual(period.number, 1)
        self.assertEqual(period.start, START)
        self.assertEqual(period.end, START + timedelta(days=30))

    def test_last_completed_month_at_day_100_is_third(self):
        period = completed_period_by_number(
            opened_at=START, as_of=START + timedelta(days=100), period_number=3
        )
        self.assertEqual(period.start, START + timedelta(days=60))
        self.assertEqual(period.end, START + timedelta(days=90))

    def test_selected_month_must_be_finished(self):
        self.assertIsNone(completed_period_by_number(
            opened_at=START, as_of=START + timedelta(days=59), period_number=2
        ))

    def test_invalid_month_numbers_rejected(self):
        for number in (-1, 0, True, 1.0, "1", None):
            with self.subTest(number=number):
                self.assertIsNone(completed_period_by_number(
                    opened_at=START, as_of=START + timedelta(days=100),
                    period_number=number,
                ))
