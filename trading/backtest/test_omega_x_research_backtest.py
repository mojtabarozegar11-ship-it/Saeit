"""Unit checks for the research-only OMEGA X backtest harness."""

import unittest

from omega_x_research_backtest import Bar, run


class OmegaResearchBacktestTests(unittest.TestCase):
    def make_bars(self):
        bars = []
        price = 100.0
        for index in range(180):
            # Deterministic waves provide both trend and reversal periods.
            drift = 0.35 if (index // 30) % 2 == 0 else -0.35
            opened = price
            closed = price + drift
            bars.append(Bar(str(index), opened, max(opened, closed) + 0.2,
                            min(opened, closed) - 0.2, closed, 1.0))
            price = closed
        return bars

    def test_output_is_explicitly_research_only(self):
        result = run(self.make_bars(), 10_000, 0.25, 8, 34, 20, 14,
                     2.0, 1.8, 0.01, 0.1)
        self.assertEqual(result["status"], "research_only")
        self.assertEqual(
            result["lookahead_policy"],
            "signal_on_closed_bar_entry_on_next_open",
        )
        self.assertIn("max_drawdown", result)
        self.assertIn("cost_model", result)

    def test_cost_model_is_recorded(self):
        result = run(self.make_bars(), 10_000, 0.25, 8, 34, 20, 14,
                     2.0, 1.8, 0.02, 0.5)
        self.assertEqual(result["cost_model"]["commission_rate_pct_per_side"], 0.02)
        self.assertEqual(result["cost_model"]["slippage_pips"], 0.5)


if __name__ == "__main__":
    unittest.main()
