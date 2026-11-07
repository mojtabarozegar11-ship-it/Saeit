# MojTrade OMEGA X — APEX 1300

**Institutional Adaptive Trading Architecture | Reference design and acceptance contract | 2026-11-07**

## Status and scope

- Classification: **design target / proposed architecture**, not a deployed or profitable system.
- Baseline: preserve every requirement in `trading/MojTrade_OMEGA_X_Build_Spec.md`. This document is additive and takes precedence only where it specifies stricter safety or measurable acceptance.
- Current known implementation: an early demo-only cTrader C# adapter and a separate private BTC/ETH hourly research observer; neither proves this APEX architecture operational.
- Current live-money permission: **none**. `Account.IsLive` must fail closed; no real orders, withdrawals, deposits, public signal posting, emails, paid integrations or deployment are authorized by this document.
- The central quality claim is **testable differentiation**, never guaranteed profit or unverified superiority over any vendor.
- Core architecture shall not depend on GitHub Actions at runtime. Source control and CI are release-time aids, not market-data clocks or strategy services.
- All financial or legal commitments require individual owner approval. Prefer free/open-source components without weakening security, data quality or legal compliance.

## Executive design outcome

The goal is an adaptive, multi-strategy, multi-asset **risk-first decision system** with three independent differentiators:

1. **Proof-Carrying Trade Decision (PCTD):** every entry, reduction and no-trade decision contains an immutable, replayable evidence packet and explicit model uncertainty.
2. **Global Risk Constitution (GRC):** one ledger of risk reservations across symbols, strategies, bot instances and accounts, with broker-state reconciliation; no independent bot can silently bypass aggregate caps.
3. **Execution Reality Twin (ERT):** a per-broker, per-symbol, per-session model compares hypothetical fill, quoted cost, actual demo fill, rejects and delayed recovery, then adjusts or blocks execution only after validation.

These are proposed system-level combinations, **not assertions that no competitor has analogous features**. Their comparative value must be demonstrated by a fair benchmark.

## 1. World-class baseline: comparison grounded in official documentation

| Reference system | Capabilities already documented | APEX must match | Proposed measurable differentiation |
|---|---|---|---|
| QuantConnect LEAN | Modular Alpha / Portfolio / Risk / Execution framework, multiple assets, live/backtest modes | Cross-asset research, risk and order model separation | Owner-level risk reservation across adapters/accounts plus signed decision evidence; benchmark against LEAN, not marketing claims |
| Freqtrade | Dry-run, backtesting, hyperparameter optimization, lookahead and recursive analysis | Bias testing, transparent simulation and explicit protections | Every candidate receives data-provenance and counterfactual drift reports before shadow promotion |
| Hummingbot Strategy V2 | Controllers, independent executors, multiple concurrent modular strategies | Strategy isolation and executable life-cycle states | Cross-controller capital constitution and broker execution quality arbitration |
| NautilusTrader | Event-driven message bus, shared backtest/live components, reconciliation, portfolio and risk | Deterministic playback, state reconciliation, adapter contracts | Mandatory proof packet attached to every trading decision plus signed causal replay receipts |
| cTrader Algo | Native cBots, demo account execution, backtesting and broker order events | Broker-specific C# execution and protected orders | One native demo execution core consuming only validated, versioned and signed strategy releases |

Official references: https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview ; https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control ; https://www.freqtrade.io/en/stable/lookahead-analysis/ ; https://hummingbot.org/strategies/v2-strategies/ ; https://nautilustrader.io/docs/latest/concepts/architecture/ ; https://help.ctrader.com/ctrader-algo/documentation/cbots/cbot-bar-events/ .

No blanket ranking of “world’s best bot” is scientifically meaningful without matching asset, venue, capital, period, fees, slippage and risk budget. APEX passes a competitive claim only on preregistered matched datasets and an independent reproducible evaluation.

## 2. Thirteen score pillars: 1000-point baseline plus 300-point advantage contract

