using System;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class MojTradeDemoBot : Robot
    {
        private const string Label = "MojTrade-Demo-EMA-ATR";

        private ExponentialMovingAverage _fastEma;
        private ExponentialMovingAverage _slowEma;
        private AverageTrueRange _atr;

        [Parameter("Fast EMA", DefaultValue = 20, MinValue = 2)]
        public int FastEma { get; set; }

        [Parameter("Slow EMA", DefaultValue = 50, MinValue = 3)]
        public int SlowEma { get; set; }

        [Parameter("ATR Period", DefaultValue = 14, MinValue = 2)]
        public int AtrPeriod { get; set; }

        [Parameter("ATR Stop Multiplier", DefaultValue = 2.0, MinValue = 0.5)]
        public double AtrStopMultiplier { get; set; }

        [Parameter("Reward / Risk", DefaultValue = 1.5, MinValue = 0.5)]
        public double RewardRisk { get; set; }

        [Parameter("Fixed Volume (Units)", DefaultValue = 1000, MinValue = 1)]
        public double FixedVolumeInUnits { get; set; }

        [Parameter("Maximum Spread (Pips)", DefaultValue = 5.0, MinValue = 0.1)]
        public double MaximumSpreadPips { get; set; }

        [Parameter("Minimum Stop (Pips)", DefaultValue = 10.0, MinValue = 1)]
        public double MinimumStopPips { get; set; }

        protected override void OnStart()
        {
            if (Account.IsLive)
            {
                Print("BLOCKED: MojTradeDemoBot can run only on a demo account.");
                Stop();
                return;
            }

            if (FastEma >= SlowEma)
            {
                Print("BLOCKED: Fast EMA must be lower than Slow EMA.");
                Stop();
                return;
            }

            _fastEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, FastEma);
            _slowEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, SlowEma);
            _atr = Indicators.AverageTrueRange(AtrPeriod, MovingAverageType.Exponential);

            Print("MojTradeDemoBot started on DEMO account: {0}, symbol: {1}, timeframe: {2}",
                Account.Balance, SymbolName, TimeFrame);
        }

        protected override void OnBarClosed()
        {
            if (Bars.Count < SlowEma + AtrPeriod + 3)
                return;

            if (Positions.Find(Label, SymbolName) != null)
                return;

            var spreadPips = (Symbol.Ask - Symbol.Bid) / Symbol.PipSize;
            if (spreadPips > MaximumSpreadPips)
            {
                Print("Skipped: spread {0:F2} pips exceeds limit {1:F2}.",
                    spreadPips, MaximumSpreadPips);
                return;
            }

            var fastPrevious = _fastEma.Result.Last(2);
            var slowPrevious = _slowEma.Result.Last(2);
            var fastClosed = _fastEma.Result.Last(1);
            var slowClosed = _slowEma.Result.Last(1);

            TradeType? tradeType = null;
            if (fastPrevious <= slowPrevious && fastClosed > slowClosed)
                tradeType = TradeType.Buy;
            else if (fastPrevious >= slowPrevious && fastClosed < slowClosed)
                tradeType = TradeType.Sell;

            if (!tradeType.HasValue)
                return;

            var atrPips = _atr.Result.Last(1) / Symbol.PipSize;
            var stopLossPips = Math.Max(MinimumStopPips, atrPips * AtrStopMultiplier);
            var takeProfitPips = stopLossPips * RewardRisk;
            var volume = Symbol.NormalizeVolumeInUnits(FixedVolumeInUnits, RoundingMode.Down);

            if (volume < Symbol.VolumeInUnitsMin)
            {
                Print("Skipped: volume is below broker minimum.");
                return;
            }

            var result = ExecuteMarketOrder(
                tradeType.Value,
                SymbolName,
                volume,
                Label,
                stopLossPips,
                takeProfitPips,
                "DEMO ONLY EMA/ATR crossover");

            if (!result.IsSuccessful)
                Print("Demo order rejected: {0}", result.Error);
            else
                Print("Demo order opened: {0}, volume={1}, SL={2:F1}, TP={3:F1}",
                    tradeType.Value, volume, stopLossPips, takeProfitPips);
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
