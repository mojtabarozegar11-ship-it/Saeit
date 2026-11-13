using System;
using System.Linq;
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

        private ExponentialMovingAverage _fastEma;
        private ExponentialMovingAverage _slowEma;
        private RelativeStrengthIndex _rsi;
        private AverageTrueRange _atr;
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
            if (atrPrice <= 0)
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

            var rangeHigh = Bars.HighPrices.Skip(Math.Max(0, index - 20)).Take(20).Max();
            var rangeLow = Bars.LowPrices.Skip(Math.Max(0, index - 20)).Take(20).Min();
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
            if (Account.IsLive)
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
                    // Prices from Position.EntryPrice and Position.TakeProfit are absolute.
                    // Never treat them as pip distances during protection updates.
                    var protectionResult = ModifyPosition(position, breakEven,
                        position.TakeProfit, ProtectionType.Absolute);
                    if (!protectionResult.IsSuccessful)
                        Print("OMEGA X protection update rejected: {0}", protectionResult.Error);
                }
            }
        }

        private void SubmitDemoOrder(TradeType tradeType, double atrPrice)
        {
            var stopPips = Math.Max(atrPrice * AtrStopMultiplier / Symbol.PipSize, 1.0);
            var takePips = stopPips * RewardRisk;
            var volume = Symbol.VolumeForProportionalRisk(ProportionalAmountType.Equity,
                                                           RiskPercent, stopPips);
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            if (volume < Symbol.VolumeInUnitsMin)
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
            return (Symbol.Ask - Symbol.Bid) / Symbol.PipSize;
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
