# MojTrade — forward-only hourly bar evidence

The existing market observer on `main` reduces 60 valid closed candles to a
watch state. It does not retain raw bars or the time they were first seen by
the system. `scripts/mojtrade_forward_bar_capture.py` **reuses its five public
data-source parsers** to retain one *latest closed* OHLCV bar per execution.

## Safety and provenance

- The `first_observed_at_utc` timestamp is taken from the live process clock
  **after** the upstream fetch completes. Historical candle timestamps are not
  presented as observation timestamps. A bar first seen more than one hour
  after its close is rejected rather than silently backdated.
- The claimed upstream venue is recorded but **not cryptographically
  authenticated**. A SHA-256 linked private journal detects changes after
  recording, not false statements by a provider or local compromise.
- The private file is an owner-owned, regular 0600 append-only JSONL file in an
  owner-owned 0700 directory. Duplicate polls do not add entries. Changed
  values for the same bar, corrupted journals and out-of-order observations
  fail closed. Network or data-quality failures do not create observations.
- Bid/ask snapshots are **not yet captured**: `spread_bps: null`. Consequently
  `research_dataset_eligible: false`, `execution: disabled`,
  `publication: disabled` and `real_orders: 0` are unconditional. Do **not**
  transform null spreads into zero or invented fixed trading fees.
- Provider fallbacks may use different venues across hours. A single coherent
  research series requires a proven venue/source policy and appropriate
  reconciliation before conversion to Strategy Foundry.

## Run path (not activated)

```bash
python3 scripts/mojtrade_forward_bar_capture.py \
  --symbol BTC-USD \
  --private-journal /absolute/owner-private-0700/btc-hourly.jsonl
```

An hourly cron or systemd schedule is **not included or activated** in this PR.
No VPS service, production source, broker or public signal feed is changed.
The command only queries the existing public market-data APIs and appends one
local private observation when validation passes.

Each market must use its own journal. First-hand forward evidence needs at
least 100 correctly spaced hourly observations per symbol over actual time;
this cannot be accelerated by retrieving a historical candle snapshot.

Even after 100 hours, observed spreads/fees, forward performance, signed data
custody and release controls are separate unresolved gates. No profit claim
follows from capture success.

No-network regression tests:

```bash
python3 -m unittest -q test_mojtrade_forward_bar_capture.py \
  test_mojtrade_observer_contract.py test_mojtrade_observer_boundary.py
```