| Pillar | Design acceptance, 0–100 each |
|---|---|
| P01 Market data integrity | Multi-source lineage, latency, timestamps, staleness and quarantine |
| P02 Macro and event intelligence | Event calendar, surprise/impact, blackout and delayed reaction |
| P03 Strategy alpha factory | Distinct economic hypotheses, independent entry/exit contracts and de-duplication |
| P04 Portfolio and capital | Cross-instance reservations, correlated exposures, drawdown and CVaR |
| P05 Execution engineering | Broker adapters, idempotence, partial fills, slippage, reconciliation |
| P06 Controlled evolution | Versioned genomes, locked validation, Champion/Challenger, rollback |
| P07 Market memory | Concept drift, per-session attribution, model/calibration monitoring |
| P08 Simulation and stress | Event replay, cost/latency injection, partial fills and outage scenarios |
| P09 Security and reliable operations | Secrets, audit logs, monitoring, isolated services, recovery |
| P10 Management, accounting and signals | Net-P&L reconciliation, Persian dashboard, lawful language-routed signal publication |
| A11 Proof-carrying decisions | Evidence completeness, replay equality, cryptographic integrity |
| A12 Global risk constitution | Race-free cross-bot/cross-account risk holds and broker reconciliation |
| A13 Execution reality twin | Cost forecast calibration, broker/session drift detection, observed improvement |

**Maximum design-and-acceptance rubric = 1300.** A documented idea earns at most 25/100 for its pillar; implementing tested contracts can reach 70/100; the remaining 30 points require independent operational evidence. The label “1300/1300 delivered” is prohibited until every acceptance artifact exists. In the previous 1000-point scale, a number greater than 1000 is impossible; the additional 300 points are an explicitly separate advantage criterion.

## 3. Component topology and execution boundaries

1. `DataFabric` — market ticks/bars, economic calendar and provenance; private storage.
2. `FeatureAndRegimeEngine` — normalized time-aware features and uncertainty, **without access to future data**.
3. `StrategyWorkers` — isolated signed versions that propose intentions, never issue broker orders.
4. `EvidenceArbiter` — consensus, duplicate/conflict detection, expected value after cost and no-trade gate.
5. `PortfolioRiskCoordinator` — durable serialized risk holds, account-level loss budgets and correlation stress.
6. `ExecutionRealityTwin` — estimate fill/cost risk using broker/session-specific, demonstrably calibrated observations.
7. `cTraderDemoExecutionAdapter` — last independent policy check, explicit broker state machine and safe SL/TP confirmation.
8. `OrderAndDecisionEventStore` — immutable decision/order/fill/fee journal; UTC timestamps and monotonic event sequence.
9. `ResearchAndEvolutionLab` — reproduce, train, validate and shadow-run candidate versions, no order privileges.
10. `OwnerConsole` — Persian read-only review as default; owner-approved configuration management and emergency halt.
11. `SignalPublicationGateway` — disabled by default; only dedicated trading-signal sites, Persian signals to Persian destinations and English to English, with separate signed releases and approvals.

Trust boundaries: Research → signed `StrategyRelease` → policy validator → demo execution; execution events → immutable audit → research. The research process cannot write broker commands or modify live-risk limits. The adapter does not accept model text as an executable instruction. Untrusted market/news data cannot carry tool commands.

Bridge compatibility must be proven against official cTrader and the named broker API. If a secure verified transport from VPS to cTrader is unavailable, independent cTrader-only demo mode remains allowed and the bridge is **blocked**, not simulated as working. Do not weaken `AccessRights` or publish private data to solve connectivity.

## 4. Required data contracts

All messages use UTC ISO-8601 timestamps, integer sequence, schema version, producer version, SHA-256 digest, source identity and a trace ID. Reject duplicate IDs, future timestamps beyond measured clock skew, incompatible precision and untrusted producers.

**MarketObservation v2**: `source_id`, `venue`, `symbol`, `asset_class`, `bid`, `ask`, `last`, `ohlcv`, `bar_close_at`, `observed_at`, `received_at`, `quality_flags[]`, `freshness_ms`, `spread_bps`, `provider_latency_ms`, `calendar_context_id?`. Bid/ask and tradeable quote cannot be silently replaced by candle close.

