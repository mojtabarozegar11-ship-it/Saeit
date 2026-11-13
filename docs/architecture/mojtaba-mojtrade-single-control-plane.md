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

## Demo restart, order idempotency and protective-fill gate (review branch)

Official cTrader Algo APIs expose `History.FindAll(label)`,
`HistoricalTrade.ClosingTime` / `NetProfit` / `Comment`, and
`TradeResult.Position` plus position-side `StopLoss` / `TakeProfit`.
The DEMO-only Omega X source now uses these to close three gaps:

1. **Risk cannot be reset merely by restarting a cBot.** Each
   `DailyLossReached` call sums the account's **historical same-UTC-day**
   closed P&L to derive a baseline from `Account.Balance`; the consecutive
   loss count is rebuilt in closing-time order from *all symbols* sharing
   the Omega X label. If history or numeric inputs cannot be read, new
   orders are blocked. This is still a DEMO approximation: incomplete
   broker history and same-day deposits/withdrawals must be reconciled.
2. **One closed candle, one attempted order per instance.** A stable candle
   identity is passed in the supported cTrader market-order `comment`
   argument and checked against labelled open positions and closed history
   before another attempt. Local attempts are reserved BEFORE dispatch.
   A rejected/ambiguous response locks the instance pending reconciliation.
   Broker comment retention and concurrent instance races remain
   unresolved release blockers; this is NOT distributed exactly-once.
3. **Reject missing protective fills.** After a successful DEMO order
   response, a missing position receipt or missing broker-confirmed SL/TP
   sets a reconciliation hold. A position without protection triggers one
   DEMO-only closing attempt; a failed close is never presented as success.

These edits do NOT execute trades now. The source must compile against
the pinned official cTrader API and pass existing regressions before
a broker-connected DEMO forward test is considered. Any real account
remains permanently rejected and owner authorization, reconciled demo
fills, single-commander execution and costed OOS evidence remain required.

## Operational proof console and receipt binding (review branch)

The same Django control plane now includes a read-only, authenticated
owner-only `GET /api/mojtrade/readiness/` endpoint. It does not start an
agent, place orders, send messages, publish a signal, or generate a
financial transaction. Ordinary users, anonymous visitors and staff
without active superuser authority are denied. Responses are private,
noncacheable and noindex.

The operator sees distinct **evidence gates**, never one misleading
"one bot = 100%" value:

- Is the canonical `mojtaba-bot-ai` owner active in this database?
- Is the latest canonical BTC/USD and ETH/USD **research-watch** receipt
  fresh, with an exact matching audit receipt and source digest?
- Is a local cTrader DEMO closed-deals log recorded as a canonical
  task with its own audit receipt?
- Is there a corresponding DEMO statement task whose **unverified**
  source log SHA-256, account alias and symbol match that exact demo log?
- Is a broker account independently authenticated, connected to
  a canonical approved order controller, and evidenced by real broker
  executions? **False until independently proven.**
- Is a real site/subscriber signal delivered and receipt-authenticated?
  **False until independently proven.**
- Is a single live master/runtime cutover verified, real funds authorized,
  or real settled revenue evidenced? **False until independently proven.**

Two matching local files are explicitly labelled
`local_two_unverified_demo_exports_matched_to_same_log`, NOT an
authenticated broker statement. The overall operational completion
percentage stays `null` without a full live runtime and independent
external-delivery census.

The private watch endpoint/export now also requires exactly one matching
`mojtrade_private_research_ingested` `AuditLog` record with the same
canonical AgentTask ID, owner row, source hash, two observations and no
orders. Missing, duplicate, tampered or mismatched receipts fail closed,
even if the stored draft JSON otherwise looks well-formed.

**Remaining blockers to 100% production:** working authorized broker
connection, broker-attested DEMO fills and costs, multi-instance/external
scheduler coordination, signed canonical order authorization, authenticated
site delivery and per-channel permission, tested production deployment,
and externally reconciled economics. No live trade or paid publication
is authorized by a successful offline test.

## Owner-only previews for 17 finance brand routes

The existing brand registry contains **17** distinct brand slugs.
A new canonical Django read-only endpoint provides exactly one
**private** market-watch preview per brand and language:

`GET /api/mojtrade/brand-preview/<brand>/<locale>/`

