"""Static risk-contract checks for the two cTrader demo adapters.

These checks are intentionally source-level; they do NOT prove that cTrader
compiles the bots, accepts the orders, or enforces cross-process atomic limits.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCALP = (ROOT / "trading" / "MojTradeDemoBot.cs").read_text(encoding="utf-8")
OMEGA = (ROOT / "trading" / "MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8")


class MojTradeC07SafetyContract(unittest.TestCase):
    def test_both_adapters_reject_live_accounts(self):
        self.assertGreaterEqual(SCALP.count("Account.IsLive"), 3)
        self.assertGreaterEqual(OMEGA.count("Account.IsLive"), 3)

    def test_scalp_rechecks_at_order_boundary(self):
        boundary = SCALP.split("private void TryOpen(", 1)[1].split(
            "private bool RiskStopActive()", 1)[0]
        for gate in ("!EnableCoordinatedDemoTrading", "!CoordinatorConfigured()",
                     "_halted || Account.IsLive || RiskStopActive()",
                     "SharedMojTradePositionCount() >= SharedPositionCap"):
            self.assertIn(gate, boundary)
        self.assertLess(boundary.index("RiskStopActive()"),
                        boundary.index("var reservationId = ReserveCoordinatedSlot("))

    def test_omega_rechecks_at_order_boundary(self):
        boundary = OMEGA.split("private void SubmitDemoOrder(", 1)[1].split(
            "private double TodayAccountRealizedProfit()", 1)[0]
        for gate in ("_halted || !EnableDemoTrading || !EnableCoordinatedDemoTrading",
                     "!CoordinatorConfigured() || Account.IsLive || DailyLossReached()",
                     "SharedMojTradePositionCount() >= SharedPositionCap"):
            self.assertIn(gate, boundary)
        self.assertLess(boundary.index("DailyLossReached()"),
                        boundary.index("var reservationId = ReserveCoordinatedSlot("))

    def test_scalp_daily_stop_includes_floating_equity(self):
        self.assertIn("Account.Equity <= _dailyStartEquity - allowedLoss", SCALP)

    def test_scalp_daily_stop_preserves_closed_loss_guard(self):
        self.assertIn("closedToday <= -(Account.Balance * MaxDailyLossPercent / 100.0)", SCALP)

    def test_scalp_uses_utc_for_daily_reset_and_trades(self):
        self.assertIn("Server.TimeInUtc.Date", SCALP)
        self.assertNotIn("trade.ClosingTime.Date == Server.Time.Date", SCALP)

    def test_both_bots_limit_shared_mojtrade_positions(self):
        for source in (SCALP, OMEGA):
            with self.subTest(bot="scalp" if source == SCALP else "omega"):
                self.assertIn("private const int SharedPositionCap = 3;", source)
                self.assertIn("SharedMojTradePositionCount() >= SharedPositionCap", source)
                self.assertIn("private int SharedMojTradePositionCount()", source)

    def test_scalp_parameter_cannot_expand_past_three(self):
        self.assertIn("Max Open Trades / Symbol\", DefaultValue = 3, MinValue = 1, MaxValue = 3", SCALP)

    def test_omega_daily_loss_parameter_has_upper_bound(self):
        self.assertIn("Daily Loss Stop %\", DefaultValue = 2.0, MinValue = 0.1, MaxValue = 10", OMEGA)

    def test_finite_market_feed_checks(self):
        for source in (SCALP, OMEGA):
            with self.subTest(bot="scalp" if source == SCALP else "omega"):
                self.assertIn("!IsFinitePositive(Symbol.PipSize)", source)
                self.assertIn("!IsFinitePositive(volume)", source)

    def test_broker_side_sl_tp_must_exist_after_order(self):
        for source in (SCALP, OMEGA):
            with self.subTest(bot="scalp" if source == SCALP else "omega"):
                self.assertIn("result.Position == null || !result.Position.StopLoss.HasValue", source)
                self.assertIn("!result.Position.TakeProfit.HasValue", source)
                self.assertIn("ClosePosition(result.Position)", source)

    def test_scalp_halts_after_unprotected_result(self):
        boundary = SCALP.split("private void TryOpen(", 1)[1].split(
            "private bool RiskStopActive()", 1)[0]
        unprotected = boundary.split("if (result.Position == null ||", 1)[1]
        self.assertIn("_halted = true;", unprotected)
        self.assertIn("Stop();", unprotected)
        self.assertIn("_halted || Account.IsLive || RiskStopActive()", boundary)

    def test_omega_demo_stays_opt_in(self):
        self.assertIn('[Parameter("Enable Demo Trading", DefaultValue = false)]', OMEGA)

    def test_both_keep_access_rights_none(self):
        for source in (SCALP, OMEGA):
            self.assertIn("AccessRights = AccessRights.None", source)


if __name__ == "__main__":
    unittest.main()
