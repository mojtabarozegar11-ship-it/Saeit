"""C21 fail-closed cTrader observation freshness source contracts.

These checks exercise structural safety contracts, not an authenticated cTrader
runtime or an external risk coordinator. The official CI also compiles both bots.
"""
from pathlib import Path
import re
import unittest


TRADING = Path(__file__).resolve().parents[1] / "trading"
BOTS = {
    "scalp": (TRADING / "MojTradeDemoBot.cs").read_text(encoding="utf-8"),
    "omega": (TRADING / "MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8"),
}


class FreshObservationContract(unittest.TestCase):
    def test_attempt_and_success_timestamps_are_distinct(self):
        for name, bot in BOTS.items():
            with self.subTest(bot=name):
                self.assertIn("private DateTime _lastObservationUtc = DateTime.MinValue;", bot)
                self.assertIn("private DateTime _lastSuccessfulObservationUtc = DateTime.MinValue;", bot)

    def test_success_stamp_only_follows_valid_coordinator_ack(self):
        for name, bot in BOTS.items():
            with self.subTest(bot=name):
                self.assertEqual(bot.count("_lastSuccessfulObservationUtc = now;"), 1)
                self.assertRegex(bot, r'if \(response\.IsSuccessful && response\.StatusCode == 200 &&\s*'
                                      r'response\.Body == "OBSERVED"\)\s*\{\s*'
                                      r'_lastSuccessfulObservationUtc = now;\s*return;')

    def test_freshness_excludes_missing_old_future_and_previous_day(self):
        for name, bot in BOTS.items():
            with self.subTest(bot=name):
                method = bot.split("private bool HasFreshRiskObservation()", 1)[1].split("}", 1)[0]
                for guard in ("_lastSuccessfulObservationUtc != DateTime.MinValue",
                              "now >= _lastSuccessfulObservationUtc",
                              "now.Date == _lastSuccessfulObservationUtc.Date",
                              "(now - _lastSuccessfulObservationUtc).TotalSeconds <= 60"):
                    self.assertIn(guard, method)

    def test_trailing_management_requires_recent_success(self):
        for name, bot in BOTS.items():
            with self.subTest(bot=name):
                handler = bot.split("protected override void OnTick()", 1)[1].split(
                    "protected override void OnTimer()", 1)[0]
                self.assertIn("if (!HasFreshRiskObservation())", handler)
                if name == "scalp":
                    self.assertLess(handler.index("HasFreshRiskObservation()"),
                                    handler.index("ManageOpenPositions()"))
                else:
                    self.assertLess(handler.index("HasFreshRiskObservation()"),
                                    handler.index("ModifyPosition("))

    def test_new_entries_also_require_fresh_observation(self):
        scalp, omega = BOTS["scalp"], BOTS["omega"]
        scalp_order = scalp.split("private void TryOpen(", 1)[1].split("private bool RiskStopActive()", 1)[0]
        omega_order = omega.split("private void SubmitDemoOrder(", 1)[1].split(
            "private double TodayAccountRealizedProfit()", 1)[0]
        self.assertLess(scalp_order.index("if (!HasFreshRiskObservation())"),
                        scalp_order.index("ExecuteMarketOrder("))
        self.assertLess(omega_order.index("if (!HasFreshRiskObservation())"),
                        omega_order.index("ExecuteMarketOrder("))
        self.assertIn("if (!HasFreshRiskObservation())", scalp.split("protected override void OnBarClosed()", 1)[1])
        self.assertIn("if (!HasFreshRiskObservation())", omega.split("protected override void OnBarClosed()", 1)[1])


if __name__ == "__main__":
    unittest.main()
