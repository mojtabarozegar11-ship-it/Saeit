"""Static client contract checks. Not a substitute for a cTrader C# build."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCALP = (ROOT / "trading/MojTradeDemoBot.cs").read_text(encoding="utf-8")
OMEGA = (ROOT / "trading/MojTradeOmegaXDemoBot.cs").read_text(encoding="utf-8")


class C08ClientContractTests(unittest.TestCase):
    def test_both_demo_switches_default_off(self):
        for bot in (SCALP, OMEGA):
            self.assertIn('[Parameter("Enable Coordinated Demo Trading", DefaultValue = false)]', bot)

    def test_both_require_https_and_no_uri_credentials(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("endpoint.Scheme == Uri.UriSchemeHttps", bot)
            self.assertIn("string.IsNullOrEmpty(endpoint.UserInfo)", bot)

    def test_both_require_long_token(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("CoordinatorToken.Length >= 32", bot)
            self.assertIn('request.Headers.Add("Authorization", "Bearer " + CoordinatorToken)', bot)

    def test_both_use_short_network_timeout(self):
        for bot in (SCALP, OMEGA):
            self.assertGreaterEqual(bot.count("Timeout = TimeSpan.FromSeconds(3)"), 2)

    def test_order_requires_reservation(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("var reservationId = ReserveCoordinatedSlot(", bot)
            self.assertIn("if (reservationId == null)", bot)
            self.assertLess(bot.index("var reservationId = ReserveCoordinatedSlot("),
                            bot.index("var result = ExecuteMarketOrder("))

    def test_order_result_always_settled_before_success_path(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("SettleCoordinatedSlot(reservationId, result.IsSuccessful, brokerPositionId)", bot)
            self.assertIn("Adapter halted.", bot)

    def test_settlement_retries_same_receipt_but_never_unconfirmed_success(self):
        for bot in (SCALP, OMEGA):
            method = bot.split("private bool SettleCoordinatedSlot(", 1)[1]
            method = method.split("\n        private ", 1)[0]
            self.assertIn("attempt < 2", method)
            self.assertIn('"&request_id=" + requestId', method)
            self.assertIn('"&broker_position_id=" + brokerPositionId', method)
            self.assertIn('response.Body == "SETTLED"', method)
            self.assertIn("response.StatusCode < 500", method)
            self.assertIn("return false; // Never treat unconfirmed", method)

    def test_successful_order_reports_broker_position_id(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("result.Position.Id.ToString(CultureInfo.InvariantCulture)", bot)
            self.assertIn("SettleCoordinatedSlot(reservationId, result.IsSuccessful, brokerPositionId)", bot)
            self.assertIn('filled ? "&broker_position_id=" + brokerPositionId : ""', bot)

    def test_both_send_broker_observed_equity_and_position_count(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("Account.Number.ToString(invariant)", bot)
            self.assertIn('Account.Equity.ToString("R", invariant)', bot)
            self.assertIn("SharedMojTradePositionCount().ToString(invariant)", bot)

    def test_both_preserve_live_account_lock(self):
        for bot in (SCALP, OMEGA):
            self.assertGreaterEqual(bot.count("Account.IsLive"), 4)

    def test_old_uncoordinated_demo_entry_is_blocked(self):
        self.assertIn("!EnableCoordinatedDemoTrading || !CoordinatorConfigured()", SCALP)
        self.assertIn("!EnableCoordinatedDemoTrading ||", OMEGA)
        self.assertIn("DefaultValue = false", OMEGA)

    def test_http_failure_is_fail_closed(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("if (!response.IsSuccessful || response.StatusCode != 200", bot)
            self.assertIn('response.Body != "GRANTED|" + requestId', bot)
            self.assertIn("return null;", bot)

    def test_both_use_periodic_timer_for_equity_observation(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("Timer.Start(60);", bot)
            self.assertIn("protected override void OnTimer()", bot)
            self.assertIn("ObserveCoordinatedRisk(", bot)

    def test_observation_is_authenticated_and_has_short_timeout(self):
        for bot in (SCALP, OMEGA):
            self.assertIn('CoordinatorUrl.TrimEnd(\'/\') + "/v1/observe"', bot)
            self.assertIn('response.Body == "OBSERVED"', bot)
            self.assertGreaterEqual(bot.count('request.Headers.Add("Authorization", "Bearer " + CoordinatorToken)'), 3)
            self.assertGreaterEqual(bot.count("Timeout = TimeSpan.FromSeconds(3)"), 3)

    def test_observation_failure_latches_new_order_stop(self):
        for bot in (SCALP, OMEGA):
            self.assertIn("_lastObservationUtc", bot)
            self.assertIn("(now - _lastObservationUtc).TotalSeconds < 60", bot)
            self.assertIn("_halted = true;", bot)
            self.assertIn("coordinator risk observation failed; new orders halted.", bot)

    def test_observation_not_bound_to_signal_or_empty_book(self):
        for bot in (SCALP, OMEGA):
            before_bar = bot.split("protected override void OnBarClosed()", 1)[1]
            self.assertLess(before_bar.index("ObserveCoordinatedRisk("),
                            before_bar.index("SharedMojTradePositionCount()"))
            self.assertIn("&open_positions=", bot)

    def test_both_observe_account_wide_realized_profit(self):
        # Losses from manual trades or other symbols must count toward the
        # daily loss gate. Static tests cannot replace broker reconciliation.
        for bot in (SCALP, OMEGA):
            method = bot.split("private double TodayAccountRealizedProfit()", 1)[1]
            method = method.split("\n        private ", 1)[0]
            self.assertIn("foreach (var trade in History)", method)
            self.assertIn("trade.ClosingTime.Date != Server.TimeInUtc.Date", method)
            self.assertIn("total += trade.NetProfit;", method)
            self.assertIn("return IsFinite(total) ? total : double.NaN;", method)
            self.assertNotIn("History.FindAll(", method)
            self.assertNotIn("trade.Label", method)
            self.assertNotIn("trade.SymbolName", method)
            self.assertIn("ReserveCoordinatedSlot(TodayAccountRealizedProfit())", bot)
            self.assertIn("ObserveCoordinatedRisk(TodayAccountRealizedProfit())", bot)


if __name__ == "__main__":
    unittest.main()
