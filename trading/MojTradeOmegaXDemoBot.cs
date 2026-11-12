using System;
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
        private double _sessionStartEquity;
        private int _consecutiveLosses;

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
            _sessionStartEquity = Account.Equity;
            Positions.Closed += OnPositionClosed;
            Print("OMEGA X DEMO adapter started: {0} {1}", SymbolName, TimeFrame);
        }

        protected override void OnBarClosed()
        {
            if (!EnableDemoTrading || Account.IsLive || Bars.Count < SlowEmaPeriod + 5)
                return;
            if (DailyLossReached() || _consecutiveLosses >= ConsecutiveLossStop)
                return;
            if (CurrentSpreadPips() > MaxSpreadPips)
                return;

            var positions = Positions.FindAll(Label, SymbolName);
            if (positions.Length >= MaxPositions)
                return;

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
                var trigger = position.StopLoss.HasValue
                    ? Math.Abs(position.EntryPrice - position.StopLoss.Value)
                    : Symbol.PipSize * 10;
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
            if (Account.IsLive || !EnableDemoTrading || Symbol.PipSize <= 0)
                return;
            var stopPips = Math.Max(atrPrice * AtrStopMultiplier / Symbol.PipSize, 1.0);
            if (double.IsNaN(stopPips) || double.IsInfinity(stopPips))
                return;
            var takePips = stopPips * RewardRisk;
            var volume = Symbol.VolumeForProportionalRisk(ProportionalAmountType.Equity,
                                                           RiskPercent, stopPips);
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            if (double.IsNaN(volume) || double.IsInfinity(volume) ||
                volume < Symbol.VolumeInUnitsMin || volume > Symbol.VolumeInUnitsMax)
                return;

            var result = ExecuteMarketOrder(tradeType, SymbolName, volume, Label, stopPips, takePips);
            if (!result.IsSuccessful)
                Print("OMEGA X order rejected: {0}", result.Error);
            else
                Print("OMEGA X DEMO order: {0} volume={1} SL={2} TP={3}",
                      tradeType, volume, stopPips, takePips);
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
            return Account.Equity <= _sessionStartEquity * (1.0 - DailyLossStopPercent / 100.0);
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            if (args.Position.Label != Label || args.Position.SymbolName != SymbolName)
                return;
            if (args.Position.NetProfit < 0)
                _consecutiveLosses++;
            else if (args.Position.NetProfit > 0)
                _consecutiveLosses = 0;
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
            Print("OMEGA X stopped. Existing positions remain broker-managed.");
        }
    }
}
