"""Regression contract for the OMEGA X breakout lookback.

This test mirrors the indexing contract used by MojTradeOmegaXDemoBot:
the just-closed candle is the candidate breakout candle, while the
20-candle range must contain only preceding candles.
"""

import unittest


def breakout_range(highs, lows, index, lookback=20):
    start = max(0, index - lookback)
    count = index - start
    if count <= 0:
        raise ValueError("lookback must contain a preceding candle")
    return max(highs[start : start + count]), min(lows[start : start + count])


class OmegaBreakoutContractTests(unittest.TestCase):
    def test_buy_breakout_excludes_candidate_candle(self):
        highs = [100.0 + i * 0.1 for i in range(20)] + [103.0]
        lows = [99.0 + i * 0.1 for i in range(20)] + [101.0]
        current_close = 102.9

        range_high, range_low = breakout_range(highs, lows, index=20)
        self.assertEqual(range_high, max(highs[:20]))
        self.assertEqual(range_low, min(lows[:20]))
        self.assertGreater(current_close, range_high)

    def test_sell_breakout_excludes_candidate_candle(self):
        highs = [110.0 - i * 0.1 for i in range(20)] + [108.0]
        lows = [109.0 - i * 0.1 for i in range(20)] + [107.0]
        current_close = 107.1

        range_high, range_low = breakout_range(highs, lows, index=20)
        self.assertEqual(range_high, max(highs[:20]))
        self.assertEqual(range_low, min(lows[:20]))
        self.assertLess(current_close, range_low)

    def test_candidate_in_old_range_would_make_breakout_impossible(self):
        highs = [100.0] * 20 + [105.0]
        lows = [90.0] * 20 + [95.0]
        current_close = 104.0

        old_range_high = max(highs[:21])
        new_range_high, _ = breakout_range(highs, lows, index=20)

        self.assertFalse(current_close > old_range_high)
        self.assertTrue(current_close > new_range_high)


if __name__ == "__main__":
    unittest.main()
