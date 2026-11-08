# MojTrade OMEGA X — quote-depth execution twin (research only)

## What actually exists

An **offline, deterministic, event-level hypothetical fill replay engine** for short-horizon strategy research. It models client/network/venue latency, executable bid/ask spread, up to five visible depth levels per side, multiple contenders consuming a single event's limited displayed liquidity, IOC partial fill/cancel, FOK all-or-none, adverse slippage thresholds relative to the **last actually observed quote at decision time**, order TTL, halted venue and per-fill commission.

This is **not a live execution adapter, exchange simulator, depth reconstruction engine, or evidence of strategy profitability**. No market data source is connected; all event books, sizes, timestamps and latency assumptions are externally supplied and are not authenticated. It has no broker API, socket, account key, order placement, public signals, email, payment or background service. It does not write any persistent production data.

Official cTrader documentation explains that market execution may be affected by liquidity and network latency, potentially causing partial fills and slippage: https://help.ctrader.com/trading-with-ctrader/orders/

## Replay contract

Input schema `mojtrade.execution-twin.research.v1`, with exactly `schema`, `source_id`, `symbol`, `events`, `hypothetical_intents`.

- **Events:** 2–4000 monotonic venue timestamps within one hour. Every event has a data-availability timestamp no more than five seconds after event time, venue state `OPEN`/`HALT`, and price-sorted positive bid/ask depth. Locked/crossed best quotes and invalid duplicate timestamps are refused.
- **Intents:** 1–128 with unique IDs, strategy ID, `BUY`/`SELL`, positive quantity, decision timestamp, three bounded latency components in milliseconds, positive TTL (relative to modeled arrival), IOC/FOK, max adverse slippage in basis points and commission basis points.
- **No lookahead for the reference quote:** an intent cannot form an execution reference before a quote is actually observable. Buy reference uses the observed ask; sell uses the observed bid.
- **First eligible event:** modeled arrival is `decision_at + client_latency_ms + network_latency_ms + venue_latency_ms`. The first event at or after arrival is used. If it is after `arrival+ttl`, the intent expires. If it is a halt, no fill occurs.
- **Price/depth matching:** buy consumes ascending asks, sell consumes descending bids within the adverse slippage bound. Orders are processed by arrival time, then stable ID; every filled unit decreases the event's shared available size. FOK is rejected without consuming depth if its entire quantity is unavailable. IOC can fill partially and cancels its remainder.
- **Costs:** receipt reports weighted average fill price, positive or negative signed slippage cost versus observable reference, filled notional and hypothetical **entry-side** commission. It does not estimate realized P&L or round-trip profits.
- **Audit:** deterministic receipts with SHA-256 checksums and complete no-fill reasons. Every result has `mode=RESEARCH_SIMULATION_ONLY`, `real_orders=0`, `public_signals=0`, `broker_connected=false`.

## Example

```json
{
  "schema": "mojtrade.execution-twin.research.v1",
  "source_id": "synthetic-example",
  "symbol": "EURUSD",
  "events": [
    {
      "t": "2026-11-07T18:00:00Z", "available_at": "2026-11-07T18:00:00Z",
      "venue_status": "OPEN",
      "bids": [{"price": "1.1000", "size": "2000"}],
      "asks": [{"price": "1.1002", "size": "2000"}]
    },
    {
      "t": "2026-11-07T18:00:00.100Z",
      "available_at": "2026-11-07T18:00:00.100Z",
      "venue_status": "OPEN",
      "bids": [{"price": "1.1000", "size": "1000"}],
      "asks": [{"price": "1.1003", "size": "1000"}]
    }
  ],
  "hypothetical_intents": [{
    "intent_id": "research-001", "strategy_id": "MTF-example",
    "side": "BUY", "quantity": "1500",
    "decision_at": "2026-11-07T18:00:00Z",
    "client_latency_ms": 10, "network_latency_ms": 30, "venue_latency_ms": 10,
    "ttl_ms": 300, "time_in_force": "IOC",
    "max_adverse_slippage_bps": "15", "commission_bps_per_side": "2"
  }]
}
```

The JSON is invented for demonstrating schema behavior and **does not describe any actual historical EURUSD market depth or realized trade**.

```text
python3 scripts/mojtrade_execution_twin.py --input /private/research/quote-depth-scenario.json
python3 -m unittest -v tests/test_mojtrade_execution_twin.py
```

No file is created by the CLI; the JSON report goes to stdout. Run this only on bounded local research input.

## What is not modeled / remaining release gates

- No source-authenticated real tick/level-2 data, exchange timestamps or actual latency distribution. Synthetic or fabricated depth cannot calibrate real execution.
- No queue position, hidden liquidity, venue-specific book resets, matching priorities, market impact, cancellations during latency, order replace/modify, fee tiers or currency conversion.
- No partially resting limit-order lifecycle (only IOC/FOK immediate-or-cancel style simulation), no stop/TP execution, no liquidation, margin/funding or realized trade P&L.
- No authenticated link to the Foundry PR #2120 or the portfolio risk handoff PR #2125; integration must require both proofs and a real demo data contract. This twin is a **separate offline component**.
- No statistical claim, paper-account P&L, demo run, profitable alpha, financial revenue, or permission to route an order.

The acceptance boundary is independent venue-certified replay data plus a separately reviewed integration to the signed strategy release, risk constitution and authenticated demo-only adapter. Real-money execution stays locked.
