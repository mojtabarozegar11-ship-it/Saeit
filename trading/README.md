# MojTrade QuantumScalp v2 — Demo Only

This is a short-term multi-strategy cBot for cTrader Cloud. It is locked to demo accounts and stops immediately if Account.IsLive is true.

## Major engine

- EMA 9/21 signal module
- RSI pullback module
- Donchian-style breakout module
- 15-minute higher-timeframe EMA trend confirmation
- ATR-adaptive stop-loss and reward/risk take-profit
- Equity-based risk sizing instead of blind fixed volume
- Maximum volume cap
- Maximum three independent positions per symbol by default
- Per-entry cooldown
- Maximum spread filter
- Daily loss circuit breaker
- Consecutive-loss circuit breaker
- Automatic break-even protection
- Automatic trailing stop
- Separate labels and accounting for each strategy
- No external HTTP calls, plugins or file dependencies; designed for cTrader Cloud

## Recommended demo deployment

- Account: LiteFinance cTrader demo
- Symbols: BTCUSD and ETHUSD
- One Cloud instance per symbol
- Chart timeframe: 1 minute, 5 minutes or 10 minutes
- Risk per trade: 0.25% of equity
- Maximum open trades per symbol: 3
- Maximum daily loss: 2%
- Maximum consecutive losses: 3

The bot can attempt several independent entries on the same completed candle when different modules agree. The broker account mode controls whether positions remain separate (hedging) or are aggregated (netting).

## Required validation

1. Compile the source in cTrader Algo.
2. Attach it only to the demo account.
3. Start one cloud instance per symbol.
4. Confirm the journal reports DEMO ONLY.
5. Verify spread, risk sizing, stop-loss, take-profit and position count.
6. Stop the instance if any unexpected behaviour occurs.

The bot does not close existing positions when stopped. Profitability is not guaranteed; this is a guarded demo-testing engine.
