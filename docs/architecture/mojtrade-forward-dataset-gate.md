# MojTrade: forward journal to research-only dataset

`scripts/mojtrade_forward_dataset_gate.py` connects the prospective, append-only
bar+quote capture journal to `scripts/mojtrade_strategy_foundry.py` without
backfilling availability times or synthesizing missing bid/ask spreads.

## Exact promotion gate

- Input must be an absolute owner-private regular `0600` JSONL file in an
  owner-private `0700` directory. SHA-256 chain and sequence are validated.
- Only the **latest** consecutive hourly suffix is considered. Every selected
  bar must have a contemporaneous quote receipt from the *same* supported
  venue and identical BTC/USD or ETH/USD symbol. A gap, source switch or a
  missing/invalid spread cuts the suffix; old bars are never patched.
- At least 100 contiguous hourly quoted bars are required. Actual data cannot
  be collected faster by replaying historical OHLC responses. A new market
  quote is measured after the current closed bar is fetched, and its receipt
  time becomes the bar's research `available_at`.
- The dataset runs through the real Strategy Foundry schema validator. Each
  resulting bar carries exact `t`, `available_at`, OHLC and observed
  `spread_bps`. No guessed fee, spread, candle or availability value is used.
- An original venue+symbol gives a **stable research source family** across
  rolling overlapping windows. Each window gets a separate SHA but is not
  counted as an independent market source.

The manifest **always** says `UNVERIFIED_FORWARD_RESEARCH_ONLY`,
`provider_authenticity_verified=false`, `commission_and_slippage_verified=false`,
`production_eligible=false`, `publication_eligible=false`, `execution=disabled`
and `real_orders=0`. A journal checksum is evidence of local byte consistency,
not a cryptographic signature from Coinbase/Kraken or a real broker.

## Offline CLI (not activated on any VPS)

```bash
python3 scripts/mojtrade_forward_dataset_gate.py \
  --private-journal /absolute/private-0700/btc-hourly.jsonl \
  --private-output /absolute/private-0700/btc-research-unique.json
```

The output path must not exist; no existing research file is overwritten.
No network request, broker order, mail, website signal or background scheduler
is performed by the gate itself. The command cannot succeed without a genuine
local journal with enough coherent source observations.

Tests:

```bash
python3 -m unittest -q test_mojtrade_forward_dataset_gate.py
```

Remaining gates for any claim beyond preliminary research: signed independent
venue provenance, exact commission/slippage records, prospective holdout,
broker execution reconciliation, market eligibility and the owner's explicit
production authorization. No profitable outcome or commercial readiness is
established by creating a dataset.
