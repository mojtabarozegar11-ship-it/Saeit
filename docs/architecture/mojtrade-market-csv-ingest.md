# MojTrade — Observation-Time-Safe Market CSV Ingest

**Research-only.** This importer accepts a local market-data CSV and converts
it to the exact Strategy Foundry OHLC schema, with a separate source-integrity
manifest. It does not fetch, synthesize, interpolate or repair market data.

## Required CSV contract

Exactly these headers, in this order:

```csv
bar_open_utc,available_at_utc,open,high,low,close,spread_bps
2026-09-01T00:00:00+00:00,2026-09-01T00:01:00.100+00:00,100,101,99,100.5,2.5
```

- `bar_open_utc`: **start** of the candle, with explicit UTC offset.
- `available_at_utc`: the actual timestamp when the complete bar first
  became observable to the data capture. The importer **does not invent** it.
- The import converts `bar_open_utc + interval_seconds` into the Foundry
  `t` field, which is explicitly the **bar close timestamp**.
- `available_at_utc` must be at or after candle close and no more than one
  interval after it; observation times must increase strictly.
- Bar openings must be exactly one interval apart. Gaps, duplicates,
  reordered observations, missing timestamps and invalid OHLC/spreads cause
  hard failure, with no interpolation.
- Interval is one of 60, 180, 300, 600 or 3600 seconds; count must be 100–5000;
  CSV must be UTF-8, regular non-hard-linked file, at most 950,000 bytes.

## Execution (offline only)

```bash
python3 scripts/mojtrade_market_csv_ingest.py \
  --input /path/to/observations.csv \
  --output /path/to/private-dir/export.json \
  --symbol BTC/USD \
  --interval-seconds 60 \
  --claimed-provider MY_UNVERIFIED_EXPORT
```

Create the private output directory with mode `0700` before running. The
resulting file is created exclusively with mode `0600`; existing output is
never silently overwritten. It contains two objects:

1. `dataset`: valid Foundry-ready market bars, usable as `market_bars` in the
   unified research shadow **after separate quote/account evidence is supplied**.
2. `manifest`: SHA-256 digest of exact imported CSV bytes and normalized data,
   row count, timestamp bounds and explicit evidence status.

The `source_id` starts with `unverified-csv-` and incorporates the CSV hash.
The manifest always says `UNVERIFIED_LOCAL_EXPORT`, even if the user labels
the source as a broker or exchange. This is **not an authenticated exchange
feed**: a file checksum only detects later byte changes; it does not prove
truth, independent quote provenance or the claimed observation timestamp.

## Evidence before trading

- Independent provenance and read-only API/archival capture from an approved
  data source, including observer clock accuracy and signed/checkpointed logs.
- Venue quote/depth matching and source/runtime parity with the current closed
  bar, not just historical OHLC data.
- Untouched out-of-sample validation, realistic costs and live DEMO broker
  reconciliation, with separate approval for any future deployment.

No orders, public signals, account credentials, network requests, or paid
service integrations are created by this importer.
