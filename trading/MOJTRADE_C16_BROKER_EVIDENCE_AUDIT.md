# MojTrade C16 — independent-evidence comparison gate (no trading)

## Purpose

C15 added broker-*reported* position IDs to DEMO settlement receipts. C16
compares those receipts with a separately exported broker position/history
snapshot, flags missing/unexplained positions and missing protective stops,
and always refuses to interpret matching data as a trading authorization.

`trading/mojtrade_broker_reconcile.py` is an offline, read-only Python CLI.
It needs no broker API token or funds, writes no database and places no orders.

## Inputs

1. A JSON response saved from the bearer-protected C15
   `GET /v1/receipts?account=ACCOUNT&day=YYYY-MM-DD` endpoint.
2. A *normalized CSV* obtained independently from the **same cTrader DEMO
   account**. This is a defined interchange format, **not a claim that
   cTrader's native export uses these exact columns**:

   `account,position_id,label,state,opened_utc,stop_loss,take_profit`

   - `state` is `open` or `closed`.
   - `opened_utc` must be an ISO-8601 timestamp with explicit timezone.
   - `stop_loss` and `take_profit` must be positive values for a MojTrade
     position to count as protection evidenced. If the broker's closed-trade
     export does not preserve historical protective stops, **do not invent
     them**; the check will report insufficient evidence.
   - Include all MojTrade-labeled positions opened that UTC day, even those
     already closed. Extra manual trades with other labels are permitted.

Example (only for illustrating the import format; **not a real trade**):

```csv
account,position_id,label,state,opened_utc,stop_loss,take_profit
123,801,MojTrade-OMEGA-X-DEMO,open,2026-11-08T08:00:00Z,1.20,1.40
```

## Usage on an operator-controlled machine

```bash
python3 trading/mojtrade_broker_reconcile.py \
  --receipts ./receipts.json \
  --broker-csv ./normalized-broker.csv \
  --account 123 --day 2026-11-08
```

Exit codes: `0` means **only that supplied evidence is internally
consistent**, `1` identifies a reconciliation problem, `2` identifies invalid
or inaccessible input. All outputs include `commercial_readiness: false` and
`broker_source_authenticated: false`. Authentication of the export's origin
still requires a trusted broker session; successful comparison never enables
live trading, demo trading or public signals.

The checker refuses partial `/v1/receipts` results (`truncated: true`),
unsettled reservations, orphan MojTrade broker positions, missing broker
positions, duplicated identity and missing stop/take-profit evidence.

### C17 evidence-integrity tightening (source-only)

For the C15 receipt schema, every receipt must now contain its original
`created_unix_seconds` and `expires_unix_seconds`. The UTC creation day and
90-second reservation TTL are checked against the coordinator contract.
The independently supplied broker opening timestamp must fall within the
reservation window, with a conservative five-second clock tolerance on either
side; skew or clock anomalies block a consistent-evidence verdict.

Duplicate CSV header names, duplicate JSON keys (including nested receipt
objects), non-finite JSON constants and incomplete/malformed timestamps are
rejected rather than silently accepted. These strict offline checks do **not**
authenticate the broker export, verify the order in the broker's own system,
turn on DEMO trading, or confer commercial readiness. A clock-synchronisation
problem can produce a deliberate false-negative and requires operator review;
it must never be bypassed automatically.

## CI improvement

`.github/workflows/mojtrade-cbot-build.yml` now has a separate
`risk-regression` job, triggered by Python coordinator/auditor or test changes,
running the complete `test_mojtrade_*.py` suite without credentials.
The prior zero-credential .NET cBot compile job is retained. GitHub Actions
builds and checks source only; it must not host the running trading system.

No external account was accessed and no broker export, TLS VPS deployment,
order, real-money transfer, paid service or public signal was created.