**StrategyCandidate v2**: `strategy_id`, `strategy_version`, `genome_hash`, `symbol`, `timeframe`, `side`, `entry_type`, `entry_window`, `max_hold_seconds`, `stop_distance`, `take_policy`, `signal_score`, `confidence_interval`, `regime_id`, `cost_estimate_id`, `feature_snapshot_hash`, `reasons[]`, `invalidation[]`, `expires_at`.

**DecisionEvidence v2**: `decision_id`, `candidate_ids[]`, `data_provenance_hashes[]`, `model_versions[]`, `portfolio_snapshot_version`, `broker_snapshot_version`, `risk_envelope_hash`, `counterfactual_ids[]`, `forecast_cost`, `uncertainty`, `verdict` (ALLOW/REDUCE/REJECT), `rejection_reason`, `decision_at`, `signed_digest`.

**RiskReservation v2**: `reservation_id`, `account_id`, `strategy_id`, `cluster_id`, `max_loss_minor`, `currency`, `expires_at`, `portfolio_version`, `order_intent_id`, `state` (HELD/CONSUMED/RELEASED/QUARANTINED). Atomic compare-and-swap prevents two independent workers consuming the same risk budget.

**OrderLifecycle v2**: `intent_id`, `idempotency_key`, `client_order_id`, `broker_order_id?`, `state`, `sent_at?`, `ack_at?`, `fill_events[]`, `remaining_quantity`, `stop_status`, `take_status`, `reconciliation_status`, `error_class`, `last_broker_seen_at`.

**BrokerCostObservation v2**: `broker_id`, `symbol`, `session`, `intended_price`, `quote_age_ms`, `filled_price?`, `spread`, `commission`, `slippage`, `order_latency_ms`, `partial_fill_ratio`, `reject_class?`, `currency_conversion`, `confidence_interval`.

**ChampionRelease v2**: `release_hash`, `strategy_hashes[]`, `dataset_manifest`, `split_plan_hash`, `cost_model_version`, `simulation_report_hash`, `shadow_report_hash`, `safety_contract_hash`, `approved_mode`, `effective_at`, `rollback_hash`. Only DEMO or SHADOW releases allowed by current policy.

## 5. Data-quality fabric and causality guard

- Free data may cover only supported markets/timeframes; no invented tick/order-book depth. Mark missing inputs as `unavailable`; do not substitute synthetic liquidity.
- Normalize sessions, daylight saving, symbol point/pip value, contract specifications, holidays and macro release timestamps.
- Cross-check independent providers with tolerance learned from actual venue spreads, not a hard-coded universal price gap; quarantine on material disagreement.
- Track `event_time`, `ingestion_time`, `availability_time` and revision time to prevent asynchronous news/revised economic data leaking into historical decisions.
- Use as-of joins; embargo around train/test partitions; persist the exact input data hash of every simulated decision.
- Gold-specific features: XAU/USD, actual available USD proxy, yields/real-rate proxy, scheduled high-impact releases, London/NY overlap and broker spread shocks. If a proxy is missing, the relevant macro-dependent strategy is disabled.
- BTC/ETH-specific features: spot reference versus broker quote, weekend liquidity regime, funding only if contract-appropriate, cross-asset divergence and tick-size/volume constraints.
- No model may use unlicensed private data or bypass a provider's terms.

## 6. Distinct strategy catalog — no duplicate mechanisms

Each worker has a distinct hypothesis, entry logic, exit logic, adverse regime and outcome attribution. Merely changing an EMA period does **not** create a new strategy.