The `brand` segment is validated against the existing registry and
`locale` is restricted to `fa`, `en`, or `ar`. All 17 × 3 = **51**
brand/language combinations use one revalidated `mojtaba-bot-ai`
market research receipt (no independent 17-brand bots). The response
includes a language-specific watch text, content-addressed hash,
source timestamp and expiry, and canonical source identifier.
Access requires an active superuser (not just staff). Responses are
`no-store`, `noindex`, `X-Frame-Options: DENY`. Expired or altered
source tasks never fall back to an earlier cached signal.

**Not publication:** these are owner previews, not the existing
public `/<brand>/market-signals/` pages or paid subscribers.
No account state, charge, order, signal delivery or commercial
entitlement changes. Opening the page without active owner login
reveals no private preview. A future authorized site publisher
would need its own real subscriber access, consent, copy review,
trusted market data, external delivery receipt and no stale replay.

## cTrader Cloud execution facts and release blocker

From cTrader's official Cloud execution documentation (read in
November 2026), a DEMO account normally allows **one concurrent
cloud cBot instance** (broker limits may differ); a DEMO cloud
instance runs for **up to seven days** before stopping. The official
cTrader LocalStorage reference expressly states that Cloud LocalStorage
values are **in-memory for the current run only**, not persisted to
disk. Consequently:

- Three independent demo-cloud cBots per account are NOT a feasible
  default plan. Do not assert that desktop Type/Device LocalStorage
  is an atomic, persistent or Cloud-compatible lock.
- Existing per-candle broker-history comments provide only
  **best-effort** replay detection; they cannot guarantee exactly-once
  execution when two instances race or when the broker loses comments.
- To pursue uninterrupted one-bot demo execution, a single multi-symbol
  execution adapter or a demonstrably unique supported host must
  be implemented and broker-validated, with separately verified
  external scheduling/failover and a durable server-side command ledger.
  No such evidence has been gathered by these offline code changes.
- Broker-managed SL/TP and externally reconciled position accounting
  remain necessary even if the cBot/cloud process stops after seven days.

Official sources:
https://help.ctrader.com/ctrader-algo/synchronisation/
https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/

## Account-wide DEMO portfolio risk admission (review branch)

The earlier cTrader DEMO engine limited open positions **only by the
`MojTrade-OMEGA-X-DEMO` label** and sized each proposed order at its
individual risk percentage. A different manual trade or another label
could exhaust the same account risk budget unnoticed.

The current `MojTradeOmegaXDemoBot` now gates every proposed order on
**all open positions** on that DEMO account, including other labels and
symbols:

- Count total account positions against `MaxPositions` (1–3), not
  just labelled Omega X positions.
- Hold new market orders whenever **any pending order** is present on
  the account; a pending fill could otherwise breach the shared cap.
- Refuse to add exposure if any open position is missing its
  broker-confirmed SL or TP, or if numeric/instrument data are invalid.
- Estimate open-stop risk from the position's own symbol and SL
  distance using official cTrader `Symbol.AmountRisked`.
- Estimate the proposed stop risk and margin using
  `Symbol.AmountRisked` and `Symbol.GetEstimatedMargin`.
- Require finite positive equity and available margin, no leverage
  shortfall, and total *estimated* at-risk amount (including new order)
  ≤ `AggregateStopRiskPercent` of current equity. The parameter
  defaults to **1%**, cannot be set above 1%, and is separate from
  the 0.25% default per-order cap.
- Fail closed if the broker or account objects cannot provide the
  required values. This admission check is before any DEMO
  `ExecuteMarketOrder` call; real accounts are still rejected and
  DEMO trading remains disabled by default.

**Limits:** This is a conservative risk *estimate*, not a guarantee of
filled stop price, negative-balance protection or profit. Commissions,
slippage, price gaps, currency conversions and multiple concurrent
cBots may cause realized losses outside the estimate. The check
cannot prevent two processes from racing between observation and
order. The **single-executor broker-verified cutover** remains
mandatory before production approval.

Official API reference:
https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/

## 2026-11-13 official CLI command verification and JSON trust boundary

Spotware's official `CLI-references` documents all four preflight verbs
(`accounts`, `cbots`, `positions`, `orders`) and their expected
authentication mode. `accounts` uses batch `--ctid --pwd-file`;
`cbots`, `positions`, `orders` support interactive quick mode `-q`
with `--pwd-file`, and `--account` and `--broker` are supported global
selectors. This verifies command syntax **only**, not installed binary,
broker authorization or the actual response payload schema.

