# mojtaba.bot.ai — Canonical Trading Core (Demo Only)

This document describes the canonical trading core of mojtaba.bot.ai. QuantumScalp capabilities are absorbed into trading/MojTradeOmegaXDemoBot.cs. The legacy source is retained only until compile, demo verification, backup and owner-approved retirement. Live accounts are permanently rejected.

## Canonical ownership and activation gate

- Canonical bot: `mojtaba.bot.ai`
- Canonical execution source: `trading/MojTradeOmegaXDemoBot.cs`
- Independent trader activation: forbidden
- Demo activation: blocked until cTrader compile, backtest, risk checks and owner-gated verification pass
- Live trading: permanently locked
- Legacy root `trading/MojTradeDemoBot.cs`: retained for rollback evidence; do not activate independently

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
- Daily loss circuit breaker blocks new entries; it does not forcibly close existing positions
- Consecutive-loss circuit breaker
- Automatic break-even protection
- Automatic trailing stop
- Unhandled runtime exceptions stop the canonical cBot fail-closed; existing positions are not forcibly closed
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

## Canonical source boundary

The one deployable package name is `Mojtaba.Bot.Ai.algo` from `Mojtaba.Bot.Ai.csproj`. This source is a component of `mojtaba.bot.ai`, not an independently branded agent. The included Python research backtest is narrower than the full 3-strategy cBot and does not independently validate its behavior. Code integration precedes manual Build, historical data review, demo testing and any release decision. No real account execution is authorized.
