from datetime import date, datetime, timedelta
from decimal import Decimal as D
import unittest

from prop_firm.mojprop_starter30_product_profile import assess_starter30_consistency


class Starter30ConsistencyTests(unittest.TestCase):
    def check(self, values, total):
        days = {date(2026, 1, 1) + timedelta(days=i): D(v)
                for i, v in enumerate(values)}
        return assess_starter30_consistency(
            daily_realized_net_usd=days, reconciled_realized_net_usd=D(total))

    def test_exact_half_is_allowed(self):
        result = self.check(["50", "30", "20"], "100")
        self.assertTrue(result.allowed)
        self.assertEqual(result.cap_pct, D("50"))

    def test_one_cent_above_half_is_rejected(self):
        result = self.check(["50.01", "49.99"], "100")
        self.assertFalse(result.allowed)
        self.assertIn("starter30_profit_consistency_not_met", result.reasons)

    def test_between_old_and_new_cap(self):
        self.assertTrue(self.check(["40", "30", "30"], "100").allowed)

    def test_loss_days_reduce_denominator(self):
        self.assertFalse(self.check(["50", "50", "-20"], "80").allowed)

    def test_zero_and_negative_profit(self):
        for values, total in [(["20", "-20"], "0"), (["-10"], "-10")]:
            with self.subTest(total=total):
                self.assertIn("positive_net_profit_required", self.check(values, total).reasons)

    def test_missing_days(self):
        self.assertIn("daily_evidence_missing", self.check([], "0").reasons)

    def test_reconciliation(self):
        self.assertIn("daily_net_profit_reconciliation_mismatch",
                      self.check(["40", "40"], "100").reasons)

    def test_invalid_values_fail_closed(self):
        for v in (D("NaN"), D("Infinity"), D("1.001"), 10.0, True, D("10000000000000000")):
            with self.subTest(value=v):
                with self.assertRaises(ValueError):
                    assess_starter30_consistency(daily_realized_net_usd={date(2026,1,1): v},
                                                  reconciled_realized_net_usd=D("10"))

    def test_invalid_day_key(self):
        with self.assertRaises(ValueError):
            assess_starter30_consistency(daily_realized_net_usd={datetime(2026,1,1):D("10")},
                                          reconciled_realized_net_usd=D("10"))

    def test_excessive_day_count(self):
        with self.assertRaises(ValueError):
            self.check(["1"] * 61, "61")

    def test_single_profitable_day_never_passes(self):
        self.assertFalse(self.check(["100"], "100").allowed)
