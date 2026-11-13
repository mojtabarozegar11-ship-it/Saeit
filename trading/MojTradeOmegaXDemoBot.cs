// Canonical execution core for mojtaba.bot.ai.\n// QuantumScalp capabilities are absorbed here; live trading remains locked.\nusing System;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace Mojtaba.Bot.Ai
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class MojtabaBotTradingCoreDemo : Robot
    {
        private const string BaseLabel = "MojtabaBot.ai-TRADING-DEMO";

        private ExponentialMovingAverage _fastEma;
        private ExponentialMovingAverage _slowEma;
        private RelativeStrengthIndex _rsi;
        private AverageTrueRange _atr;

        private Bars _higherBars;
        private ExponentialMovingAverage _higherFastEma;
        private ExponentialMovingAverage _higherSlowEma;

        private DateTime _lastEntryTime = DateTime.MinValue;

        [Parameter("EMA Cross", DefaultValue = true)]
        public bool EnableEmaCross { get; set; }

        [Parameter("RSI Pullback", DefaultValue = true)]
        public bool EnableRsiPullback { get; set; }

        [Parameter("Breakout", DefaultValue = true)]
        public bool EnableBreakout { get; set; }

        [Parameter("Fast EMA", DefaultValue = 9, MinValue = 2)]
        public int FastEma { get; set; }

        [Parameter("Slow EMA", DefaultValue = 21, MinValue = 3)]
        public int SlowEma { get; set; }

        [Parameter("Higher TF Fast EMA", DefaultValue = 20, MinValue = 3)]
        public int HigherFastEma { get; set; }

        [Parameter("Higher TF Slow EMA", DefaultValue = 50, MinValue = 5)]
        public int HigherSlowEma { get; set; }

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

        [Parameter("Reward / Risk", DefaultValue = 1.4, MinValue = 0.5)]
        public double RewardRisk { get; set; }

        [Parameter("Risk Per Trade (%)", DefaultValue = 0.25, MinValue = 0.05, MaxValue = 1.0)]
        public double RiskPerTradePercent { get; set; }

        [Parameter("Max Volume (Units)", DefaultValue = 5000, MinValue = 1)]
        public double MaxVolumeInUnits { get; set; }

        [Parameter("Max Open Trades / Symbol", DefaultValue = 3, MinValue = 1, MaxValue = 10)]
        public int MaxOpenTradesPerSymbol { get; set; }

        [Parameter("Max Daily Loss (%)", DefaultValue = 2.0, MinValue = 0.5, MaxValue = 10)]
        public double MaxDailyLossPercent { get; set; }

        [Parameter("Max Consecutive Losses", DefaultValue = 3, MinValue = 1, MaxValue = 10)]
        public int MaxConsecutiveLosses { get; set; }

        [Parameter("Cooldown Seconds", DefaultValue = 30, MinValue = 0, MaxValue = 3600)]
        public int CooldownSeconds { get; set; }

        [Parameter("Maximum Spread (Pips)", DefaultValue = 2.5, MinValue = 0.1)]
        public double MaximumSpreadPips { get; set; }

        [Parameter("Minimum Stop (Pips)", DefaultValue = 3.0, MinValue = 1)]
        public double MinimumStopPips { get; set; }

        [Parameter("Break-even Trigger (Pips)", DefaultValue = 4.0, MinValue = 0.5)]
        public double BreakEvenTriggerPips { get; set; }

        [Parameter("Break-even Lock (Pips)", DefaultValue = 0.5, MinValue = 0)]
        public double BreakEvenLockPips { get; set; }

        [Parameter("Trailing Start (Pips)", DefaultValue = 7.0, MinValue = 1)]
        public double TrailingStartPips { get; set; }

        [Parameter("Trailing Distance (Pips)", DefaultValue = 4.0, MinValue = 1)]
        public double TrailingDistancePips { get; set; }

        protected override void OnStart()
        {
            if (Account.IsLive)
            {
                Print("BLOCKED: MojTradeDemoBot is demo-only.");
                Stop();
                return;
            }

            if (FastEma >= SlowEma || HigherFastEma >= HigherSlowEma)
            {
                Print("BLOCKED: EMA settings are invalid.");
                Stop();
                return;
            }

            if (!EnableEmaCross && !EnableRsiPullback && !EnableBreakout)
            {
                Print("BLOCKED: no strategy is enabled.");
                Stop();
                return;
            }

            _fastEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, FastEma);
            _slowEma = Indicators.ExponentialMovingAverage(Bars.ClosePrices, SlowEma);
            _rsi = Indicators.RelativeStrengthIndex(Bars.ClosePrices, RsiPeriod);
            _atr = Indicators.AverageTrueRange(AtrPeriod, MovingAverageType.Exponential);

            _higherBars = MarketData.GetBars(TimeFrame.Minute15, SymbolName);
            _higherFastEma = Indicators.ExponentialMovingAverage(_higherBars.ClosePrices, HigherFastEma);
            _higherSlowEma = Indicators.ExponentialMovingAverage(_higherBars.ClosePrices, HigherSlowEma);

            Print("Mojtaba.bot.ai canonical trading core started on DEMO: {0} {1}", SymbolName, TimeFrame);
            Print("Risk={0}% | max trades={1} | daily loss stop={2}%",
                RiskPerTradePercent, MaxOpenTradesPerSymbol, MaxDailyLossPercent);
        }

        protected override void OnBarClosed()
        {
            ManageRiskStop();

            var requiredBars = Math.Max(SlowEma, BreakoutLookback) +
                               Math.Max(AtrPeriod, RsiPeriod) + 5;
            if (Bars.Count < requiredBars || _higherBars.Count < HigherSlowEma + 5)
                return;

            if (OpenTradeCount() >= MaxOpenTradesPerSymbol)
                return;

            if (DailyNetProfit() <= -(Account.Balance * MaxDailyLossPercent / 100.0))
            {
                Print("Daily loss limit reached. New entries disabled.");
                return;
            }

            if (RecentConsecutiveLosses() >= MaxConsecutiveLosses)
            {
                Print("Consecutive-loss limit reached. New entries disabled.");
                return;
            }

            if ((Server.Time - _lastEntryTime).TotalSeconds < CooldownSeconds)
                return;

            var spreadPips = (Symbol.Ask - Symbol.Bid) / Symbol.PipSize;
            if (spreadPips > MaximumSpreadPips)
                return;

            var fastPrevious = _fastEma.Result.Last(2);
            var slowPrevious = _slowEma.Result.Last(2);
            var fastClosed = _fastEma.Result.Last(1);
            var slowClosed = _slowEma.Result.Last(1);
            var rsiPrevious = _rsi.Result.Last(2);
            var rsiClosed = _rsi.Result.Last(1);

            var higherFast = _higherFastEma.Result.Last(1);
            var higherSlow = _higherSlowEma.Result.Last(1);
            var higherTrendUp = higherFast > higherSlow;
            var higherTrendDown = higherFast < higherSlow;

            var close = Bars.ClosePrices.Last(1);
            var priorHigh = HighestHigh(2, BreakoutLookback);
            var priorLow = LowestLow(2, BreakoutLookback);

            if (EnableEmaCross && higherTrendUp &&
                fastPrevious <= slowPrevious && fastClosed > slowClosed)
                TryOpen(TradeType.Buy, "EMA");

            if (EnableEmaCross && higherTrendDown &&
                fastPrevious >= slowPrevious && fastClosed < slowClosed)
                TryOpen(TradeType.Sell, "EMA");

            if (EnableRsiPullback && higherTrendUp &&
                rsiPrevious <= RsiOversold && rsiClosed > RsiOversold &&
                fastClosed > slowClosed)
                TryOpen(TradeType.Buy, "RSI");

            if (EnableRsiPullback && higherTrendDown &&
                rsiPrevious >= RsiOverbought && rsiClosed < RsiOverbought &&
                fastClosed < slowClosed)
                TryOpen(TradeType.Sell, "RSI");

            if (EnableBreakout && higherTrendUp && close > priorHigh)
                TryOpen(TradeType.Buy, "BREAKOUT");

            if (EnableBreakout && higherTrendDown && close < priorLow)
                TryOpen(TradeType.Sell, "BREAKOUT");
        }

        protected override void OnTick()
        {
            ManageOpenPositions();
        }

        private void TryOpen(TradeType tradeType, string strategy)
        {
            if (OpenTradeCount() >= MaxOpenTradesPerSymbol)
                return;

            var atrPips = _atr.Result.Last(1) / Symbol.PipSize;
            var stopLossPips = Math.Max(MinimumStopPips, atrPips * AtrStopMultiplier);
            var takeProfitPips = stopLossPips * RewardRisk;

            var volume = Symbol.VolumeForProportionalRisk(
                ProportionalAmountType.Equity,
                RiskPerTradePercent,
                stopLossPips,
                RoundingMode.Down);

            volume = Math.Min(volume, MaxVolumeInUnits);
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);

            if (volume < Symbol.VolumeInUnitsMin)
            {
                Print("{0}: calculated volume is below broker minimum.", strategy);
                return;
            }

            var label = BaseLabel + "-" + strategy;
            var result = ExecuteMarketOrder(
                tradeType,
                SymbolName,
                volume,
                label,
                stopLossPips,
                takeProfitPips,
                "DEMO ONLY | short-term | " + strategy);

            if (!result.IsSuccessful)
            {
                Print("{0} rejected: {1}", strategy, result.Error);
                return;
            }

            _lastEntryTime = Server.Time;
            Print("{0} opened {1}: risk={2}% volume={3} SL={4:F1} TP={5:F1}",
                strategy, tradeType, RiskPerTradePercent, volume,
                stopLossPips, takeProfitPips);
        }

        private void ManageRiskStop()
        {
            if (DailyNetProfit() <= -(Account.Balance * MaxDailyLossPercent / 100.0))
                Print("Risk stop active: daily loss cap reached.");
        }

        private void ManageOpenPositions()
        {
            foreach (var position in Positions)
            {
                if (!IsMojTradePosition(position))
                    continue;

                var profitPips = position.Pips;
                if (profitPips < BreakEvenTriggerPips)
                    continue;

                double desiredStop;
                if (position.TradeType == TradeType.Buy)
                {
                    desiredStop = position.EntryPrice + BreakEvenLockPips * Symbol.PipSize;
                    if (profitPips >= TrailingStartPips)
                        desiredStop = Math.Max(desiredStop,
                            Symbol.Bid - TrailingDistancePips * Symbol.PipSize);

                    if (!position.StopLoss.HasValue || desiredStop > position.StopLoss.Value)
                        ModifyPosition(position, desiredStop, position.TakeProfit, ProtectionType.Absolute);
                }
                else
                {
                    desiredStop = position.EntryPrice - BreakEvenLockPips * Symbol.PipSize;
                    if (profitPips >= TrailingStartPips)
                        desiredStop = Math.Min(desiredStop,
                            Symbol.Ask + TrailingDistancePips * Symbol.PipSize);

                    if (!position.StopLoss.HasValue || desiredStop < position.StopLoss.Value)
                        ModifyPosition(position, desiredStop, position.TakeProfit, ProtectionType.Absolute);
                }
            }
        }

        private bool IsMojTradePosition(Position position)
        {
            return position.SymbolName == SymbolName &&
                   position.Label != null &&
                   position.Label.StartsWith(BaseLabel, StringComparison.Ordinal);
        }

        private int OpenTradeCount()
        {
            var count = 0;
            foreach (var position in Positions)
                if (IsMojTradePosition(position))
                    count++;
            return count;
        }

        private double DailyNetProfit()
        {
            var total = 0.0;
            foreach (var label in StrategyLabels())
            {
                var trades = History.FindAll(label, SymbolName);
                foreach (var trade in trades)
                    if (trade.ClosingTime.Date == Server.Time.Date)
                        total += trade.NetProfit;
            }
            return total;
        }

        private int RecentConsecutiveLosses()
        {
            var losses = 0;
            HistoricalTrade lastTrade = null;

            foreach (var label in StrategyLabels())
            {
                var trades = History.FindAll(label, SymbolName);
                foreach (var trade in trades)
                {
                    if (lastTrade == null || trade.ClosingTime > lastTrade.ClosingTime)
                        lastTrade = trade;
                }
            }

            while (lastTrade != null && lastTrade.NetProfit < 0)
            {
                losses++;
                var next = FindPreviousTrade(lastTrade.ClosingTime);
                lastTrade = next;
            }

            return losses;
        }

        private HistoricalTrade FindPreviousTrade(DateTime before)
        {
            HistoricalTrade previous = null;
            foreach (var label in StrategyLabels())
            {
                var trades = History.FindAll(label, SymbolName);
                foreach (var trade in trades)
                {
                    if (trade.ClosingTime < before &&
                        (previous == null || trade.ClosingTime > previous.ClosingTime))
                        previous = trade;
                }
            }
            return previous;
        }

        private string[] StrategyLabels()
        {
            return new[]
            {
                BaseLabel + "-EMA",
                BaseLabel + "-RSI",
                BaseLabel + "-BREAKOUT"
            };
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
            Print("MojTrade QuantumScalp v2 stopped. Existing positions remain open.");
        }
    }
}