| ID | Hypothesis | Trigger / operational horizon | Prohibited regime or special exit |
|---|---|---|---|
| S01 TrendImpulse | Intrabar continuation after multi-timeframe alignment | Confirmed momentum, 1–3 min | Exit on momentum decay; reject widened spreads |
| S02 CompressionRelease | Volatility expansion after measurable compression | Range contraction and expansion, 1–5 min | Reject low liquidity/fakeouts |
| S03 FalseBreakTrap | Failed breakout returns into prior range | Re-entry confirmation, 2–10 min | Stop beyond invalidation, no averaging down |
| S04 MicroMeanReversion | Overextension within measured stationary range | Deviation + reversion confirmation, 3–10 min | Never deploy in trend/news regime |
| S05 SessionOpeningDrive | Session open directional imbalance | London/NY time windows, 1–10 min | Ban around unsupported broker liquidity |
| S06 VolumePriceDivergence | Price and authenticated volume proxy disagree | Independent divergence filter, 3–10 min | Skip when true volume unavailable |
| S07 MomentumExhaustion | Short-run momentum loses persistence | Exhaustion + opposing confirmation, 1–5 min | Strong breakout mode disables |
| S08 PostEventReaction | Actual post-release price path differs from pre-event path | Delayed post-news confirmation, 2–10 min | No pre-news directional guessing |
| S09 GoldMacroTransmission | Real yields/USD proxy changes precede XAU response | Time-aligned macro + XAU condition, 5–10 min | Proxy missing/stale → reject |
| S10 BTCETHRelativeDislocation | Normalized BTC/ETH movement diverges | Pairwise conditional signal, 3–10 min | No guaranteed pairs arbitrage; avoid common-risk doubling |
| S11 LiquidityDefense | Execution cost/quote integrity degrades | No-trade risk strategy, immediate | Cancels new intents, controls existing protections |
| S12 CrisisCapitalShelter | Volatility, drawdown or broker health breaches regime cap | Flat/reduce-risk directive, immediate | Cannot open recovery or martingale orders |

Strategy units emit at most one candidate per unique closed-bar/timeframe/event unless their verified contract explicitly permits a second independent event. `EvidenceArbiter` can combine votes but must prevent duplicate exposure for the same underlying hypothesis. Each strategy tracks independent hit rate, after-cost expectancy, tail losses, execution failures, drawdown, time-to-exit and number of distinct effective trades.

Separate *sleeve* budgets may run concurrent strategies and multiple positions per symbol only where the account supports hedging. Under netting, maintain virtual strategy attribution but recognize a single broker position. The portfolio risk coordinator reconciles net economic exposure regardless of label.

## 7. Multi-horizon trading contract: 1–10 minutes

- Supported execution horizons: nominal 60, 180, 300, 600 seconds, with data resolution and broker capability verified for each instrument.
- Every candidate declares `max_hold_seconds` and a broker-side SL where supported; timeout exit is not guaranteed if venue disconnected, so the risk case must model prolonged hold and gap loss.
- Time-based exits, stop/target, break-even, trailing protection and emergency closure have a deterministic priority order and idempotent execution.
- Cooldown keyed by `(account, symbol, strategy, event_id)`; duplicate entries on restart remain rejected.
- Multiple positions are capped both by symbol and correlated-risk cluster, not just by a cBot `Label`.
- Active-event strategies may use on-tick logic; closed-bar-only strategies must not claim sub-bar reaction speed.
- No high-frequency/latency-arbitrage claim: cTrader/retail broker, real network and spread constraints govern feasible speed.

## 8. Global Risk Constitution — non-negotiable defaults

These are **conservative initial DEMO constraints**, not financial suitability recommendations. A release may tighten them automatically; loosening requires owner authorization and a newly approved policy version.

| Limit | Initial DEMO policy |
|---|---|
| Maximum initial risk per position | 0.25% of reconciled equity |
| Per correlated cluster | 0.50% worst-case stop loss |
| Total simultaneous planned risk | 1.00% of reconciled equity |
| Daily stop | 2% of start-of-trading-day equity, incorporating realized + current floating P&L |
| Weekly stop | 4% of weekly reference equity |
| Portfolio peak-to-trough emergency halt | 8% |
| Consecutive losses | Three → pause affected sleeve pending review |
| Symbol position count | Up to three, subject to tighter aggregate budget |
| Overall account position count | Up to eight, subject to margin and correlation guard |
| Martin­gale, revenge-risk, unchecked averaging | Prohibited |
| Data/quote/clock/reconciliation failure | Fail closed to NO_NEW_ORDERS |

