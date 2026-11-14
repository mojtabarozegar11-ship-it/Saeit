# Mojtaba.bot.ai — trading capability integration and identity handoff

## Authoritative identity

- The **only organizational bot identity and public-facing bot brand** is `mojtaba.bot.ai`.
- Trading is an **internal capability** of this bot, not a second independently branded bot.
- Historical labels such as `MojTrade`, `OMEGA X`, or `QuantumScalp` in file paths, signed-feed source fields, database keys, operational identifiers, and legacy deployment scripts are **technical compatibility labels**, not permission to present a separate bot.
- Do not delete or rename operational identifiers without a verified consumer/scheduler inventory and an atomic handoff; dropping them blindly can break existing data flows and erase reconciliation evidence.

## Current repository evidence (not proof of live operation)

- `scripts/mojtrade_observe_market.py` creates read-only public market research observations, does not place trades.
- `scripts/mojtrade_consume_observation.py` validates observations and writes private reports; orders and broker execution remain disabled.
- `trading/MojTradeOmegaXDemoBot.cs` and `trading/MojTradeDemoBot.cs` are cTrader adapters with existing safety constraints. They are not evidence of a unified production trading execution service.
- Historical schedules and launch scripts (for example `deploy/install_mojtrade_observer_vps.sh`) may be independent. Their actual live deployment status is unverified.
- The canonical bot registry and runtime-source inventory reside in `runtime/mojtaba_bot_disposition_sources_v1.json`. Its unknown live counts must not be converted into assumptions.

## Implemented in this change

The research consumer accepts **all five exact provider identifiers** currently emitted by the observation producer (Coinbase, Bitstamp, Binance, Kraken, Bitfinex) and preserves rejection of unknown providers. The public-wire source value `mojtrade-vps` is left unchanged for compatibility. This is a tangible pipeline defect fix, **not** a claim that live consolidation was completed.

## Required end state

1. An internal trading module is registered under canonical bot `mojtaba.bot.ai`, with one owner/routing identity, unified permissions, idempotency, audit logging, and income accounting.
2. The existing observer, signal consumer, strategy engine, broker adapters and any trade reconciler become capability endpoints governed by the canonical orchestration boundary.
3. The canonical scheduler owns the trading module. Independent legacy schedules are inventoried and retired only after completion, replay, and reconciliation evidence for queued tasks and receipts.
4. Customer-facing endpoints, dashboards, documentation and commerce expose **only** `mojtaba.bot.ai` as the robot. Technical strategy labels may remain internal.
5. No live broker orders, capital movement, paid service, infrastructure deployment, or live scheduler retirement is implied by this branch. Preserve current safety restrictions until environment, legal eligibility and transaction-specific controls are verified.
6. Obtain verified VPS and cPanel runtime evidence. Conduct a cutover with rollback and recorded post-cutover success, then remove obsolete identities only after compatibility consumers are migrated.

## Prop-firm project boundary

A future proprietary trading website is a **distinct commercial service**, not a separate AI robot. Its evaluation account rules, simulation disclosures, payouts, anti-fraud controls, eligibility and contractual/regulatory requirements will be specified by the owner before the commercial flow is implemented. It can later call trading/risk/audit capabilities of `mojtaba.bot.ai` through a restricted internal API, without introducing another bot.

**Status:** repository remediation staged in a draft PR; unified live runtime not attested; no deployment, payments, emails, trading or deletion performed.
