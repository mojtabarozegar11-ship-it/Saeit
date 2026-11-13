using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using cAlgo.API;

// ONE-BOT, read-only input collector for the existing Mojtaba.bot.ai planner.
// Emits a bounded machine-readable private LOG. Not broker-authenticated,
// not signed, never transmits data, never starts/modifies/closes an order.
// Log lines may contain account equity: keep cTrader logs PRIVATE.
namespace MojTrade.OmegaX
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class MojTradeGoldSnapshotAuditBot : Robot
    {
        private const string Marker = "MOJTABA_GOLD_H1_CAPTURE_V1";
        private const int BarCount = 80;
        private const int MaxHistoryDeals = 5000;
        private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        [Parameter("Non-sensitive Demo Alias", DefaultValue = "LITE_DEMO_1")]
        public string DemoAlias { get; set; } = "LITE_DEMO_1";

        private static bool Valid(double v)
        {
            return !double.IsNaN(v) && !double.IsInfinity(v);
        }

        private static string Num(double v)
        {
            return v.ToString("R", Inv);
        }

        private static string Utc(DateTime v)
        {
            return v.ToString("yyyy-MM-ddTHH:mm:ss.fffffff", Inv) + "Z";
        }

        private static void Require(bool ok, string code)
        {
            if (!ok)
                throw new InvalidOperationException(code);
        }

        protected override void OnStart()
        {
            try
            {
                Capture();
            }
            catch (InvalidOperationException ex)
            {
                // Only fixed, non-sensitive error codes can escape to logs.
                Print(Marker + "|BLOCKED|reason=" + ex.Message);
            }
            catch (Exception)
            {
                Print(Marker + "|BLOCKED|reason=broker_snapshot_unavailable");
            }
            finally
            {
                Stop();
            }
        }

        private void Capture()
        {
            Require(!Account.IsLive, "live_account_forbidden");
            Require(SymbolName == "XAUUSD", "xauusd_chart_required");
            Require(Regex.IsMatch(DemoAlias ?? "", "^[A-Za-z0-9_-]{3,40}$"),
                "alias_invalid");
            Require(Account.Asset != null && Account.Asset.Name == "USD",
                "usd_demo_account_required");
            var now = TimeInUtc;
            Require(now != DateTime.MinValue, "server_utc_clock_unavailable");
            Require(Valid(Symbol.Bid) && Valid(Symbol.Ask) &&
                    Valid(Symbol.PipSize) && Valid(Symbol.TickSize) &&
                    Symbol.Bid > 0 && Symbol.Ask > Symbol.Bid &&
                    Symbol.PipSize > 0 && Symbol.TickSize > 0,
                "quote_invalid");
            Require(Valid(Account.Equity) && Account.Equity > 0 &&
                    Valid(Account.FreeMargin) && Account.FreeMargin >= 0,
                "account_risk_invalid");
            Require(History.Count <= MaxHistoryDeals, "history_not_bounded");

            // Account-wide realized P&L and open stop risk are best-effort.
            // Broker history completeness cannot be independently attested.
            var pnl = 0.0;
            var seenDeals = new HashSet<long>();
            var startUtc = now.Date;
            foreach (var deal in History)
            {
                Require(deal.ClosingDealId > 0 &&
                        seenDeals.Add(deal.ClosingDealId) &&
                        Valid(deal.NetProfit),
                    "history_invalid_or_duplicated");
                if (deal.ClosingTime >= startUtc && deal.ClosingTime <= now)
                    pnl += deal.NetProfit;
            }
            Require(Valid(pnl), "daily_pnl_invalid");

            var openRisk = 0.0;
            foreach (var position in Positions)
            {
                Require(position.StopLoss.HasValue &&
                        position.TakeProfit.HasValue &&
                        Valid(position.EntryPrice) && position.EntryPrice > 0 &&
                        Valid(position.StopLoss.Value) &&
                        Valid(position.VolumeInUnits) && position.VolumeInUnits > 0 &&
                        position.Symbol != null && Valid(position.Symbol.PipSize) &&
                        position.Symbol.PipSize > 0, "unprotected_or_invalid_position");
                var riskDistance = position.TradeType == TradeType.Buy
                    ? position.EntryPrice - position.StopLoss.Value
                    : position.StopLoss.Value - position.EntryPrice;
                Require(Valid(riskDistance), "stop_risk_invalid");
                if (riskDistance > 0)
                {
                    var risk = position.Symbol.AmountRisked(
                        position.VolumeInUnits, riskDistance / position.Symbol.PipSize);
                    Require(Valid(risk) && risk >= 0, "stop_risk_unavailable");
                    openRisk += risk;
                }
            }
            Require(Valid(openRisk) && openRisk >= 0,
                "portfolio_risk_invalid");

            var bars = MarketData.GetBars(TimeFrame.Hour, SymbolName);
            Require(bars != null && bars.Count >= BarCount,
                "insufficient_loaded_h1_bars");
            var last = bars.Count - 1;
            // Current unfinished H1 candle may be included in GetBars.
            if (bars.OpenTimes[last].AddHours(1) > now)
                last--;
            Require(last >= BarCount - 1, "insufficient_closed_h1_bars");
            Require(bars.OpenTimes[last].AddHours(1) <= now &&
                    now - bars.OpenTimes[last].AddHours(1) <= TimeSpan.FromHours(2),
                "stale_h1_candle");
            var first = last - BarCount + 1;
            var rows = new List<string>(BarCount + 1);

            var session = Guid.NewGuid().ToString("N");
            // The initial record contains no broker account number or cTID.
            var header = string.Join("|", new[] {
                Marker, "START", session, DemoAlias, Utc(now),
                Num(Symbol.Bid), Num(Symbol.Ask), Num(Symbol.PipSize),
                Num(Symbol.TickSize), Num(Account.Equity),
                Num(Account.FreeMargin), Num(pnl), Num(openRisk),
                Positions.Count.ToString(Inv), PendingOrders.Count.ToString(Inv),
                BarCount.ToString(Inv)
            });
            rows.Add(header);
            var previous = DateTime.MinValue;
            for (var i = first; i <= last; i++)
            {
                var stamp = bars.OpenTimes[i];
                Require(stamp.Minute == 0 && stamp.Second == 0 &&
                        stamp.Millisecond == 0 &&
                        (previous == DateTime.MinValue ||
                         stamp - previous == TimeSpan.FromHours(1)),
                    "h1_history_gap_or_unaligned");
                var o = bars.OpenPrices[i];
                var h = bars.HighPrices[i];
                var l = bars.LowPrices[i];
                var c = bars.ClosePrices[i];
                Require(Valid(o) && Valid(h) && Valid(l) && Valid(c) &&
                        l > 0 && l <= o && o <= h && l <= c && c <= h,
                    "h1_ohlc_invalid");
                rows.Add(string.Join("|", new[] {
                    Marker, "BAR", session, Utc(stamp),
                    Num(o), Num(h), Num(l), Num(c)
                }));
                previous = stamp;
            }
            var canonical = string.Join("\n", rows);
            string hash;
            using (var sha = SHA256.Create())
            {
                hash = BitConverter.ToString(
                    sha.ComputeHash(Encoding.UTF8.GetBytes(canonical))
                ).Replace("-", "").ToLowerInvariant();
            }
            // No partially emitted snapshot is accepted without exact END.
            foreach (var row in rows)
                Print(row);
            Print(string.Join("|", new[] {
                Marker, "END", session, BarCount.ToString(Inv), hash
            }));
        }
    }
}