Loss reference periods use broker-server session calendar mapped to UTC with persisted daily/weekly boundaries, not process startup time. Restarts never reset a breach. P&L uses account currency and includes commissions, swaps and unrealized loss. Account-wide stop/kill state is persisted with signed audit and verified broker reconciliation before reset. 

Before any new demo intent: check available margin under stress, symbol minimum stop distance, tick size, real broker precision, current quote, spread percentile, execution-cost interval, pending orders, risk reservations, high-impact event guard and all active positions across accounts. Correlated exposures use rolling stress correlations plus worst-case common-factor grouping; missing covariance produces the conservative grouping.

## 9. Order state machine and failure semantics

`PROPOSED → EVIDENCE_VALIDATED → RISK_HELD → SENT → ACKNOWLEDGED → PARTIAL/FILLED → PROTECTION_VERIFIED → EXITING → CLOSED → RECONCILED`.

Additional terminal or holding states: `REJECTED`, `EXPIRED`, `CANCELLED`, `UNKNOWN_OUTCOME`, `QUARANTINED`.

- A repeated intent ID is idempotent. The system never blindly resends an order after a timeout; it queries broker state and reconciles first.
- On partial fills, only the filled quantity consumes risk and receives verified protection; residual risk holds are adjusted atomically.
- An ACK without confirmed stop protection is a critical event; the executor attempts a bounded broker-authorized repair or defensive close and halts new orders. It records failure, never assumes success.
- A restart restores journal offsets, positions, pending orders, stop status and broker capabilities before entering an order-eligible state.
- Unknown order outcome blocks new orders for the account/strategy until reconciliation. Persisted intent IDs survive process and GitHub outages.
- Separate hedging/netting accounting; avoid falsely attributing the same gross position to several strategies.
- Never store secrets in Git, website HTML, logs or signal payloads. Live mode remains disabled even if the adapter is accidentally configured with a real account.

## 10. Execution Reality Twin

The twin predicts a **distribution** of spread + commission + slippage + delay + reject probability, conditional on `(broker, symbol, session, volatility, size, order_type)`. It never replaces observed broker facts. It must mark uncertainty for sparse samples.

Before entry: estimate after-cost edge and adverse-fill sensitivity under BASE, STRESSED and CRISIS assumptions. A negative lower-confidence-bound result rejects the candidate or reduces size under the risk constitution.

After every demo fill/reject: compare prediction to actual with MAE, tail coverage, calibration error, prediction interval coverage and drift. Changes require shadow verification; sudden cost-model failure triggers NO_NEW_ORDERS. There is no claim of zero slippage or guaranteed best execution.

## 11. Proof-Carrying Trade Decision

Each decision carries exactly the causal input view available at that time, the model/strategy version, risk preconditions, rival candidates, dissent/rejection reasons, execution forecast and alternative `NO_TRADE` outcome.

An auditor can replay any decision from a pinned dataset and seed. The replay result must reproduce verdict, risk reservation and feature hashes; nondeterministic model operations must record the seed/library/hardware version and declared tolerance.

The evidence object is append-only and cryptographically linked to previous event hashes; tampering invalidates subsequent reports. Never use hash chaining as a substitute for secure storage access, authorization or off-host backup.

**Counterfactual shadow book:** in parallel with each accepted/rejected candidate, record the hypothetical opposite action, smaller size, delayed entry and no-trade outcome under pre-registered fill models. Counterfactual outcomes are research estimates, not actual P&L and not revenue.

## 12. Evolution laboratory and statistical ethics

Pipeline: candidate registration → data eligibility → train → purged/embargoed OOS → walk-forward → cost stress → multiple-testing correction → Monte Carlo → shadow demo → independent demo → signed champion decision.