**Critical unresolved dependency:** the public CLI command reference
does not provide a version-pinned field-by-field JSON schema for these
four responses. The offline regression tests use intentionally synthetic
JSON structures. The real CLI may emit different field names or wrapper
objects; an unrecognized format MUST produce a blocked preflight, not a
coerced approval. Exact output contracts and account demo markers
must be reconciled from the owner-authorized installed CLI on a trusted
host before accepting the preflight as an authenticated broker connection.

The preflight now explicitly refuses:

- Duplicate JSON keys, even when hidden within account rows.
- A wrapper with `success=false`, `ok=false`, nonempty `error` or
  `errors`, including when a valid-looking account list is present.
- Non-finite numeric JSON constants.
- Conflicting displayed trader logins, account IDs, broker names or
  `isLive` values. cTrader Open API distinguishes the internal
  `ctidTraderAccountId` from the displayed `traderLogin`; accepting
  one ambiguous number as both may bind the wrong account.
- Real-account, duplicate-account and missing-demo-marker cases before
  querying cBots or positions.

Official primary sources:

- https://help.ctrader.com/ctrader-cli/use-commands/
- https://github.com/spotware/CLI-references
- https://help.ctrader.com/open-api/model-messages/

## Read-only cTrader CLI demo-account preflight (new review-cycle source)

Spotware's official documentation confirms a material architectural
difference:

- **cTrader Cloud:** Algo `Http` does not send requests and the response
  is 403; Cloud `LocalStorage` is volatile between runs. A Cloud cBot
  cannot be treated as an authenticated HTTP client for the one-bot
  command ledger.
- **cTrader CLI:** A free terminal tool can run on **Linux/VPS** and
  exposes documented read-only `accounts`, `cbots`, `positions`,
  `deals` commands. It is distinct from cTrader Cloud, requires a
  cTID and private credential file, and does NOT confer authority for
  real orders. cTrader supports account- and broker-scoped CLI queries.

The new `deploy/mojtrade_ctrader_cli_preflight_readonly.py` implements
the **first no-order CLI connection gate**. Its only invocations
are the read-only `ctrader-cli accounts`, `cbots -q`, `positions -q`
and `orders -q` commands; it cannot launch/stop cBots or
create/modify/close orders. It refuses to query cBots, positions
or pending orders **unless the initial account identity is explicitly
DEMO**. The observed number of open positions and pending orders is
reported without exposing individual trade IDs or account values.
All CLI outputs remain
inside the process and are represented by SHA-256 digests in a small
redacted JSON report. Owner's cTID, raw account number, password, broker
JSON, order/position details and raw instance identifiers are
**never printed**.

A local operator must provision **two private files** in one existing
mode-0700 directory, with both files mode 0600:

```json
{
  "schema_version": 1,
  "ctid": "YOUR_CTRADER_ID",
  "demo_account": "YOUR_DEMO_ACCOUNT_NUMBER",
  "account_alias": "LITE_DEMO_1",
  "broker": "LiteFinance",
  "password_file": "ctrader-cli.pwd"
}
```

The example is a template; it is **not a credential request** and
must not be committed or pasted into chat. The password file is
plaintext for the CLI itself, and must remain on the operator-approved
private host; do not use GitHub Secrets, Actions, logs or web requests
for this gate. An owner-authorized, already-configured host can then
execute:

```bash
python3 deploy/mojtrade_ctrader_cli_preflight_readonly.py \
  --config /ABSOLUTE/PRIVATE/DIRECTORY/config.json
```

It fails closed on missing/unsafe credentials, unexpected response
schema, non-demo account, wrong broker, ambiguous account, duplicate
instance IDs or CLI failure. A completed check reports only that this
one CLI saw the selected DEMO account, a running-instance count and
an observed exposure count. It **cannot establish** that a Cloud
instance, another machine or another broker session is absent.
Counts do not prove stop protection, available margin, correct
portfolio risk or permission to place a new order. Therefore
`single_runtime_instance_independently_attested=false` and
`trading_release_authorized=false` remain **fixed**. No real credential
is available in the CI tests, which use synthetic data and a fake CLI.

Important: this probe is a **staging prerequisite** and does not yet
bind the cTrader CLI to a signed, per-order canonical task, account-wide
atomic reservation or broker-verified execution receipt. Real
capital and public signal publication remain disallowed.

Official sources:

- https://help.ctrader.com/ctrader-cli/
- https://help.ctrader.com/ctrader-cli/use-commands/
- https://help.ctrader.com/ctrader-algo/references/HTTP/Http/
- https://help.ctrader.com/ctrader-algo/references/Localstorage/LocalStorage/

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
