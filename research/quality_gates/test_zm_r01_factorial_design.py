#!/usr/bin/env python3
"""Metadata-only regression checks; no biological reads, fabricated DEGs or model output."""
import unittest
from collections import Counter
from zm_r01_preflight import GateError, validate_factorial_design


class FactorialDesignGateTests(unittest.TestCase):
    def test_exact_eight_cells_three_libraries_each(self):
        validate_factorial_design(Counter({format(i, '03b'): 3 for i in range(8)}))

    def test_two_cells_twelve_each_are_not_full_factorial(self):
        with self.assertRaises(GateError):
            validate_factorial_design(Counter({'000': 12, '111': 12}))

    def test_unbalanced_eight_cells_rejected(self):
        cells = Counter({format(i, '03b'): 3 for i in range(8)})
        cells['110'], cells['111'] = 4, 2
        with self.assertRaises(GateError):
            validate_factorial_design(cells)

    def test_loss_of_leading_zeroes_rejected(self):
        with self.assertRaises(GateError):
            validate_factorial_design(Counter({str(i): 3 for i in range(8)}))


if __name__ == '__main__':
    unittest.main()
