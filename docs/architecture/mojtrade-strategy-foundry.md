# MojTrade Strategy Foundry — autonomous research-only invention v1

## Honest status

This is a functioning **offline, bounded strategy-hypothesis generator**. It discovers conditional patterns in historical training data, synthesizes typed two-event strategies including ordered sequences, rejects structural/behavioral duplicates and records reproducible research birth certificates.

It is **not** the complete APEX 1300 Foundry. It does not write arbitrary new C#, process market microstructure, connect to cTrader, execute orders, qualify live/demo strategies or establish verified profitable alpha. Approximate OHLC research P&L is not broker-verified profit and must never be counted as revenue.

Safety invariants: no network, no API keys, no broker imports, no orders, no public signals, no email, no paid services, no GitHub Actions runtime dependency. Any demo execution integration requires a separate reviewed release.

## Processing contract

1. Validate bounded chronological OHLC with observation-availability timestamps; reject gaps, invalid prices, unsupported intervals and excessive spreads.
2. Split data chronologically: 65% discovery/training; untouched 35% holdout reporting.
3. Scan a fixed typed feature grammar for conditional next-period return patterns using **training only**. Count every primitive trial, including failures.
4. Generate two-feature strategy ASTs using ALL, ANY or ordered SEQUENCE operations.
5. Reject changes that only tune numeric parameters; reject substantially overlapping training signals.
6. Evaluate delayed-next-closed-bar approximate outcomes with spread, commission and adverse ordering when stop and target both hit in one bar.
7. Save a ledger and SHA-256 evidence digests; every candidate remains RESEARCH_ONLY_UNPROVEN, broker eligibility false, orders zero.

Optional LLM services are excluded: Python standard library only. The engine composes typed mechanisms from a bounded grammar; **it does not claim unlimited invention of genuinely novel mathematical finance theories**.

## Input example

Input JSON has exactly four top-level keys:

    {
      "source_id": "verified-local-candle-export",
      "symbol": "BTC/USD",
      "interval_seconds": 60,
      "bars": [
        {
          "t": "2026-11-01T09:01:00+00:00",
          "available_at": "2026-11-01T09:01:00+00:00",
          "open": 100.0, "high": 101.0, "low": 99.0,
          "close": 100.5, "spread_bps": 2.0
        }
      ]
    }

The sample contains one row for brevity. The actual dataset must contain **100–5000 consecutive bars** with intervals 60/180/300/600/3600 seconds. Time t denotes the bar close and available_at its first observability. Late/gapped observations are rejected. This engine does not use live ticks and cannot model sub-minute execution realistically.

Output fields:

- training_discovery: number of primitive hypotheses tested and qualified.
- trial_ledger: every attempted program, including duplicate/inactive rejections.
- birth_certificates: AST, semantic fingerprint, behavioral novelty, source hash, approximate train/holdout metrics and SHA-256 integrity digest (not an authenticated digital signature).
- execution disabled, orders 0, public_signals 0.

## Local CLI

Create a private output directory with mode 0700. The script writes one specified report through atomic rename with 0600 permissions.

    python3 scripts/mojtrade_strategy_foundry.py \
      --input /private/verified-bars.json \
      --output /private/research/foundry-report.json \
      --seed 173 --trials 64 --cost-bps 2

These paths are illustrative; they do not imply files exist. The cost estimate is a research assumption, not a broker contract.

    python3 -m unittest -v tests/test_mojtrade_strategy_foundry.py

Regression checks cover fixed-seed reproducibility, three or more distinct candidates on a **synthetic fixture only**, holdout isolation, no future-bar signal input, flat-market refusal, structural novelty, simulated fee monotonicity, private output and invalid-data rejection. Synthetic success is never market profitability evidence.

## Known limitations and release blockers

- Four feature families; can combine and order them, but cannot invent arbitrary unseen operators.
- Primitive discovery uses conditional means without multiple-testing correction. Do not promote to demo without embargoed purged walk-forward, trial-aware statistics and adequate independent holdout evidence.
- No cross-asset dataset, book depth, cTrader C# generator, signed StrategyRelease, risk coordinator or broker reconciliation yet.
- Approximate bar fills omit live slippage, swap, fee tiers, partial fills, rejects and most gap behavior.
- A report-producing CLI is **not** a continuously running autonomous service. Independent runtime installation requires separate disk/backup/resource authorization.
- Research P&L and trial counts are not cash revenue.

Next boundary: a typed, signed strategy release plus independent shared risk gate prior to any separately authorized demo adapter connection. Live-money execution remains blocked.
