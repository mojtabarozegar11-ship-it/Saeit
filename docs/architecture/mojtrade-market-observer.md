# MojTrade independent market observer — safe integration

## Delivered scope

- Read-only collection of **actual** hourly BTC-USD and ETH-USD candles from Coinbase Exchange's public API.
- Uses only finished hourly candles; rejects data gaps, duplicate or invalid prices, and stale observations.
- Calculates reproducible SMA20/SMA50/momentum10 *research watch states*; these are **not** verified profitable strategies or personalized recommendations.
- Emits exactly the schema required by the separate signed-feed interface in PR #1892 (`schema_version=1`, `source=mojtrade-vps`, `signals[]`). The output is private, atomically replaced, and expires in 90 minutes.
- No API credentials, broker adapter, order endpoint, payment, wallet access or executable trade action exists in this module.
- Fails without replacing the last good payload if the provider is unavailable; downstream feeds have an expiry guard and must not quietly publish stale data.

## Independent VPS execution path

1. Provision a dedicated unprivileged service account and a *private* directory (permissions 0700) outside any site document root, e.g. `/var/lib/mojtrade/private`.
2. On the VPS, with Python 3.11 or newer and outbound HTTPS to `api.exchange.coinbase.com`, run:

   `python3 scripts/mojtrade_observe_market.py --output /var/lib/mojtrade/private/validated-payload.json`

3. Inspect the exit status and JSON. The success message confirms **only** that the configured market-source responses passed basic structure and freshness checks, not execution on a broker or realized P&L.
4. On the existing `githubops` VPS runtime, the supported manual installation route is `.github/workflows/mojtrade-vps-observer-activate.yml` using the previously pinned SSH fingerprint. It stages only the observer and `deploy/install_mojtrade_observer_vps.sh` under `~/factory-runtime/operations/mojtrade`, validates a **real** upstream candle fetch, then adds exactly one hourly cron entry. No cron is changed if source validation fails. It stores output in `~/factory-runtime/private/mojtrade` and never touches the database, factory cron or master-agent cron.
5. The independent systemd templates are an **alternative for a VPS with a dedicated `mojtrade` user and root-managed systemd**; they are not the install route for the existing `githubops` VPS.
6. The separately reviewed `scripts/mojtrade_sign_feed.py` (PR #1892) can sign the private payload with an environment-injected HMAC key. Moving that signed feed to cPanel and enabling public signals are **separate, not yet authorized** actions. `MOJTRADE_PUBLICATION_ENABLED=false` must remain the default.

## Release blocks

- **No VPS installation has been performed by this change.** Confirm actual outbound HTTPS and runtime service/timer status on VPS before claiming operation.
- **No live trades.** Real order execution requires a distinct integration with a named broker, exchange eligibility, withdrawal-disabled credentials, limits, independent reconciliation, and the owner's transaction-level approval.
- No financial viability claim without forward performance, fees, slippage, execution records, and independently reconciled net P&L.
- This observer covers two cryptocurrency markets only. Forex, securities, commodities, bonds and funds remain unconnected; do not present them as operational market data.
- If the upstream API returns incomplete data or stops serving requests, the proper outcome is a visible data-quality failure, not a fabricated signal.

Provider reference: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
