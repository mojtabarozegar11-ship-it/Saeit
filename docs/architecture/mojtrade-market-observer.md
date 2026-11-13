# MojTrade independent market observer — safe integration

## Delivered scope

- Read-only collection of **actual** hourly BTC-USD and ETH-USD candles from Coinbase Exchange's public API, with Bitstamp's unauthenticated OHLC endpoint as the first fallback, followed by Kraken Spot OHLC and Bitfinex public-candle fallbacks. The separate Binance BTCUSDT/ETHUSDT parser is **excluded from the active USD-quote fallback chain**: its prices are quoted in USDT, not USD, and publishing them as BTC/USD or ETH/USD would misrepresent the market. Future USDT support requires an explicit schema and matching downstream consumer. Each emitted research observation identifies the provider actually used; a provider failure never results in invented prices.
- Uses only finished hourly candles; rejects data gaps, duplicate or invalid prices, and stale observations.
- Calculates reproducible SMA20/SMA50/momentum10 *research watch states*; these are **not** verified profitable strategies or personalized recommendations.
- Emits exactly the schema required by the separate signed-feed interface in PR #1892 (`schema_version=1`, `source=mojtrade-vps`, `signals[]`). The output is private, atomically replaced, and expires in 90 minutes.
- No API credentials, broker adapter, order endpoint, payment, wallet access or executable trade action exists in this module.
- Fails without replacing the last good payload if the provider is unavailable; downstream feeds have an expiry guard and must not quietly publish stale data.

## Read-only consumption path

`scripts/mojtrade_consume_observation.py` is the downstream research consumer. It reads the private observation, rejects expired/future payloads, validates the schema, provider, symbols, timeframe and research stance, and atomically writes a private report. The report explicitly contains `action=research_only`, `execution=disabled` and `orders=0`. It never places orders, contacts a broker, sends email or changes the source observation.

## Canonical master-bot research review (new capability)

The **existing** `economic-master-agent` (`Mojtaba.bot.ai`), not a second bot,
can execute a queued `income_mojtrade_research_review` task via its normal
`ToolGateway`, `TaskRuntime` and audit ledger. The seeder grants this low-risk
capability only to the existing master, not to factory/specialist agents.
This adds **no new cron**, daemon, market-data fetch, broker connector or live
trading permission. An explicit queued, correctly authorized task is required.

The review reads exactly
`~/factory-runtime/private/mojtrade/validated-payload.json`, with no
caller-controlled pathname, enforces 0700 private directory/0600-style file
permissions, no file symlinks/hardlinks, 96 KB max, immutable read snapshot
consistency, the existing consumer's schema/provider/market validation,
at most 90-minute source validity, and completed candle freshness within 3h.
Missing/stale/untrusted evidence is an explicit failed task, never invented
signals. No source file is modified.

The output records SHA-256 provenance, source, symbol, directional *watch*
classification, and **zero** independently measured forward-outcome or
backtest samples. Win rate and independently verified P&L are **null**;
orders=0, execution=disabled, publication and delivery=false. Task completion
verifies that this bounded private audit occurred, **not** the strategy's
predictive accuracy, profitability or live VPS installation.
A real performance score requires independently sourced future market closes,
a clearly defined entry/exit and fee/slippage model, sample-size tracking,
and separate trade-execution approvals.

## Independent VPS execution path

1. Provision a dedicated unprivileged service account and a *private* directory (permissions 0700) outside any site document root, e.g. `/var/lib/mojtrade/private`.
2. On the VPS, with Python 3.11 or newer and outbound HTTPS to the public market-data endpoints (`api.exchange.coinbase.com`, `www.bitstamp.net` and `data-api.binance.vision`), run:

   `python3 scripts/mojtrade_observe_market.py --output /var/lib/mojtrade/private/validated-payload.json`

3. Inspect the exit status and JSON. The success message confirms **only** that the configured market-source responses passed basic structure and freshness checks, not execution on a broker or realized P&L.
4. On the existing `githubops` VPS runtime, the supported manual installation route is `.github/workflows/mojtrade-vps-observer-activate.yml` using the previously pinned SSH fingerprint. It stages only the observer and `deploy/install_mojtrade_observer_vps.sh` under `~/factory-runtime/operations/mojtrade`, validates a **real** upstream candle fetch, then adds exactly one hourly cron entry. No cron is changed if source validation fails. It stores output in `~/factory-runtime/private/mojtrade` and writes a private `activation-receipt.json` containing the observer and payload SHA-256 values. The receipt is the minimum evidence for a later read-only runtime audit; its existence alone does not prove ongoing hourly health. It never touches the database, factory cron or master-agent cron.
5. The independent systemd templates are an **alternative for a VPS with a dedicated `mojtrade` user and root-managed systemd**; they are not the install route for the existing `githubops` VPS.
6. The separately reviewed `scripts/mojtrade_sign_feed.py` (PR #1892) can sign the private payload with an environment-injected HMAC key. Moving that signed feed to cPanel and enabling public signals are **separate, not yet authorized** actions. `MOJTRADE_PUBLICATION_ENABLED=false` must remain the default.

## Release blocks

- **No VPS installation has been performed by this change.** Confirm actual outbound HTTPS and runtime service/timer status on VPS before claiming operation.
- **No live trades.** Real order execution requires a distinct integration with a named broker, exchange eligibility, withdrawal-disabled credentials, limits, independent reconciliation, and the owner's transaction-level approval.
- No financial viability claim without forward performance, fees, slippage, execution records, and independently reconciled net P&L.
- This observer covers two cryptocurrency markets only. Forex, securities, commodities, bonds and funds remain unconnected; do not present them as operational market data.
- If both official APIs return incomplete data or fail, the proper outcome is a visible data-quality failure, not a fabricated signal. This includes an explicit short HTTP/network failure classification in the private installation log.

Provider reference: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles

Bitstamp public OHLC reference: https://www.bitstamp.net/api/

Binance public market-data reference: https://developers.binance.com/en/docs/products/spot/rest-api

Fallback provider reference: https://docs.kraken.com/api-reference/market-data/get-ohlc-data

Third provider reference: https://docs.bitfinex.com/reference/rest-public-candles
