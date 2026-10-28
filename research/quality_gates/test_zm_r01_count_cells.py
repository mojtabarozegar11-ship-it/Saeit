#!/usr/bin/env python3
"""Synthetic token-only regression tests; these are NOT biological count data."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zm_r01_preflight import valid_raw_integer_count


class RawIntegerCountCellTests(unittest.TestCase):
    def test_ascii_integer_tokens_are_valid(self):
        for token in ("0", "00", "123", "9876543210"):
            with self.subTest(token=token):
                self.assertTrue(valid_raw_integer_count(token))

    def test_unicode_digits_are_not_portable_raw_counts(self):
        for token in ("١٢", "۱۲", "１２", "²", "四"):
            with self.subTest(token=token):
                self.assertFalse(valid_raw_integer_count(token))

    def test_missing_fractional_signed_and_whitespace_tokens_rejected(self):
        for token in ("", "-1", "+1", "1.5", " 10", "10 ", "1e3", "1,000", "NA", None, 10):
            with self.subTest(token=repr(token)):
                self.assertFalse(valid_raw_integer_count(token))


if __name__ == "__main__":
    unittest.main()
