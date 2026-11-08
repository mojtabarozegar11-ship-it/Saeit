# MojTrade C07 — demo adapter safety gates

Status: **proposed source changes only**. This change has not been compiled by cTrader, installed on VPS, launched in cTrader, or authorized for real trading or public signal publication.

## Fixed in source

- QuantumScalp now checks `Account.IsLive` at startup, every bar/tick, and immediately before each attempted order. OMEGA X retains those locks.
- QuantumScalp daily entry stop includes broker `Account.Equity` (floating profit/loss) plus today's realized P/L; both use the UTC trading day.
- Both bots reject invalid price, risk, pip, ATR, stop, and volume data before placing demo orders.
- Both bots count positions with either MojTrade label across all symbols and deny a new entry at three existing MojTrade positions. This is a **best-effort check**, not an atomic limit across concurrently running cBots.
- Both bots inspect the returned demo position for broker-side stop-loss and take-profit; if missing, they attempt to close that demo position, log any failure, and stop. An unsuccessful emergency close still needs human attention.
- OMEGA X caps the configurable daily loss stop at 10%; demo execution is still opt-in and disabled by default.

## Remaining release blockers

1. Compile both `.cs` files against the exact cTrader version and confirm accepted API overloads.
2. Independently review in a controlled **demo-only** account the behavior of drawdown, missing quotes, partial broker responses, new UTC dates, and simultaneous strategies.
3. Design a **single persistent account-wide risk controller** before promising an atomic three-position cap or restart-resistant daily loss stops. Each adapter currently maintains an in-memory baseline; a restart can change that baseline.
4. Review fees/slippage/spread volatility, risk aggregation across unrelated positions, and the emergency-close failure path.
5. Match the reviewed source to the running build and obtain separate explicit approval before any deployment, trading switch, or public signal publication.

No VPS, cPanel, broker, wallets, databases, email, or public site changed in C07. GitHub Actions are not a permanent execution runtime. Signals, if later separately approved, must go only to specialist trading-signal platforms with matching FA/EN language.
