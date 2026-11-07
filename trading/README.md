# MojTrade Demo cBot

This cBot is intentionally demo-only. It stops immediately when attached to a live account.

Strategy:
- EMA 20/50 crossover on the selected symbol and timeframe
- ATR-based stop-loss
- 1.5:1 take-profit target by default
- Fixed volume of 1,000 units by default
- Maximum spread filter
- One open position per symbol and bot label

Default test settings:
- Account: LiteFinance cTrader demo
- Symbol: BTCUSD or ETHUSD
- Timeframe: 1 hour
- Volume: 1,000 units
- No live account activation
- No external HTTP calls or file access; compatible with cTrader Cloud requirements

Before starting:
1. Compile the cBot in cTrader Algo.
2. Attach it only to the demo account.
3. Start one cloud instance.
4. Confirm the journal reports DEMO account.
5. Stop the instance if unexpected behaviour occurs.

The bot does not close existing positions when stopped.
