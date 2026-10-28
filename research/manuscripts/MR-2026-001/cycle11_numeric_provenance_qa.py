#!/usr/bin/env python3
"""Reproducible arithmetic QA of *reported summary numbers*, NOT source raw-data replication.
Bonet 2026: https://doi.org/10.1016/j.agwat.2026.110131 (abstract)
Bernhardt 2026: https://doi.org/10.1016/j.agwat.2026.110730 (§3.4 indexed text)
"""
import math
import unittest

class SummaryArithmeticQA(unittest.TestCase):
    def test_bonet_absolute_difference(self):
        self.assertAlmostEqual(111.3 - 99.4, 11.9, places=10)
    def test_bonet_percentage_vs_reported_rounded(self):
        pct = (111.3 - 99.4) / 111.3 * 100
        self.assertAlmostEqual(pct, 10.69182389937106, places=8)
        self.assertEqual(round(pct), 11)
    def test_bernhardt_rmse_mae_ratio(self):
        self.assertAlmostEqual(2.2 / 1.5, 1.4666666666666668, places=8)
    def test_bernhardt_correlation_t_from_rounded_r(self):
        r, n = 0.93, 7
        t = r * math.sqrt((n - 2) / (1 - r * r))
        self.assertTrue(5.5 < t < 5.8)  # paper t=5.61 from unrounded source r
    def test_bernhardt_percent_difference_range(self):
        self.assertAlmostEqual(47.5 - (-34.7), 82.2, places=8)
    def test_no_causal_adoption_inference_from_arithmetic(self):
        measured_farmer_adoption_n = None
        self.assertIsNone(measured_farmer_adoption_n)
if __name__ == "__main__":
    unittest.main(verbosity=2)