- Genome parameters: data selection, regime, risk, entry/exit, time horizon, signal threshold, execution style and activity budget. Mutations constrained by schema and existing safety policy.
- Champion remains active until Challenger passes *all* comparable preregistered tests with uncertainty and costs. Rolling back is a versioned state transition, never self-modifying production code.
- Explicitly track every trial and hypothesis to penalize selection bias; deflated/probabilistic Sharpe alone does not prove future edge.
- Hold out untouched periods and venues where feasible; test sensitivity to different volatility regimes, commission, spread, gaps and outages.
- Benchmark trading metrics net of cost: return, drawdown, Sortino/Sharpe with uncertainty, expectancy, tail CVaR, turnover, calibration, market exposure and missing-data frequency.
- No mandatory profitability claim based solely on backtests. A failed OOS gate means research-only; no cherry-picking a period with positive headline P&L.
- Continuous learning can propose code/config changes but cannot autonomously raise leverage, risk budgets or promote itself to live trading.

## 13. Release acceptance: explicit evidence, not green generic CI

### Gate G0 — code and portability

1. cTrader C# build succeeds using the pinned official SDK/runtime; verify DataSeries indexing and available order method overloads.
2. Each source file/config has version, owner, expected runtime and SHA; syntax and unit test receipts are attached.
3. No unreviewed network or secret access; no live-account permission; build report includes warnings.

### Gate G1 — pure deterministic logic

4. All 12 strategy contracts pass unit and property tests, including no-trade, bad timestamp, invalid price, negative/NaN risk and duplicate event.
5. Exact expected branch for mutually contradictory signals, stale market data and unavailable macro proxy.
6. A replay yields the same outcome within declared tolerance; intentionally corrupt evidence hash must fail.

### Gate G2 — execution and portfolio failure injection

7. Parallel 100-intent race tests prove total consumed reservations never exceed available portfolio budget.
8. Duplicate intent, restart, network timeout, partial fill, broker reject, stop-creation failure, stale margin and spread shock each block or reconcile correctly.
9. Zero unknown-order automatic retries; zero observed unprotected new positions permitted in the accepted demo trace.
10. Daily/weekly loss references survive a restart and timezone boundary; cross-bot aggregate loss halt cannot be bypassed.

### Gate G3 — validity and commercial-grade measurements

11. Locked OOS and walk-forward splits, full trial accounting, leakage/recursive bias analyses, bootstrap uncertainty, cost and latency stress reports.
12. At least 200 independent closed demo-equivalent opportunities per promoted strategy across representative regimes, or explicitly declare inadequate sample and do not promote. Counts are statistical study targets, not promises that market events will occur quickly.
13. At least 90 calendar days of genuine forward DEMO observation for a final automated execution candidate, covering multiple volatility regimes where possible. Shorter observation cannot be labeled fully accepted.
14. Precommitted test requires positive estimated after-cost edge with 95% bootstrap interval lower bound above zero plus acceptable drawdown under policy. If the sample is too small or confidence conditions fail, the verdict is **INCONCLUSIVE**, never PASS.
15. Compare against buy/hold, no-trade, simple EMA and benchmark framework implementations at matched market, time, risk, costs and data access; report underperformance as prominently as outperformance.

### Gate G4 — safe 24/7 operations

16. Independent VPS or cTrader-approved instance; GitHub Actions is not a scheduler or data relay in the production runtime.
17. Demo service health, recovery, current source SHA, order/position reconciliation and backups have externally readable receipts.
18. 30-day demonstrable service availability target >=99.9% excluding declared provider outages, with every missing interval labeled; p99 decision time and broker ACK distribution reported per venue, not guessed.
19. Alert, kill-switch, recovery rehearsal, controlled rollback and signed audit log verified without publicizing credentials or proprietary quotes.
20. No production switch while VPS disk safety, recoverable backup and source isolation controls are failed.

### Gate G5 — management and publication

21. Persian dashboard reconciles true broker demo fills, P&L, fees, risk holds, deviations, all open positions and blocked intents.
22. Distinct display of `SIMULATED`, `BACKTEST`, `SHADOW`, `DEMO_FILLED` and `REAL_SETTLED` (real remains disabled); none counts as company revenue without independent settlement proof.
23. No signal publication until separate explicit owner approval; destinations must be specifically dedicated to trading signals, with Persian content only to Persian destinations and English only to English destinations.
24. Public feed is versioned, signed, expiry-checked and never exposes account, order ID, private pricing or API secrets; no email is sent without owner approval.

