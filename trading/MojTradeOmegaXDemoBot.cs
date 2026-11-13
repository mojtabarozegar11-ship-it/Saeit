using System;
using System.Globalization;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace MojTrade.OmegaX
{
    // cTrader execution adapter for MojTrade OMEGA X.
    // Deliberately fail-closed: live accounts are always rejected.
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class MojTradeOmegaXDemoBot : Robot
    {
        private const string Label = "MojTrade-OMEGA-X-DEMO";

        [Parameter("Fast EMA", DefaultValue = 8, MinValue = 2)]
        public int FastEmaPeriod { get; set; }

        [Parameter("Slow EMA", DefaultValue = 34, MinValue = 3)]
        public int SlowEmaPeriod { get; set; }

        [Parameter("RSI Period", DefaultValue = 14, MinValue = 2)]
        public int RsiPeriod { get; set; }

        [Parameter("ATR Period", DefaultValue = 14, MinValue = 2)]
        public int AtrPeriod { get; set; }

        [Parameter("ATR Stop Multiplier", DefaultValue = 2.0, MinValue = 0.5)]
        public double AtrStopMultiplier { get; set; }

        [Parameter("Reward/Risk", DefaultValue = 1.8, MinValue = 0.5)]
        public double RewardRisk { get; set; }

        [Parameter("Risk %", DefaultValue = 0.25, MinValue = 0.01, MaxValue = 1.0)]
        public double RiskPercent { get; set; }

        [Parameter("Max Spread (pips)", DefaultValue = 25.0, MinValue = 0.1)]
        public double MaxSpreadPips { get; set; }

        [Parameter("Max Positions", DefaultValue = 3, MinValue = 1, MaxValue = 3)]
        public int MaxPositions { get; set; }

        // Upper bound includes ALL account positions, not only Omega X
        // positions; risk is denominated in the cTrader account currency.
        [Parameter("Aggregate Stop Risk %", DefaultValue = 1.0, MinValue = 0.25, MaxValue = 1.0)]
        public double AggregateStopRiskPercent { get; set; }

        [Parameter("Daily Loss Stop %", DefaultValue = 2.0, MinValue = 0.1)]
        public double DailyLossStopPercent { get; set; }

        [Parameter("Consecutive Loss Stop", DefaultValue = 5, MinValue = 1)]
        public int ConsecutiveLossStop { get; set; }

        [Parameter("Enable Demo Trading", DefaultValue = false)]
        public bool EnableDemoTrading { get; set; }

        // Indicators are initialized on a validated OnStart path.
        private ExponentialMovingAverage _fastEma = null!;
        private ExponentialMovingAverage _slowEma = null!;
        private RelativeStrengthIndex _rsi = null!;
        private AverageTrueRange _atr = null!;
        private double _dayStartEquity;
        private int _consecutiveLosses;
        private string _lastAttemptedSignalKey = "";
        private bool _orderReconciliationHold;

        protected override void OnStart()
        {
            if (Account.IsLive)
            {
                Print("OMEGA X STOPPED: live accounts are permanently locked.");
                Stop();
                return;
            }

            if (!EnableDemoTrading)
            {
                Print("OMEGA X is in observation mode. EnableDemoTrading=false.");
            }

            if (FastEmaPeriod >= SlowEmaPeriod)
            {
                Print("OMEGA X STOPPED: Fast EMA must be lower than Slow EMA.");
                Stop();
                return;
            }

            _fastEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, FastEmaPeriod);
            _slowEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, SlowEmaPeriod);
            _rsi = Indicators.RelativeStrengthIndex(Bars.ClosePrices, RsiPeriod);
            _atr = Indicators.AverageTrueRange(AtrPeriod, MovingAverageType.Exponential);
            // Reconstruct prior same-day risk from broker history. Starting
            // the cBot must NOT erase a loss streak or refresh the loss
            // baseline halfway through the UTC trading day.
            if (DailyLossReached())
                Print("OMEGA X HOLD: historical account risk limit or reconciliation gate.");
            Positions.Closed += OnPositionClosed;
            Print("OMEGA X DEMO adapter started: {0} {1}", SymbolName, TimeFrame);
        }

        protected override void OnBarClosed()
        {
            // The breakout lookback touches index-20. Low configured EMA
            // periods must not allow a negative candle index at runtime.
            var minimumBars = Math.Max(
                Math.Max(SlowEmaPeriod + 5, 22),
                Math.Max(AtrPeriod + 2, RsiPeriod + 2));
            if (!EnableDemoTrading || Account.IsLive || Bars.Count < minimumBars ||
                _orderReconciliationHold)
                return;
            if (DailyLossReached() || _consecutiveLosses >= ConsecutiveLossStop)
                return;
            if (CurrentSpreadPips() > MaxSpreadPips)
                return;

            // Account-wide bound across symbols, not three positions PER
            // running chart. Concurrency across instances still needs broker
            // reconciliation before any production deployment.
            var positions = Positions.FindAll(Label);
            if (positions.Length >= MaxPositions || Positions.Count >= MaxPositions)
                return;
            // Never add market risk while a prior demo position lacks a
            // broker-confirmed protective stop or target.
            foreach (var position in positions)
            {
                if (!position.StopLoss.HasValue || !position.TakeProfit.HasValue)
                {
                    Print("OMEGA X HOLD: existing demo position is unprotected.");
                    return;
                }
            }

            var index = Bars.Count - 1;
            var atrPrice = _atr.Result[index];
            if (atrPrice <= 0 || double.IsNaN(atrPrice) || double.IsInfinity(atrPrice))
                return;

            var buyVotes = 0;
            var sellVotes = 0;
            var fast = _fastEma.Result[index];
            var slow = _slowEma.Result[index];
            var previousFast = _fastEma.Result[index - 1];
            var previousSlow = _slowEma.Result[index - 1];
            var rsi = _rsi.Result[index];
            if (!IsFinite(fast) || !IsFinite(slow) ||
                !IsFinite(previousFast) || !IsFinite(previousSlow) ||
                !IsFinite(rsi) || rsi < 0 || rsi > 100)
                return;

            if (previousFast <= previousSlow && fast > slow && rsi < 75)
                buyVotes++;
            if (previousFast >= previousSlow && fast < slow && rsi > 25)
                sellVotes++;

            // cTrader DataSeries is indexed but does not implement
            // IEnumerable<double>: LINQ Skip/Take/Max/Min cannot compile here.
            // Examine only bars strictly BEFORE the closed signal bar.
            var rangeHigh = double.NegativeInfinity;
            var rangeLow = double.PositiveInfinity;
            for (var candle = index - 20; candle < index; candle++)
            {
                rangeHigh = Math.Max(rangeHigh, Bars.HighPrices[candle]);
                rangeLow = Math.Min(rangeLow, Bars.LowPrices[candle]);
            }
            if (double.IsNaN(rangeHigh) || double.IsNaN(rangeLow) ||
                double.IsInfinity(rangeHigh) || double.IsInfinity(rangeLow))
                return;
            var close = Bars.ClosePrices[index];
            if (close > rangeHigh && fast > slow)
                buyVotes++;
            if (close < rangeLow && fast < slow)
                sellVotes++;

            if (buyVotes >= 2 && sellVotes == 0)
                SubmitDemoOrder(TradeType.Buy, atrPrice);
            else if (sellVotes >= 2 && buyVotes == 0)
                SubmitDemoOrder(TradeType.Sell, atrPrice);
        }

        protected override void OnTick()
        {
            // Observation mode must also block modifications of positions
            // left from a previous demo run.
            if (Account.IsLive || !EnableDemoTrading)
                return;

            foreach (var position in Positions.FindAll(Label, SymbolName))
            {
                // No improvised fallback stop for a position without verified
                // protection; ask for explicit broker reconciliation instead.
                if (!position.StopLoss.HasValue || !position.TakeProfit.HasValue ||
                    !IsFinite(Symbol.PipSize) || Symbol.PipSize <= 0)
                    continue;
                var trigger = Math.Abs(position.EntryPrice - position.StopLoss.Value);
                var current = position.TradeType == TradeType.Buy ? Symbol.Bid : Symbol.Ask;
                var favourable = position.TradeType == TradeType.Buy
                    ? current - position.EntryPrice
                    : position.EntryPrice - current;

                if (favourable >= trigger && (!position.StopLoss.HasValue ||
                    (position.TradeType == TradeType.Buy && position.StopLoss.Value < position.EntryPrice) ||
                    (position.TradeType == TradeType.Sell && position.StopLoss.Value > position.EntryPrice)))
                {
                    var breakEven = position.TradeType == TradeType.Buy
                        ? position.EntryPrice + Symbol.PipSize
                        : position.EntryPrice - Symbol.PipSize;
                    // Absolute prices, never relative pips. The legacy
                    // three-argument overload is obsolete.
                    var modified = ModifyPosition(
                        position, breakEven, position.TakeProfit, ProtectionType.Absolute);
                    if (!modified.IsSuccessful)
                        Print("OMEGA X DEMO protection update rejected: {0}", modified.Error);
                }
            }
        }

        private void SubmitDemoOrder(TradeType tradeType, double atrPrice)
        {
            if (Account.IsLive || !EnableDemoTrading || _orderReconciliationHold ||
                !IsFinite(Symbol.PipSize) || Symbol.PipSize <= 0 ||
                DailyLossReached() || _consecutiveLosses >= ConsecutiveLossStop ||
                Positions.FindAll(Label).Length >= MaxPositions ||
                Positions.Count >= MaxPositions ||
                CurrentSpreadPips() > MaxSpreadPips)
                return;
            var stopPips = Math.Max(atrPrice * AtrStopMultiplier / Symbol.PipSize, 1.0);
            if (double.IsNaN(stopPips) || double.IsInfinity(stopPips))
                return;
            var takePips = stopPips * RewardRisk;
            var volume = Symbol.VolumeForProportionalRisk(ProportionalAmountType.Equity,
                                                           RiskPercent, stopPips);
            if (!IsFinite(volume) || volume <= 0)
                return;
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            if (!IsFinite(volume) ||
                volume < Symbol.VolumeInUnitsMin || volume > Symbol.VolumeInUnitsMax)
                return;
            if (!PortfolioRiskAllows(tradeType, volume, stopPips))
                return;

            // A closed-bar identity is stored in the broker-side comment and
            // checked against positions AND closed trades. It reduces
            // duplicate submissions after a restart. It is not an atomic
            // distributed lock across multiple simultaneous cBot instances.
            var closedBarTime = Bars.OpenTimes[Bars.Count - 1];
            var signalKey = "MOJ:" + SymbolName + ":" +
                TimeFrame.ToString() + ":" +
                closedBarTime.ToString("yyyyMMddHHmm", CultureInfo.InvariantCulture);
            if (_lastAttemptedSignalKey == signalKey)
                return;
            foreach (var position in Positions.FindAll(Label))
                if (position.Comment == signalKey)
                    return;
            foreach (var closedTrade in History.FindAll(Label))
                if (closedTrade.Comment == signalKey)
                    return;
            // Reserve before dispatch. An ambiguous broker error must NOT
            // trigger an automatic duplicate on the same closed bar.
            _lastAttemptedSignalKey = signalKey;
            var result = ExecuteMarketOrder(
                tradeType, SymbolName, volume, Label, stopPips, takePips, signalKey);
            if (!result.IsSuccessful)
            {
                _orderReconciliationHold = true;
                Print("OMEGA X HOLD: demo order rejected or ambiguous, broker reconciliation required: {0}",
                      result.Error);
                return;
            }
            var opened = result.Position;
            if (opened == null)
            {
                _orderReconciliationHold = true;
                Print("OMEGA X HOLD: successful broker response has no position receipt.");
                return;
            }
            if (!opened.StopLoss.HasValue || !opened.TakeProfit.HasValue)
            {
                _orderReconciliationHold = true;
                // Only demo positions pass OnStart / SubmitDemoOrder gates.
                // Reconcile the outcome; do not claim the close succeeded.
                var closed = ClosePosition(opened);
                Print("OMEGA X HOLD: missing broker protection; emergency demo close acknowledged={0} error={1}",
                      closed.IsSuccessful, closed.Error);
                return;
            }
            Print("OMEGA X DEMO reconciled order: position={0} side={1} volume={2}",
                  opened.Id, tradeType, volume);
        }

        private bool PortfolioRiskAllows(TradeType side, double volume, double stopPips)
        {
            // This is a conservative *pre-order* admission gate, not an
            // atomic account lock. The risk check must include manually
            // opened trades and all other symbols/labels on the account.
            // The official Symbol.AmountRisked() estimates values in the
            // account currency; realized risk can exceed stops from gaps.
            try
            {
                // A pending order on any symbol/label can fill after this
                // gate and silently breach the shared stop-risk limit.
                // Until an account-level pending-order reservation ledger
                // is broker-reconciled, refuse additional market exposure.
                if (PendingOrders.Count != 0)
                    return false;
                var equity = Account.Equity;
                if (!IsFinite(equity) || equity <= 0 ||
                    !IsFinite(Account.FreeMargin) || Account.FreeMargin <= 0 ||
                    !IsFinite(stopPips) || stopPips <= 0 ||
                    !IsFinite(volume) || volume <= 0)
                    return false;

                var intendedRisk = Symbol.AmountRisked(volume, stopPips);
                var requiredMargin = Symbol.GetEstimatedMargin(side, volume);
                if (!IsFinite(intendedRisk) || intendedRisk <= 0 ||
                    !IsFinite(requiredMargin) || requiredMargin < 0 ||
                    requiredMargin > Account.FreeMargin)
                    return false;

                var portfolioRisk = intendedRisk;
                var budget = equity * AggregateStopRiskPercent / 100.0;
                if (!IsFinite(budget) || budget <= 0 || portfolioRisk > budget)
                    return false;

                foreach (var current in Positions)
                {
                    // A position without a broker-confirmed stop or target
                    // blocks new portfolio exposure, whatever its label.
                    if (!current.StopLoss.HasValue || !current.TakeProfit.HasValue)
                        return false;
                    var instrument = current.Symbol;
                    if (instrument == null || !IsFinite(instrument.PipSize) ||
                        instrument.PipSize <= 0 || !IsFinite(current.EntryPrice) ||
                        !IsFinite(current.StopLoss.Value) ||
                        !IsFinite(current.VolumeInUnits) || current.VolumeInUnits <= 0)
                        return false;
                    var adverseDistance = current.TradeType == TradeType.Buy
                        ? current.EntryPrice - current.StopLoss.Value
                        : current.StopLoss.Value - current.EntryPrice;
                    if (!IsFinite(adverseDistance))
                        return false;
                    if (adverseDistance <= 0)
                        continue; // A stop already beyond entry locks profit.

                    var existingRisk = instrument.AmountRisked(
                        current.VolumeInUnits, adverseDistance / instrument.PipSize);
                    if (!IsFinite(existingRisk) || existingRisk < 0)
                        return false;
                    portfolioRisk += existingRisk;
                    if (!IsFinite(portfolioRisk) || portfolioRisk > budget)
                        return false;
                }
                return true;
            }
            catch (Exception)
            {
                // Unknown broker/account state must never open a new trade.
                Print("OMEGA X HOLD: portfolio risk or margin cannot be verified.");
                return false;
            }
        }

        private double CurrentSpreadPips()
        {
            if (Symbol.PipSize <= 0 || double.IsNaN(Symbol.PipSize))
                return double.PositiveInfinity;
            var spread = (Symbol.Ask - Symbol.Bid) / Symbol.PipSize;
            return spread >= 0 && !double.IsNaN(spread) && !double.IsInfinity(spread)
                ? spread : double.PositiveInfinity;
        }

        private bool DailyLossReached()
        {
            // A local in-memory baseline resets on a cBot restart and lets
            // previously realized losses bypass the daily stop. Rebuild it
            // from the broker's account-wide closed-trade ledger on EACH
            // decision; this also observes other cBots' closed losses.
            // Deposits/withdrawals and incomplete provider history remain
            // external reconciliation blockers before any production use.
            try
            {
                var today = Server.Time.Date;
                var accountNetToday = 0.0;
                foreach (var trade in History)
                {
                    if (trade.ClosingTime.Date != today)
                        continue;
                    if (!IsFinite(trade.NetProfit))
                        return true;
                    accountNetToday += trade.NetProfit;
                    if (!IsFinite(accountNetToday))
                        return true;
                }
                var owned = History.FindAll(Label);
                Array.Sort(owned, (first, second) =>
                    first.ClosingTime.CompareTo(second.ClosingTime));
                var losses = 0;
                foreach (var trade in owned)
                {
                    if (trade.ClosingTime.Date != today)
                        continue;
                    if (!IsFinite(trade.NetProfit))
                        return true;
                    if (trade.NetProfit < 0)
                        losses++;
                    else if (trade.NetProfit > 0)
                        losses = 0;
                }
                _consecutiveLosses = losses;
                _dayStartEquity = Account.Balance - accountNetToday;
                if (!IsFinite(_dayStartEquity) || _dayStartEquity <= 0 ||
                    !IsFinite(Account.Equity) || Account.Equity <= 0)
                    return true;
                return Account.Equity <=
                    _dayStartEquity * (1.0 - DailyLossStopPercent / 100.0);
            }
            catch (Exception)
            {
                Print("OMEGA X HOLD: broker history was not reconciled.");
                return true;
            }
        }

        private static bool IsFinite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            if (args.Position.Label != Label)
                return;
            // The next decision reads the account-wide history rather than
            // trusting a per-instance event counter or per-symbol subset.
            Print("OMEGA X demo position closed: position={0}; history reconciliation required.",
                  args.Position.Id);
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
            Print("OMEGA X stopped. Existing positions remain broker-managed.");
        }
    }
}
