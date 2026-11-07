using System;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class MojTradeDemoBot : Robot
    {
        private const string BaseLabel = "MojTrade-Demo-Scalper";
        private ExponentialMovingAverage _fastEma;
        private ExponentialMovingAverage _slowEma;
        private AverageTrueRange _atr;
        private RelativeStrengthIndex _rsi;

        [Parameter("Enable EMA Cross", DefaultValue = true)]
        public bool EnableEmaCross { get; set; }

        [Parameter("Enable RSI Pullback", DefaultValue = true)]
        public bool EnableRsiPullback { get; set; }

        [Parameter("Enable Breakout", DefaultValue = true)]
        public bool EnableBreakout { get; set; }

        [Parameter("Fast EMA", DefaultValue = 9, MinValue = 2)]
        public int FastEma { get; set; }

        [Parameter("Slow EMA", DefaultValue = 21, MinValue = 3)]
        public int SlowEma { get; set; }

        [Parameter("RSI Period", DefaultValue = 14, MinValue = 2)]
        public int RsiPeriod { get; set; }

        [Parameter("RSI Oversold", DefaultValue = 30, MinValue = 1, MaxValue = 49)]
        public double RsiOversold { get; set; }

        [Parameter("RSI Overbought", DefaultValue = 70, MinValue = 51, MaxValue = 99)]
        public double RsiOverbought { get; set; }

        [Parameter("Breakout Lookback", DefaultValue = 20, MinValue = 3)]
        public int BreakoutLookback { get; set; }

        [Parameter("ATR Period", DefaultValue = 14, MinValue = 2)]
        public int AtrPeriod { get; set; }

        [Parameter("ATR Stop Multiplier", DefaultValue = 1.2, MinValue = 0.2)]
        public double AtrStopMultiplier { get; set; }

        [Parameter("Reward / Risk", DefaultValue = 1.2, MinValue = 0.5)]
        public double RewardRisk { get; set; }

        [Parameter("Fixed Volume (Units)", DefaultValue = 1000, MinValue = 1)]
        public double FixedVolumeInUnits { get; set; }

        [Parameter("Max Open Trades / Symbol", DefaultValue = 3, MinValue = 1, MaxValue = 10)]
        public int MaxOpenTradesPerSymbol { get; set; }

        [Parameter("Maximum Spread (Pips)", DefaultValue = 2.5, MinValue = 0.1)]
        public double MaximumSpreadPips { get; set; }

        [Parameter("Minimum Stop (Pips)", DefaultValue = 3.0, MinValue = 1)]
        public double MinimumStopPips { get; set; }

        protected override void OnStart()
        {
            if (Account.IsLive)
            {
                Print("BLOCKED: this cBot is demo-only and cannot run on a live account.");
                Stop();
                return;
            }

            if (FastEma >= SlowEma)
            {
                Print("BLOCKED: Fast EMA must be lower than Slow EMA.");
                Stop();
                return;
            }

            if (!EnableEmaCross && !EnableRsiPullback && !EnableBreakout)
            {
                Print("BLOCKED: at least one strategy must be enabled.");
                Stop();
                return;
            }

            _fastEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, FastEma);
            _slowEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, SlowEma);
            _atr = Indicators.AverageTrueRange(AtrPeriod, MovingAverageType.Exponential);
            _rsi = Indicators.RelativeStrengthIndex(Bars.ClosePrices, RsiPeriod);

            Print("MojTradeDemoBot started: DEMO ONLY | {0} | {1} | {2}",
                SymbolName, TimeFrame, Account.Balance);
            Print("Short-term profile: attach to 1-minute, 5-minute or 10-minute charts.");
        }

        protected override void OnBarClosed()
        {
            var requiredBars = Math.Max(SlowEma, BreakoutLookback) + Math.Max(AtrPeriod, RsiPeriod) + 5;
            if (Bars.Count < requiredBars)
                return;

            var spreadPips = (Symbol.Ask - Symbol.Bid) / Symbol.PipSize;
            if (spreadPips > MaximumSpreadPips)
            {
                Print("Skipped: spread {0:F2} pips exceeds {1:F2}.",
                    spreadPips, MaximumSpreadPips);
                return;
            }

            var close = Bars.ClosePrices.Last(1);
            var fastPrevious = _fastEma.Result.Last(2);
            var slowPrevious = _slowEma.Result.Last(2);
            var fastClosed = _fastEma.Result.Last(1);
            var slowClosed = _slowEma.Result.Last(1);
            var rsiPrevious = _rsi.Result.Last(2);
            var rsiClosed = _rsi.Result.Last(1);

            if (EnableEmaCross && fastPrevious <= slowPrevious && fastClosed > slowClosed)
                TryOpen(TradeType.Buy, "EMA");
            if (EnableEmaCross && fastPrevious >= slowPrevious && fastClosed < slowClosed)
                TryOpen(TradeType.Sell, "EMA");

            if (EnableRsiPullback && fastClosed > slowClosed &&
                rsiPrevious <= RsiOversold && rsiClosed > RsiOversold)
                TryOpen(TradeType.Buy, "RSI");
            if (EnableRsiPullback && fastClosed < slowClosed &&
                rsiPrevious >= RsiOverbought && rsiClosed < RsiOverbought)
                TryOpen(TradeType.Sell, "RSI");

            var priorHigh = HighestHigh(2, BreakoutLookback);
            var priorLow = LowestLow(2, BreakoutLookback);

            if (EnableBreakout && close > priorHigh)
                TryOpen(TradeType.Buy, "BREAKOUT");
            if (EnableBreakout && close < priorLow)
                TryOpen(TradeType.Sell, "BREAKOUT");
        }

        private void TryOpen(TradeType tradeType, string strategy)
        {
            if (OpenTradeCount() >= MaxOpenTradesPerSymbol)
                return;

            var volume = Symbol.NormalizeVolumeInUnits(FixedVolumeInUnits, RoundingMode.Down);
            if (volume < Symbol.VolumeInUnitsMin)
            {
                Print("Skipped {0}: volume is below broker minimum.", strategy);
                return;
            }

            var atrPips = _atr.Result.Last(1) / Symbol.PipSize;
            var stopLossPips = Math.Max(MinimumStopPips, atrPips * AtrStopMultiplier);
            var takeProfitPips = stopLossPips * RewardRisk;
            var label = BaseLabel + "-" + strategy;

            var result = ExecuteMarketOrder(
                tradeType,
                SymbolName,
                volume,
                label,
                stopLossPips,
                takeProfitPips,
                "DEMO ONLY short-term " + strategy);

            if (!result.IsSuccessful)
                Print("{0} demo order rejected: {1}", strategy, result.Error);
            else
                Print("{0} demo order opened: {1}, volume={2}, SL={3:F1}, TP={4:F1}",
                    strategy, tradeType, volume, stopLossPips, takeProfitPips);
        }

        private int OpenTradeCount()
        {
            var count = 0;
            foreach (var position in Positions)
            {
                if (position.SymbolName == SymbolName &&
                    position.Label != null &&
                    position.Label.StartsWith(BaseLabel, StringComparison.Ordinal))
                    count++;
            }
            return count;
        }

        private double HighestHigh(int startIndex, int count)
        {
            var highest = double.MinValue;
            for (var i = startIndex; i < startIndex + count; i++)
                highest = Math.Max(highest, Bars.HighPrices.Last(i));
            return highest;
        }

        private double LowestLow(int startIndex, int count)
        {
            var lowest = double.MaxValue;
            for (var i = startIndex; i < startIndex + count; i++)
                lowest = Math.Min(lowest, Bars.LowPrices.Last(i));
            return lowest;
        }

        protected override void OnError(Error error)
        {
            Print("cBot error: {0}", error.Code);
        }

        protected override void OnStop()
        {
            Print("MojTradeDemoBot stopped. Existing positions were not closed automatically.");
        }
    }
}
