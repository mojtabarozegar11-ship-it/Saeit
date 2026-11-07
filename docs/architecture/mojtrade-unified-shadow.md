# MojTrade OMEGA X — Unified Research Shadow (7 November 2026)

**Status: research-only, offline, not a trading product, not deployable.**

This independent integration assembles four research engines without a broker
connection or network request:

1. **Strategy Foundry:** deterministic training-only candidate birth certificates,
   per-candidate provenance, a private append-only journal, and an explicit
   `NOT_STATISTICALLY_VALIDATED` multiple-testing gate.
2. **Closed-bar eligibility:** a candidate may fire only on the latest completed
   and available candle. The opening quote must already have been observable;
   its midpoint is checked against the last close. No selection of the best
   holdout-profit candidate is used.
3. **Risk handoff:** constructs a hypothesis from the candidate side, quote and
   ATR-derived stop, then requests a durable, idempotent research-only portfolio
   reservation in the shared SQLite risk gate. Circuit breakers and concentration
   caps remain enforced by the existing risk constitution.
4. **Depth execution twin:** validates the synthetic replay *before* acquiring a
   risk slot and then runs a deterministic IOC/FOK depth and latency simulation.
   Returned fills are hypothetical receipts only.

Every result hard-codes `real_orders = 0`, `public_signals = 0`,
`broker_eligible = false`, and `execution = disabled`. The code has no exchange
API client, trading credentials, broker method, or public signal publishing.

## Entry point

```
python3 scripts/mojtrade_unified_shadow.py \
  --input /path/to/research-input.json \
  --private-dir /path/to/private-research-dir
```

Supply an existing, non-symlink private directory of mode `0700`. The Foundry
and risk gate enforce their own private journal/database permissions and locks.
The output is a JSON research receipt, not an authorization to buy or sell.
The input must use exactly these top-level fields:

```
market_bars          foundry OHLCV dataset (closed-bar available_at required)
execution_book       {schema, source_id, symbol, events}; schema is twin's
                     version, first quote already observable at event time
risk_context         handoff's DEMO-only account snapshot schema
hypothetical_size    {quantity, unit_value_cash_per_price_point,
                     execution_buffer_cash, client_latency_ms,
                     network_latency_ms, venue_latency_ms, ttl_ms,
                     time_in_force, max_adverse_slippage_bps,
                     commission_bps_per_side}
candidate_id         string strategy ID to restrict selection, or null
seed                 deterministic Foundry seed
trials               bounded Foundry search count
research_fee_bps     Foundry research cost per side
```

Use the existing tests as a runnable, fully synthetic example. The workflow
does not download or authenticate live quotes or account snapshots. It refuses
cross-symbol inputs, stale/unobservable closed bars, timestamps inconsistent
with the first quote, non-DEMO accounts, caller-created execution intents,
malformed twin parameters, and the shared risk circuit-breaker states.

## Testing

```
python3 -m unittest -q \
  tests/test_mojtrade_strategy_foundry.py \
  tests/test_mojtrade_portfolio_risk_gate.py \
  tests/test_mojtrade_research_handoff.py \
  tests/test_mojtrade_execution_twin.py \
  tests/test_mojtrade_unified_shadow.py
```

At creation, **71 synthetic/local unit tests** pass (18 + 15 + 12 + 15 + 11).
These test software invariants, not economic validity or positive expected PnL.

## Non-negotiable release blockers

- Input data and DEMO account evidence must come from authenticated, monitored,
  reproducible, real (not generated) sources with immutable time provenance.
- Independent out-of-sample and walk-forward validation, multiple-testing
  correction, leakage checks, cost/latency stress, and realistic no-trade baselines.
- Reconciliation of quoted liquidity, real fills and fees with broker records
  using an approved isolated demo account; adverse selection measurement.
- Review of concurrency, account-state recovery, rollback, operational controls,
  incident handling, and regulatory/compliance requirements.
- Explicit owner approval for any broker integration, live payment, deployment,
  publishing public signals, or risk-policy change.

Existing independent PRs #2120, #2125 and #2128 remain separate and open until
review; this single integration branch is the proposed reference implementation.
It must not be merged, deployed or marketed as a profit-making trading system
based on the local test results.
