using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.RegularExpressions;
using cAlgo.API;

// One-shot, read-only cTrader demo history auditor.
// Does not open, close, modify, copy or transmit any orders or positions.
// Print statements are machine-readable but NOT independent broker attestation.
namespace MojTrade.OmegaX
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class MojTradeDemoHistoryAuditBot : Robot
    {
        private const string TradeLabel = "MojTrade-OMEGA-X-DEMO";
        private const string Prefix = "MOJTRADE_AUDIT_V1";
        private static readonly CultureInfo Numeric = CultureInfo.InvariantCulture;

        [Parameter("Non-sensitive Demo Alias", DefaultValue = "LITE_DEMO_1")]
        public string DemoAlias { get; set; }

        [Parameter("Maximum Complete Deal Rows", DefaultValue = 2000, MinValue = 1, MaxValue = 20000)]
        public int MaxCompleteDeals { get; set; }

        protected override void OnStart()
        {
            // This audit task is never permitted on a funded/live account.
            if (Account.IsLive)
            {
                Print(Prefix + "|BLOCKED|reason=live_account");
                Stop();
                return;
            }
            if (string.IsNullOrEmpty(DemoAlias) ||
                !Regex.IsMatch(DemoAlias, "^[A-Za-z0-9_-]{3,40}$"))
            {
                Print(Prefix + "|BLOCKED|reason=invalid_demo_alias");
                Stop();
                return;
            }

            var history = History.FindAll(TradeLabel, SymbolName)
                .OrderBy(t => t.ClosingTime).ThenBy(t => t.ClosingDealId).ToArray();
            if (history.Length > MaxCompleteDeals)
            {
                Print(Prefix + "|BLOCKED|reason=history_exceeds_configured_complete_limit");
                Stop();
                return;
            }

            // No broker or account number is exposed through the log.
            var currency = Account.Asset.Name;
            if (string.IsNullOrEmpty(currency) ||
                !Regex.IsMatch(currency, "^[A-Za-z]{3,10}$") ||
                !Regex.IsMatch(SymbolName, "^[A-Za-z0-9._-]{3,40}$"))
            {
                Print(Prefix + "|BLOCKED|reason=unsafe_currency_or_symbol");
                Stop();
                return;
            }

            var seen = new HashSet<int>();
            foreach (var trade in history)
            {
                if (trade.ClosingDealId <= 0 || trade.PositionId <= 0 ||
                    !seen.Add(trade.ClosingDealId) ||
                    trade.SymbolName != SymbolName || trade.Label != TradeLabel ||
                    NotFinite(trade.NetProfit) || NotFinite(trade.GrossProfit) ||
                    NotFinite(trade.Commissions) || NotFinite(trade.Swap) ||
                    NotFinite(trade.Balance) || NotFinite(trade.Quantity) ||
                    trade.Quantity <= 0)
                {
                    Print(Prefix + "|BLOCKED|reason=invalid_or_duplicate_history_deal");
                    Stop();
                    return;
                }
            }

            var session = Guid.NewGuid().ToString("N");
            Print(Prefix + "|START|session=" + session +
                  "|alias=" + DemoAlias + "|currency=" + currency +
                  "|symbol=" + SymbolName + "|mode=demo|count=" +
                  history.Length.ToString(Numeric));
            var gross = 0.0;
            var net = 0.0;
            var commission = 0.0;
            var swap = 0.0;
            var wins = 0;
            foreach (var trade in history)
            {
                gross += trade.GrossProfit;
                net += trade.NetProfit;
                commission += trade.Commissions;
                swap += trade.Swap;
                if (trade.NetProfit > 0) wins++;
                // ClosingDealId distinguishes partial-close deals. The
                // broker's own NetProfit already includes fees and swaps.
                Print(Prefix + "|DEAL|session=" + session +
                      "|deal_id=" + trade.ClosingDealId.ToString(Numeric) +
                      "|position_id=" + trade.PositionId.ToString(Numeric) +
                      "|closed_utc=" + trade.ClosingTime.ToString("yyyy-MM-ddTHH:mm:ss.fffffff", Numeric) + "Z" +
                      "|side=" + trade.TradeType.ToString().ToLowerInvariant() +
                      "|lots=" + trade.Quantity.ToString("R", Numeric) +
                      "|gross=" + trade.GrossProfit.ToString("R", Numeric) +
                      "|commission=" + trade.Commissions.ToString("R", Numeric) +
                      "|swap=" + trade.Swap.ToString("R", Numeric) +
                      "|net=" + trade.NetProfit.ToString("R", Numeric) +
                      "|balance_after=" + trade.Balance.ToString("R", Numeric));
            }
            // This END record attests only to consistency of the visible
            // cTrader API history, not broker/source authenticity or real income.
            Print(Prefix + "|END|session=" + session +
                  "|count=" + history.Length.ToString(Numeric) +
                  "|wins=" + wins.ToString(Numeric) +
                  "|gross=" + gross.ToString("R", Numeric) +
                  "|commission=" + commission.ToString("R", Numeric) +
                  "|swap=" + swap.ToString("R", Numeric) +
                  "|net=" + net.ToString("R", Numeric) +
                  "|demo_only=true|external_broker_reconciliation=false");
            Stop();
        }

        private static bool NotFinite(double value)
        {
            return double.IsNaN(value) || double.IsInfinity(value);
        }
    }
}
