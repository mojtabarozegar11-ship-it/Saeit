# MojTrade invention → risk constitution: offline research handoff v1

## Implemented

A strict, **offline-only research handoff** links the Strategy Foundry research report (separate PR #2120) to the portfolio risk constitution's serialized research slot ledger (PR #2125). The handoff is an ordinary function and CLI, not a daemon and not a broker adapter. It never calls order, live trading, signal publication, network, email or payment APIs.

Each proposed research slot requires:

1. The intact `mojtrade.strategy-foundry.v1` report, its SHA-256 receipt, and `RESEARCH_ONLY`/zero-order status.
2. A unique candidate birth certificate with matching SHA-256 receipt, source digest, AST digest, `RESEARCH_ONLY_UNPROVEN` state, no broker eligibility, and corresponding `BORN_RESEARCH_ONLY` event in the trial ledger.
3. The explicit multiple-testing gate `NOT_STATISTICALLY_VALIDATED`. A strategy cannot falsely claim statistical approval in this bridge.
4. A fixed, narrowly allowed symbol normalization (for example `BTC/USD` → `BTCUSD`). Unknown symbols never fall back to a less restrictive group.
5. A `DEMO`-only research snapshot and separately specified hypothetical price, adverse stop, quantity, unit conversion and cost buffer. The candidate side and strategy ID are **derived from the verified certificate** and cannot be overridden.
6. A deterministic replay ID computed from the report/certificate hashes, account and quote/snapshot timestamp. Repeated requests are idempotent; changing size or stop at the same identity fails closed in the shared ledger.
7. Final approval **only for a research slot** through the portfolio risk gate's SQLite `BEGIN IMMEDIATE` transaction and fixed aggregate/symbol/cluster/strategy limits.

Every handoff and risk result has `execution=disabled`, `orders=0`, `public_signals=0`, and `broker_eligible=false`. A slot receipt is never an execution authorization. SHA-256 evidence can be recomputed by anyone holding the data, so it is **not** an authenticated issuer signature; signed releases are still missing.

## Research CLI

```text
python3 scripts/mojtrade_research_handoff.py \
  --foundry-report /private/research/foundry-report.json \
  --request /private/research/handoff-request.json \
  --db /private/research/portfolio-risk.sqlite3

python3 -m unittest -v tests/test_mojtrade_research_handoff.py
```

These are illustrative file paths, not an assertion that such files exist. The risk database directory must already exist and have permissions 0700. Input files must be regular, not symlinks, and bounded in size. The request JSON has exactly three fields:

```json
{
  "strategy_id": "MTF-<birth-certificate-id>",
  "risk_context": {
    "account_id": "demo-shadow", "account_mode": "DEMO",
    "risk_day": "2026-11-07",
    "snapshot_at": "2026-11-07T18:00:00Z",
    "quote_at": "2026-11-07T17:59:59Z",
    "equity_cash": "10000", "day_start_equity_cash": "10000",
    "peak_equity_cash": "10000", "consecutive_losses": 0,
    "open_positions": []
  },
  "trade": {
    "quantity": "1000", "entry": "1.1000", "stop": "1.0950",
    "unit_value_cash_per_price_point": "1",
    "execution_buffer_cash": "1"
  }
}
```

Replace the sample candidate ID with an actual birth certificate ID from the matching report. This historical snapshot is intentionally stale if run at another time; the risk constitution will reject it. Price, point conversion and execution buffer are **hypothetical research assertions**, not live quotes.

## Verified

12 local handoff checks passed, including a genuine in-process contract smoke test with the existing autonomous Foundry implementation plus the real portfolio risk gate. This test's underlying market data is a **synthetic fixture**; it does not demonstrate profitable trading or venue execution. On a branch containing only the risk PR but not the separate Foundry PR, the actual-Foundry compatibility test skips explicitly; the other 11 contract tests remain runnable.

## Remaining release blockers

- Cryptographically signed and authenticated release manifest, including strategy provenance and independently validated research metrics.
- Authentic demo account snapshot, independent market data signatures, contract specifications, quote sequencing and broker-order reconciliation.
- Tick/quote-level execution twin with queue depth, latency, partial fills, rejections, fees and realistic tail slippage. The prior OHLC evaluator is an approximation and cannot verify sub-minute trade execution.
- Evidence from untouched market periods with dependence-aware trial corrections and verified out-of-sample robustness. The current `NOT_STATISTICALLY_VALIDATED` gate must remain in force.
- Reviewed, separately authorized and fail-closed cTrader adapter and explicit operational stop procedure. **This research handoff must never be wired directly to an order sender.**

No merge, deploy, VPS action, broker connection, public signal, expenditure or live order is performed by this module.
