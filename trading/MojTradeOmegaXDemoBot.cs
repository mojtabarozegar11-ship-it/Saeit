using System;
using System.Globalization;
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
        private const string ScalpLabelPrefix = "MojTrade-Demo-QuantumScalp-v2-";
        private const int SharedPositionCap = 3;

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

        [Parameter("Daily Loss Stop %", DefaultValue = 2.0, MinValue = 0.1, MaxValue = 10)]
        public double DailyLossStopPercent { get; set; }

        [Parameter("Consecutive Loss Stop", DefaultValue = 5, MinValue = 1, MaxValue = 10)]
        public int ConsecutiveLossStop { get; set; }

        [Parameter("Enable Coordinated Demo Trading", DefaultValue = false)]
        public bool EnableCoordinatedDemoTrading { get; set; }

        [Parameter("Risk Coordinator HTTPS URL", DefaultValue = "")]
        public string CoordinatorUrl { get; set; }

        [Parameter("Risk Coordinator Token", DefaultValue = "")]
        public string CoordinatorToken { get; set; }

        [Parameter("Enable Demo Trading", DefaultValue = false)]
        public bool EnableDemoTrading { get; set; }

        private ExponentialMovingAverage _fastEma;
        private ExponentialMovingAverage _slowEma;
        private RelativeStrengthIndex _rsi;
        private AverageTrueRange _atr;
        private double _sessionStartEquity;
        private DateTime _riskDayUtc;
        private int _consecutiveLosses;
        private bool _halted;
        private DateTime _lastObservationUtc = DateTime.MinValue;

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
            _riskDayUtc = Server.TimeInUtc.Date;
            Positions.Closed += OnPositionClosed;
            if (EnableCoordinatedDemoTrading && CoordinatorConfigured())
            {
                Timer.Start(60);
                ObserveCoordinatedRisk(TodayAccountRealizedProfit());
            }
            Print("OMEGA X DEMO adapter started: {0} {1}", SymbolName, TimeFrame);
        }

        protected override void OnBarClosed()
        {
            if (Account.IsLive)
                return;
            ObserveCoordinatedRisk(TodayAccountRealizedProfit());
            if (_halted || !EnableDemoTrading || !EnableCoordinatedDemoTrading ||
                !CoordinatorConfigured() || Account.IsLive || Bars.Count < SlowEmaPeriod + 5)
                return;
            if (DailyLossReached() || _consecutiveLosses >= ConsecutiveLossStop)
                return;
            var spreadPips = CurrentSpreadPips();
            if (!IsFinitePositive(spreadPips) || spreadPips > MaxSpreadPips)
                return;

            var positions = Positions.FindAll(Label, SymbolName);
            if (positions.Length >= MaxPositions || SharedMojTradePositionCount() >= SharedPositionCap)
                return;

            var index = Bars.Count - 1;
            var atrPrice = _atr.Result[index];
            if (!IsFinitePositive(atrPrice))
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

            if (!IsFinite(fast) || !IsFinite(slow) || !IsFinite(previousFast) ||
                !IsFinite(previousSlow) || !IsFinite(rsi))
                return;

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
                    ModifyPosition(position, breakEven, position.TakeProfit, ProtectionType.Absolute);
                }
            }
        }

        protected override void OnTimer()
        {
            if (Account.IsLive)
            {
                _halted = true;
                Stop();
                return;
            }
            ObserveCoordinatedRisk(TodayAccountRealizedProfit());
        }

        private void SubmitDemoOrder(TradeType tradeType, double atrPrice)
        {
            // Last line of defense: entries may be invoked after feed/account changes.
            if (_halted || !EnableDemoTrading || !EnableCoordinatedDemoTrading ||
                !CoordinatorConfigured() || Account.IsLive || DailyLossReached() ||
                _consecutiveLosses >= ConsecutiveLossStop ||
                Positions.FindAll(Label, SymbolName).Length >= MaxPositions ||
                SharedMojTradePositionCount() >= SharedPositionCap ||
                !IsFinitePositive(Account.Equity) || !IsFinitePositive(Symbol.PipSize) ||
                !IsFinitePositive(Symbol.Ask) || !IsFinitePositive(Symbol.Bid) ||
                Symbol.Ask < Symbol.Bid || !IsFinitePositive(atrPrice) ||
                !IsFinitePositive(RiskPercent) || RiskPercent > 1 ||
                !IsFinitePositive(AtrStopMultiplier) || !IsFinitePositive(RewardRisk) ||
                !IsFinitePositive(Symbol.VolumeInUnitsMin) ||
                !IsFinitePositive(MaxSpreadPips) ||
                !IsFinitePositive(CurrentSpreadPips()) || CurrentSpreadPips() > MaxSpreadPips)
                return;

            var stopPips = Math.Max(atrPrice * AtrStopMultiplier / Symbol.PipSize, 1.0);
            var takePips = stopPips * RewardRisk;
            if (!IsFinitePositive(stopPips) || !IsFinitePositive(takePips))
                return;
            var volume = Symbol.VolumeForProportionalRisk(ProportionalAmountType.Equity,
                                                           RiskPercent, stopPips);
            if (!IsFinitePositive(volume))
                return;
            volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
            if (!IsFinitePositive(stopPips) || !IsFinitePositive(takePips) ||
                !IsFinitePositive(volume) || volume < Symbol.VolumeInUnitsMin)
                return;

            var reservationId = ReserveCoordinatedSlot(TodayAccountRealizedProfit());
            if (reservationId == null)
                return;
            var result = ExecuteMarketOrder(tradeType, SymbolName, volume, Label, stopPips, takePips);
            if (!SettleCoordinatedSlot(reservationId, result.IsSuccessful))
            {
                Print("CRITICAL: OMEGA coordinator settlement failed. Adapter halted.");
                _halted = true;
                Stop();
                return;
            }
            if (!result.IsSuccessful)
                Print("OMEGA X order rejected: {0}", result.Error);
            else
            {
                if (result.Position == null || !result.Position.StopLoss.HasValue ||
                    !result.Position.TakeProfit.HasValue)
                {
                    Print("CRITICAL: OMEGA demo order missing broker-side SL/TP.");
                    if (result.Position != null)
                    {
                        var close = ClosePosition(result.Position);
                        if (!close.IsSuccessful)
                            Print("CRITICAL: unprotected OMEGA demo close failed: {0}", close.Error);
                    }
                    Stop();
                    return;
                }
                Print("OMEGA X DEMO order: {0} volume={1} SL={2} TP={3}",
                      tradeType, volume, stopPips, takePips);
            }
        }

        private double TodayAccountRealizedProfit()
        {
            // Match QuantumScalp's account-wide observation across all symbols,
            // cBots and manual positions on this DEMO account.
            var total = 0.0;
            foreach (var trade in History)
            {
                if (trade.ClosingTime.Date != Server.TimeInUtc.Date)
                    continue;
                if (!IsFinite(trade.NetProfit))
                    return double.NaN;
                total += trade.NetProfit;
            }
            return IsFinite(total) ? total : double.NaN;
        }

        private bool CoordinatorConfigured()
        {
            Uri endpoint;
            return !string.IsNullOrWhiteSpace(CoordinatorUrl) &&
                   Uri.TryCreate(CoordinatorUrl, UriKind.Absolute, out endpoint) &&
                   endpoint.Scheme == Uri.UriSchemeHttps &&
                   string.IsNullOrEmpty(endpoint.UserInfo) &&
                   !string.IsNullOrWhiteSpace(CoordinatorToken) &&
                   CoordinatorToken.Length >= 32;
        }

        private void ObserveCoordinatedRisk(double realizedToday)
        {
            if (_halted || Account.IsLive || !EnableCoordinatedDemoTrading ||
                !CoordinatorConfigured())
                return;
            var now = Server.TimeInUtc;
            if (now >= _lastObservationUtc &&
                (now - _lastObservationUtc).TotalSeconds < 60)
                return;
            _lastObservationUtc = now;
            if (!IsFinitePositive(Account.Equity) || !IsFinite(realizedToday))
            {
                _halted = true;
                Print("BLOCKED: invalid broker risk observation.");
                return;
            }
            var invariant = CultureInfo.InvariantCulture;
            var body = "mode=demo&account=" + Account.Number.ToString(invariant) +
                       "&day=" + now.ToString("yyyy-MM-dd", invariant) +
                       "&request_id=" + Guid.NewGuid().ToString("N") +
                       "&equity=" + Account.Equity.ToString("R", invariant) +
                       "&realized_today=" + realizedToday.ToString("R", invariant) +
                       "&open_positions=" + SharedMojTradePositionCount().ToString(invariant);
            try
            {
                var request = new HttpRequest(new Uri(CoordinatorUrl.TrimEnd('/') + "/v1/observe"))
                {
                    Method = HttpMethod.Post,
                    Body = body,
                    Timeout = TimeSpan.FromSeconds(3)
                };
                request.Headers.Add("Content-Type", "application/x-www-form-urlencoded");
                request.Headers.Add("Authorization", "Bearer " + CoordinatorToken);
                var response = Http.Send(request);
                if (response.IsSuccessful && response.StatusCode == 200 &&
                    response.Body == "OBSERVED")
                    return;
            }
            catch (Exception)
            {
                // Never print token, raw request or financial account values.
            }
            _halted = true;
            Print("BLOCKED: coordinator risk observation failed; new orders halted.");
        }

        private string ReserveCoordinatedSlot(double realizedToday)
        {
            if (!CoordinatorConfigured() || Account.IsLive ||
                !IsFinitePositive(Account.Equity) || !IsFinite(realizedToday))
                return null;

            var requestId = Guid.NewGuid().ToString("N");
            var invariant = CultureInfo.InvariantCulture;
            var body = "mode=demo&account=" + Account.Number.ToString(invariant) +
                       "&day=" + Server.TimeInUtc.ToString("yyyy-MM-dd", invariant) +
                       "&request_id=" + requestId +
                       "&equity=" + Account.Equity.ToString("R", invariant) +
                       "&realized_today=" + realizedToday.ToString("R", invariant) +
                       "&open_positions=" + SharedMojTradePositionCount().ToString(invariant);
            try
            {
                var request = new HttpRequest(new Uri(CoordinatorUrl.TrimEnd('/') + "/v1/reserve"))
                {
                    Method = HttpMethod.Post,
                    Body = body,
                    Timeout = TimeSpan.FromSeconds(3)
                };
                request.Headers.Add("Content-Type", "application/x-www-form-urlencoded");
                request.Headers.Add("Authorization", "Bearer " + CoordinatorToken);
                var response = Http.Send(request);
                if (!response.IsSuccessful || response.StatusCode != 200 ||
                    response.Body != "GRANTED|" + requestId)
                {
                    Print("DEMO order blocked: coordinator denied or unavailable.");
                    return null;
                }
                return requestId;
            }
            catch (Exception)
            {
                Print("DEMO order blocked: coordinator connection failed.");
                return null;
            }
        }

        private bool SettleCoordinatedSlot(string requestId, bool filled)
        {
            // Retry only ambiguous transport/server failures with the SAME
            // request ID and outcome. The coordinator is settlement-idempotent;
            // a conflicting or unauthorized response still halts this adapter.
            for (var attempt = 0; attempt < 2; attempt++)
            {
                try
                {
                    var request = new HttpRequest(new Uri(
                        CoordinatorUrl.TrimEnd('/') + (filled ? "/v1/commit" : "/v1/cancel")))
                    {
                        Method = HttpMethod.Post,
                        Body = "account=" + Account.Number.ToString(CultureInfo.InvariantCulture) +
                               "&request_id=" + requestId,
                        Timeout = TimeSpan.FromSeconds(3)
                    };
                    request.Headers.Add("Content-Type", "application/x-www-form-urlencoded");
                    request.Headers.Add("Authorization", "Bearer " + CoordinatorToken);
                    var response = Http.Send(request);
                    if (response.IsSuccessful && response.StatusCode == 200 &&
                        response.Body == "SETTLED")
                        return true;
                    if (response.StatusCode < 500)
                        return false;
                }
                catch (Exception)
                {
                    // The first request may already have been committed.
                }
            }
            return false; // Never treat unconfirmed broker settlement as safe.
        }

        private int SharedMojTradePositionCount()
        {
            var count = 0;
            foreach (var position in Positions)
                if (position.Label == Label ||
                    (position.Label != null && position.Label.StartsWith(ScalpLabelPrefix, StringComparison.Ordinal)))
                    count++;
            return count;
        }

        private static bool IsFinite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        private static bool IsFinitePositive(double value)
        {
            return IsFinite(value) && value > 0;
        }

        private double CurrentSpreadPips()
        {
            return (Symbol.Ask - Symbol.Bid) / Symbol.PipSize;
        }

        private bool DailyLossReached()
        {
            // Refresh the daily baseline only at the UTC date boundary.
            // This guard is demo-only and does not authorize live execution.
            var todayUtc = Server.TimeInUtc.Date;
            if (todayUtc != _riskDayUtc)
            {
                _riskDayUtc = todayUtc;
                _sessionStartEquity = Account.Equity;
                _consecutiveLosses = 0;
            }
            // Fail closed if the broker/account feed is non-finite or the equity baseline is unusable.
            if (!IsFinitePositive(Account.Equity) || !IsFinitePositive(_sessionStartEquity) ||
                !IsFinitePositive(DailyLossStopPercent) || DailyLossStopPercent > 10)
                return true;
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
