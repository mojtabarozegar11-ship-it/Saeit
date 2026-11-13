# Mojtaba.bot.ai × MojTrade — single control plane, staged execution authority

## Non-negotiable system invariant

There is **one canonical Django task owner** (`mojtaba-bot-ai`) and one
auditable risk/authorization plane. Specialist code may remain in C# (cTrader)
or Python, but no second AI commander may authorize spending, signal
publication, service retirement, or production order placement.

**Do not confuse source-level integration, unit-test results, market observation,
broker account connection, demo fills, or verified real profits.**
Each has separate evidence and a separate release gate.

## Implemented in the draft branch

1. `mojtrade_observation_ingest` is a bounded low-risk capability seeded
   onto `mojtaba-bot-ai`, with no `trade`, `payment`, `deploy`, or
   `withdraw` capability.
2. `mojtrade_research_cycle` is an operator-invoked Django command, not a
   second scheduler/bot. It reads only `MOJTRADE_PRIVATE_DIR/validated-payload.json`.
3. File metadata and signal payload are fail-closed: private mode, symlink
   rejection, fixed max size, allowlisted source and USD symbols, trusted
   method and 24-hex signal IDs, expiry and candle freshness.
4. The canonical agent row is locked and the original source SHA-256 is
   deduplicated before task creation. One `AgentTask` is claimed and
   completed using `TaskRuntime`, with a separate `AuditLog` receipt.
5. Replaying the same snapshot is idempotent. A pending/blocked duplicate
   requires manual reconciliation. The economic worker ignores **only**
   the registered exact MojTrade research pair; mismatched/unknown tasks
   remain visible to audit.
6. Execution is **always disabled**; reported orders and realized revenue
   are zero/unverified. There are no external broker calls, fees,
   network market fetches, token spends, or public signal writes in this adapter.
7. `mojtrade_strategy_risk.py` now generates a versioned, deterministic
   research-only strategy classification and SHA-256 decision digest for
   two verified USD-quoted instruments. `watch_buy` and `watch_sell`
   mean **monitor only**; they never become executable trade intent.
   Its report is stored on the same canonical `AgentTask` receipt.
8. The pure `assess_account_risk_budget` calculates advisory loss
   capacity with 0.25% equity per task, 2% maximum daily loss, and 1%
   aggregate open-stop risk **only after receiving reconciled account
   currency inputs**. It rejects NaN, unbounded, missing, float or
   out-of-range values, and always returns `execution_authorized=false`
   and `order_quantity=null`. It does not claim account connection,
   stop distance, spread, margin, volume sizing, OOS success, or P&L.

The existing public-market observer still owns upstream data fetching.
Its cron/systemd status and actual VPS runtime are **not proven** by draft
code or CI. `MOJTRADE_PRIVATE_DIR` defaults to unset and must be
configured only with an already verified private path. No automatic
installation/deployment is authorized by this work.

## Current review branch — canonical signal draft feed and demo risk hardening

The canonical `mojtrade_research_cycle` now attaches an immutable-style
`market_watch_drafts` package to the SAME completed `mojtaba-bot-ai`
AgentTask as the validated private market observation. This package:

- Derives exactly BTC/USD and ETH/USD **watch classifications** from the
  reviewed strategy digest and validated source signal identifiers.
- Binds the original source SHA-256, decision SHA-256, source observation time
  and expiry, and provides reviewed text in **fa/en/ar**.
- Keeps `publication_authorized=false`, no external delivery, zero orders,
  no executable intents, and **no fabricated entry/stop/take-profit prices**.
- Refuses expired, duplicate, direction-mismatched or manipulated sources.
- Can be atomically exported by the operator-only
  `python manage.py mojtrade_market_watch_export` to the existing
  mode-0700 `MOJTRADE_PRIVATE_DIR/market-watch-private.json` (0600).
  Export revalidates the latest canonical completed task and its saved
  digest. No new bot identity, website publication, SMS, email, trades,
  API spending or broker credentials are involved.

**This is a usable private signal-research feed, not live customer signal
service.** No public signal price, stop, target, win-rate or profit is claimed;
source is hourly *spot* market observations, not an XAUUSD broker quote.
Public publishing requires a separate authenticated subscriber/site delivery
service, per-channel owner approval, downstream receipt reconciliation and
financial/advertising rights review. Feed timestamps are not a substitute for
independent production runtime evidence.

The cTrader **demo-only** code also now guards a low-parameter negative
20-bar breakout lookback, unknown indicator values, account-wide labelled
position count, unprotected existing positions, invalid volume before
normalization, and day-based UTC loss baseline. Two independent cTrader
instances are still not atomically account-locked; their actions must be
reconciled against broker history. No real trade is enabled and this cBot is
not yet controlled by a signed order instruction from the canonical bot.

## Required work before unifying the trading engine

| Gate | Acceptance evidence | Without it |
|---|---|---|
| A. Live host census | Verifiable VPS/cPanel user, cron, process, timer, code digest and external adapters | No legacy shutdown |
| B. Data provenance | Fresh complete labeled symbols/venues, audit digest, no USD/USDT substitution | No signal/decision |
| C. Strategy engine | Versioned deterministic signals with OOS, walk-forward and realistic spread/slippage/costs | No profitability claim |
| D. Risk engine | Validated position sizing, correlated portfolio exposure, spreads, max drawdown, account currency/leverage and kill-switch | No order-intent approval |
| E. Demo execution | Explicitly identified broker/account, **demo-only** keys, idempotent client order ID, reconciliation and no duplicate orders | No production trading |
| F. Live account (separate) | Legal eligibility, verified withdrawal-disabled credentials, reconciled positions and case-specific owner approval for each allowed live risk action | No real orders |
| G. External signals | Separate per-site publication permission, language and source QA, anti-spam and authenticated delivery receipts | No public signal distribution |
| H. Handoff | Canonical receipt, zero unresolved tasks, tested rollback and stopped duplicate schedule | No independent-bot retirement |

### Canonical order intent (future, not implemented)

A versioned trade intent must carry: strategy ID, immutable signal ID,
market venue and symbol, account ID (never secrets), side, quantity,
timestamp and expiry, estimated spread/slippage, stop loss, portfolio
risk, owner grant reference when required, idempotency key and exact
broker reconciliation state. It must transition through
`proposed → risk_approved → demo_authorized → sent → acknowledged → filled/rejected/reconciled`.
A broker order is **not** a successful operation until reconciled against
broker-side receipts. Retries must never generate a new order identifier
for the same instruction.

**No live-order adapter is provided or enabled in this PR.**
No private credentials should be committed.

## Revenue verification

Trading profit is **net settled result after execution costs and account
reconciliation**, never a theoretical signal score, backtest, task count,
demo equity or public observation. Set `revenue_verified=false` and
`profit_verified=false` until this evidence exists.

## Rollback and safety

The code is review-only. The old demo cBot and market observer remain
untouched, and the source observer may coexist as a passive input.
No production deploy, scheduler cutover, legacy deletion, real trade,
external publication or financial obligation follows from a merged PR.
