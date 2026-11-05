# MojTrade AI — Three-site read-only integration (5 November 2026)

## Decision and proven repository findings

- Three interfaces use the same proposed source: `https://mojplaywin.com/api/mojtrade/v1/public/`.
  1. Zahra static site (`/zahra$$/`, `templates/zahra/index.html`)
  2. MojPlayWin `ventures/currency-crypto/` (`core/templates/mojplaywin/section.html`)
  3. Zomorod Melal `/economy/` (`core/templates/core/platform_page.html`)
- The Zahra signal currently on the page is explicitly an **illustrative demo**, not evidence of a live signal feed.
- `core/economic_master_agent.py` is a business orchestrator whose financial actions are gated; `core/autonomous_external_trade.py` concerns trade *email*, not exchange orders.
- The F41 factory agent and single-product factory are completely outside the new trading scope. Neither is repurposed.
- Code paths were verified in the repository. No live VPS/cPanel deployment, exchange permission, live market stream, public signal or trading transaction is claimed here.

## Control plane and data flow

1. Independent *MojTrade VPS* service (future): market-specific read-only adapters (crypto, FX, shares, commodities, indices, bonds, funds) -> provenance and quality gates -> deterministic analysis and scenario/risk checks -> approved research payload. No market adapter is represented as connected until genuinely verified.
2. Independent, versioned payload: `schema_version`, `generated_at`, `expires_at`, `source=mojtrade-vps`, `signals[]`; every signal has a unique ID, asset class, instrument, timeframe, stance, observation time, method, and data-source reference.
3. `scripts/mojtrade_sign_feed.py` signs the **existing** research payload using `MOJTRADE_PUBLIC_FEED_HMAC_KEY`, writing an atomic 0600 file in a private directory. It does not manufacture research or call a broker.
4. The existing authorized VPS-to-cPanel transfer route may copy the signed file into the separately configured private file path on the MojPlayWin app host. The key must never enter GitHub, browser code, public HTML, logs or document root.
5. The MojPlayWin Django `GET /api/mojtrade/v1/public/` validates an HMAC envelope, schema and expiry, then returns **no signals** unless `MOJTRADE_PUBLICATION_ENABLED=true` is separately approved and configured. Other origins are allowed only for the Zomorod Melal and MojPlayWin domains, with no credentials and no cache.
6. All three site panels use the same immutable read-only endpoint; they do not possess broker credentials or trading authority. Failure to fetch, stale data, bad signatures, or absent approval yield explicit offline/disabled status.

## Runtime configuration (not yet applied)

Configure on the MojPlayWin site app host only after a separate deployment approval:

```
MOJTRADE_PUBLIC_FEED_PATH=/a/private/non-web-directory/mojtrade-public.json
MOJTRADE_PUBLIC_FEED_HMAC_KEY=<unique long random secret stored privately>
MOJTRADE_PUBLICATION_ENABLED=false
```

`false` is the safe default. The literal paths and secrets must be resolved by the operator on the actual host; the example above is **not** a command to run. Deployment of the Django endpoint, static JS and the Zahra static file must be coordinated with all current production release guards, followed by verifying the endpoint's status and each of the three pages independently.

## Trading scope and blockers

- Current scope: cross-site *read-only research publication mechanism*. **No signal engine, live market data adapter, broker order implementation, paper-trade executor, or market feed is declared operational by this change.**
- Target full architecture: market adapters -> normalized candles/quotes (market schedule, timezone and provenance) -> reproducible strategy -> pre-trade risk gate -> paper execution -> reconciliation and measured net P&L -> owner review -> separately controlled trading service. Actual orders are prohibited until distinct permissions, exchange compatibility and capital/loss limits are verified.
- For all markets, paid data licenses and exchange eligibility must be assessed individually. An asset class being in the schema does not mean it has live or real-time licensed data.
- Full public recommendations/subscriptions require a separate review of financial-promotion and investment-advice rules and documented owner approval. A static widget or good backtest is not such approval.
- No expense, purchase, transfer, order, email, or production modification is authorized or triggered by this repository-only implementation.

## Acceptance criteria

1. Endpoint responds with no signals and `live_trading_enabled=false` when unconfigured.
2. Valid HMAC feed is still private by default.
3. Modified or expired feeds fail closed.
4. Only explicitly approved read-only signals can appear to the three intended user interfaces.
5. Unrelated MojPlayWin pages and the factory remain unchanged.
6. Site and API smoke checks must be done *on the live deployments* before claiming all three connections operational.
