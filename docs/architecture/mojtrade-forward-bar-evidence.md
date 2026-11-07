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
- When the candle provider is Coinbase Exchange or Kraken Spot, a **public,
  same-venue** bid/ask request is attempted. Coinbase uses the official
  level-1 order book; Kraken uses public Ticker bid/ask. The quote receipt
  timestamp is measured after the HTTPS response. Stale, crossed, negative,
  abnormally wide, slow or mismatched quotes are rejected. Invalid/unavailable
  quotes **never turn into a made-up spread**: the bar is retained with
  `spread_bps: null` and without `quote_receipt`. Other candle venues have no
  supported matching quote adapter in this revision and also retain null.
- Even a good same-venue quote is not a signed venue receipt or a transaction
  fee estimate. `research_dataset_eligible: false`, `execution: disabled`,
  `publication: disabled` and `real_orders: 0` remain unconditional. An observed
  spread is not the entire execution cost.
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

Even after 100 hours, incomplete quote coverage, commissions, slippage,
forward performance, independent venue authentication, signed custody and
release controls remain separate unresolved gates. No profit claim follows
from capture success.

No-network regression tests:

```bash
python3 -m unittest -q test_mojtrade_forward_bar_capture.py \
  test_mojtrade_observer_contract.py test_mojtrade_observer_boundary.py \
  test_mojtrade_market_quote_evidence.py
```

Provider documentation: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book
and https://docs.kraken.com/api-reference/market-data/get-ticker-information
