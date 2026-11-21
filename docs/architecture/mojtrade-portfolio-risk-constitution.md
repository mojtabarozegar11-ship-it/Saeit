# MojTrade portfolio risk constitution — research slot gate v1

## Delivered scope (not a trading system)

This module implements **transactionally serialized, shared, research-only risk reservations** for multiple short-horizon strategy proposals on the same account. It never sends orders and can neither verify nor reconcile a broker account. All responses, including `RESEARCH_SLOT_RESERVED`, explicitly state `broker_eligible=false`, `execution=disabled`, and `orders=0`. An approved *research slot* must never be treated as permission to place a trade.

The existing `MojTradeOmegaXDemoBot.cs` is not integrated or modified. This module has no cTrader import, API access, network calls, funds, email, public signal publishing, paid service, VPS daemon or deployment. No account keys are required. Standard-library Python / SQLite only; GitHub Actions is not an execution dependency.

## Deterministic gate

The frozen, illustrative research policy is intentionally not customer-customizable through input:

| Constraint | Research policy |
|---|---:|
| Individual candidate stop risk including execution buffer | at most 0.25% of current equity |
| Shared aggregate open plus reserved risk | at most 1.2% |
| Per-symbol risk | at most 0.5% |
| Per-correlation-cluster risk | at most 0.8% |
| Per-strategy risk | at most 0.5% |
| Gross notional | at most 3× equity |
| Concurrent positions plus research reservations | 10 overall, 3 per symbol, 3 per strategy |
| Daily equity decline from locked UTC day anchor | latch at 1.5% |
| Global drawdown from highest observed equity | latch at 5% |
| Consecutive loss counter | latch at 4 |
| Account snapshot and quote age | maximum 5 s and 3 s respectively |

These values are engineering test guardrails, **not validated investment recommendations or calibrated broker limits**. They do not establish suitability for any account, instrument or market. Supported symbol-to-cluster mapping is intentionally frozen (`EURUSD`, `GBPUSD`, `USDJPY`; `XAUUSD`, `XAGUSD`; `BTCUSD`, `ETHUSD`). Unknown symbols are rejected, not assigned to a weaker cluster.

Each position and request must supply `quantity`, `entry`, adverse `stop`, `unit_value_cash_per_price_point` and `execution_buffer_cash`. Research stop exposure is `abs(entry - stop) * quantity * unit_value_cash_per_price_point + execution_buffer_cash`; a simple buffer floor of 0.02% of notional is required. This is an **illustrative proxy**. Contract specification, currency conversion, gaps, slippage, margin, liquidity and partial fills are not broker-attested. Broker-provided sizing functions themselves are documented by cTrader as potentially imprecise: https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/VolumeForProportionalRisk/

## Concurrent execution semantics

1. The input must explicitly be `account_mode=DEMO`. LIVE or unrecognised account modes are rejected **before the research database is created**.
2. Validate timestamp freshness, UTC risk day, all price/stop/unit values, complete open-position evidence and a bounded request list. Unknown instrument mappings fail closed.
3. Open an owner-only 0600 SQLite database under an existing 0700 directory. `BEGIN IMMEDIATE` serializes requests across separate processes.
4. Persist the daily equity anchor, highest observed equity, a monotonic loss counter and circuit-breaker state. Same-day anchor resets and older snapshots fail closed. Daily loss and consecutive-loss breakers latch within the UTC day; global equity peak persists across days.
5. Account for every supplied open position **plus all previously reserved research slots**, then evaluate each proposal in input order. Store every accept/reject receipt, reason list and SHA-256 report digest. Request IDs are idempotent and cannot be reused with changed details; failure of a later item rolls the whole batch back.
6. Reservations **never auto-expire or auto-release**. Broker reconciliation has not been built, so automatic expiration would risk double counting free capital. The ledger rejects new rows at its 512-row ceiling; no cleanup/rollover logic deletes evidence.

Open positions can overlap with reserved slots, which intentionally double-counts exposure in this release. It sacrifices capacity instead of claiming verified reconciliation that does not exist. Account IDs, quotes, quantities, conversions, state and stop data are **caller assertions**, not independently authenticated broker facts. An attacker or missing position can defeat this accounting; it is therefore structurally barred from live/demo order routing.

## Research interface

```text
python3 scripts/mojtrade_portfolio_risk_gate.py \
  --input /private/research/demo-account-snapshot.json \
  --db /private/research/mojtrade-risk.sqlite3
python3 -m unittest -v tests/test_mojtrade_portfolio_risk_gate.py
```

The example files are illustrative and not claimed to exist. Input is JSON with exactly:

```json
{
  "account_id": "research-demo-1", "account_mode": "DEMO",
  "risk_day": "2026-11-07", "snapshot_at": "2026-11-07T18:00:00Z",
  "quote_at": "2026-11-07T17:59:59Z", "equity_cash": "10000",
  "day_start_equity_cash": "10000", "peak_equity_cash": "10000",
  "consecutive_losses": 0, "open_positions": [],
  "proposals": [{
    "request_id": "new-hypothesis-001", "symbol": "EURUSD",
    "strategy_id": "research-strategy-A", "side": "BUY",
    "quantity": "1000", "entry": "1.1000", "stop": "1.0950",
    "unit_value_cash_per_price_point": "1", "execution_buffer_cash": "1"
  }]
}
```

The `risk_day`, `snapshot_at`, and `quote_at` must match actual UTC now when the CLI runs. This sample timestamp is historical and thus intentionally **stale** if run later. No automatic sample data or fabricated market prices are generated.

## Release blockers

- Receive authenticated account/position/fill/contract/currency snapshots from a **separately authorized, demo-only** adapter; require heartbeat identity, monotonic sequence, robust out-of-order handling and explicit settlement/release events.
- Define cross-asset stress and dynamically measured covariance clusters (the current fixed group map is conservative but incomplete).
- Implement exchange/broker constraints and a realistic execution twin, including slippage, rejected/partially-filled orders, disconnects, gap risk and fees.
- Add external immutable audit receipt anchoring, operational alerting, backup/recovery testing and monitored storage capacity before any persistent service installation.
- Subject the proposed strategy to independent market data evaluation and an execution/risk committee release gate. No automatic live-money or demo trading is authorized by this research module.

**Do not merge, deploy or integrate with the existing bot on the basis of local unit tests alone.**