**Unambiguous outcome categories:** `DESIGNED`, `CODE_PRESENT`, `STATIC_TESTED`, `COMPILED`, `BACKTEST_VALIDATED`, `FORWARD_DEMO_PROVEN`, `OPERATIONALLY_ACCEPTED`, `LIVE_APPROVED` (currently prohibited). Generic GitHub CI success does not imply cTrader compilation, VPS activation or realized profit.

## 14. Failure hierarchy and immutable constraints

Priority: account live detection → emergency halt → unprotected open position → broker reconciliation → risk budget → data integrity → cost confidence → strategy score. No ML or dashboard control may override a higher-priority safety block.

The default for uncertain data, stale news, missing broker quote, ambiguous fill, clock drift, no reserve, rejected SL, breached daily loss or no authenticated connection is `NO_NEW_ORDERS`. Existing broker-managed protections remain under separate monitoring; the bot must never claim it can guarantee closing a position across outages.

Do not claim production readiness from unit tests, 50 simulated agent identities, an hourly public candle observer, a private snapshot relay, source files, a CI pass or a paper P&L counter.

## 15. Concrete implementation map against current repository

| Current artifact | Validated meaning | Required APEX addition |
|---|---|---|
| `trading/MojTradeOmegaXDemoBot.cs` | Early fail-closed DEMO adapter with EMA/RSI/ATR and one market-order path | Compile correction, isolated strategies, robust broker execution, durable risk state, timeout exits |
| `trading/MojTradeDemoBot.cs` | Separate short-term demo strategy experiment | Decide a single canonical executor; do not conflate labels or deploy both without shared limits |
| `scripts/mojtrade_observe_market.py` | Private hourly BTC/ETH research observation | Multi-timeframe authenticated tradeable quote support, provenance and direct independent service schedule |
| `scripts/mojtrade_consume_observation.py` | Research-only consumer; orders disabled | Signed StrategyRelease validation and evidence contracts without execution privilege |
| `deploy/audit_agent_fleet_vps_readonly.sh` | VPS inventory and observational receipts | APEX independent health/replay evidence; no activation through an audit |
| `core/trading_lab.py` on separate draft PR | Proposed demo-agent simulation, not merged main | Reconcile branch, align schemas, deduplicate with canonical portfolio core |
| Current build specification | Broad feature and acceptance vision | This APEX 1300 differentiator, data schemas, measurable gates and competitive benchmark |

### Safety-first engineering sequence

1. Correct cTrader compile blockers and protective order checks, then prove Build on a real cTrader-compatible environment.
2. Build separate deterministic contract/risk/decision libraries and pin exchange/broker market conventions.
3. Integrate 12 distinct strategy prototypes behind a shared idempotent risk coordinator in demo/shadow mode.
4. Deliver signed evidence journal, reality twin, counterfactual research and owner dashboard.
5. Validate historical and forward demo evidence with the release gates; no financial switches without an entirely new approval process.

## 16. Competitive claim audit template

For each framework/comparator, record: version/date, instruments, data provenance, venue, identical fee/spread/slippage assumptions, matched capital and max-risk, test windows, order volume, latency, outage rate, data usage/cost, auditability and verification method. Report confidence intervals, failure cases, reproducibility, limitations and whether comparator is actually deployable on this broker.

Claims permitted: “APEX design specifies cross-instance risk holds and proof-carrying decision evidence”; “X gate passed on version SHA under conditions Y.” Claims prohibited without trial: “better than all world bots,” “guaranteed monthly income,” “zero loss,” “AI detects every regime,” “best execution on every order.”

### Owner acceptance receipt

The owner is shown a single dated table with all 13 pillar scores, source hashes, acceptance evidence, blocked features, budget/spend status, runtime state, and whether demo/live orders occurred. No fabricated grade and no silent carry-over of evidence from a different commit SHA.

**Design verdict as of this revision:** a comprehensive **1300-point target architecture** with explicit competitive tests; **implementation, demonstrated superiority and real trading are NOT certified**.
