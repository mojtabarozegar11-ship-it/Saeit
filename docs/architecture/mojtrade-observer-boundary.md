# MojTrade — existing observer / new research engine boundary

## Confirmed repository contract (7 Nov 2026)

The existing `scripts/mojtrade_observe_market.py` on `main` emits a private
`schema_version: 1` feed with **two hourly watch states**, rather than a
historical tradeable-bar dataset. It validates at least 60 closed candles and
retains the derived `symbol`, `stance`, `observed_at` (bar **close**, not
feed availability), `method` and claimed `data_source`. It discards the raw
open/high/low/volume history and contains no per-bar exchange availability
timestamps or observed spreads.

The independent `scripts/mojtrade_strategy_foundry.py` requires at least 100
consecutive bars carrying `t`, *actual observed* `available_at`, OHLC and
`spread_bps`. Synthesizing any missing field, or substituting the time the
bar closed for the time its information became available, would create
look-ahead/data-quality risk. **There is no automatic adapter.**

`scripts/mojtrade_observer_boundary.py` provides a read-only compatibility
audit of an existing local private observer payload. It checks the actual
observer schema, freshness, two markets, hourly close times, allowed source
labels and deterministic signal IDs. Its stable output is always **watch-only**
with `engine_input_eligible=false`, `execution=disabled`, `publication=disabled`
and `real_orders=0`. The recorded data-source labels and payload SHA-256 are
not source authentication. Invalid/expired/unsafe evidence fails closed.

Run on a machine that already holds a private observation file:

```bash
python3 scripts/mojtrade_observer_boundary.py \
  --input /absolute/owner-private-0700/validated-payload.json
```

The input must be an ordinary owner-owned `0600` file inside an owner-owned
`0700` directory. The command does not contact providers, modify the file,
publish signals, send emails, create orders or install a daemon. Use an
absolute path to a genuine local observation; neither test fixtures nor this
documentation demonstrate a current live VPS observer.

Automated no-network contract tests:

```bash
python3 -m unittest -q test_mojtrade_observer_boundary.py
```

### Remaining evidence for research-to-market integration

1. Independently retained raw closed OHLCV bars with sufficient history.
2. Venue-verified **per-bar availability** times and bid/ask or observed
   spread evidence, including data-capture receipt.
3. Independent out-of-sample performance, friction and forward-reconciliation
   evidence; a consistent watch-state feed is not such evidence.
4. Separate user authorization for any public publication or real broker
   connection; none is granted by this audit.

This module is an audit boundary, not an alternate observer or trading robot.
