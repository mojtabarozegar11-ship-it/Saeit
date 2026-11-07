# MojTrade Demo cBot

This cBot is intentionally demo-only. It stops immediately when attached to a live account.

Short-term strategies:
- EMA 9/21 crossover
- RSI pullback with EMA trend filter
- Donchian-style breakout
- ATR-based stop-loss and reward/risk take-profit
- Maximum spread filter
- Multiple independent positions per symbol, capped by Max Open Trades / Symbol (default 3)

Recommended demo setup:
- Account: LiteFinance cTrader demo
- Symbols: BTCUSD and ETHUSD, one cBot instance per symbol
- Timeframes: 1 minute, 5 minutes or 10 minutes
- Volume: 1,000 units initially
- Keep all three strategies enabled for the first comparison
- No live account activation

Important:
- The cBot opens trades only when a completed candle produces a signal.
- On hedging accounts, independent strategy positions can remain separate.
- On netting accounts, the broker may aggregate positions for the same symbol.
- The bot does not close existing positions when stopped.
- This is a demo testing bot; profitability is not guaranteed.

Before starting:
1. Compile the cBot in cTrader Algo.
2. Attach it only to the demo account.
3. Start one cloud instance per symbol.
4. Confirm the journal reports DEMO account.
5. Verify the first orders, stop-loss and take-profit.
6. Stop the instance if unexpected behaviour occurs.

The bot uses no external HTTP calls or file access and is designed for cTrader Cloud.
