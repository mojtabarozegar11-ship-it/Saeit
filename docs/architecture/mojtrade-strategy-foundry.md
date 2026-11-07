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
7. Count 96 tested primitive hypotheses plus all generated strategy trials in a **multiple-testing gate**. This gate remains `NOT_STATISTICALLY_VALIDATED`; the holdout is descriptive and never licenses an order or a public signal.
8. Save a ledger and SHA-256 evidence digests; every candidate remains RESEARCH_ONLY_UNPROVEN, broker eligibility false, orders zero.
9. Append full reports to an exclusive-locked, permission-restricted, bounded, hash-chained registry across runs. A duplicate report does not create a second entry; corrupted registry data fails closed.

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
- multiple_testing_gate: primitive plus candidate trial counts, observed holdout candidate count, explicit non-validation, and independent-evidence requirements. This is **not** a statistical p-value correction.
- execution disabled, orders 0, public_signals 0.

## Local CLI

Create a private output directory with mode 0700. The script writes one specified report through atomic rename with 0600 permissions **and** separately appends a full report to `foundry-registry.jsonl` in that directory. Registry appends use file locking and `fsync`; maximum 128 entries or 8 MB. When full, the registry rejects additions; there is no automatic deletion or rewriting.

    python3 scripts/mojtrade_strategy_foundry.py \
      --input /private/verified-bars.json \
      --output /private/research/foundry-report.json \
      --seed 173 --trials 64 --cost-bps 2

You may choose `--registry /private/research/foundry-registry.jsonl`. The registry path must be in an existing mode-0700 directory. Its file is mode 0600, owned by the process user, regular and not a symlink. The report and registry must not be the same path.

These paths are illustrative; they do not imply files exist. The cost estimate is a research assumption, not a broker contract.

    python3 -m unittest -v tests/test_mojtrade_strategy_foundry.py

Regression checks cover fixed-seed reproducibility, three or more distinct candidates on a **synthetic fixture only**, holdout isolation, no future-bar signal input, flat-market refusal, structural novelty, simulated fee monotonicity, private output, invalid-data rejection, hash-chain integrity, idempotency, concurrent duplicate append, file permissions, and record budgets. Synthetic success is never market profitability evidence.

## Known limitations and release blockers

- Four feature families; can combine and order them, but cannot invent arbitrary unseen operators.
- Primitive discovery uses conditional means without multiple-testing correction. The new explicit `multiple_testing_gate` accounts for search attempts but **does not perform statistical adjustment**. A favorable holdout reading across many candidate reports is vulnerable to selection/peeking. Do not promote to demo without a new independent untouched data period, embargoed purged walk-forward, dependency-aware trial statistics and adequate holdout evidence.
- The registry is **not yet cross-run strategy novelty enforcement**; it saves prior full reports to support a future historical uniqueness check. Its chain is tamper-*evident* relative to a known trusted checkpoint, not cryptographically authenticated against a writer able to rewrite the entire file. An independently held off-host chain-head checkpoint is needed.
- No cross-asset dataset, book depth, cTrader C# generator, signed StrategyRelease, risk coordinator or broker reconciliation yet.
- Approximate bar fills omit live slippage, swap, fee tiers, partial fills, rejects and most gap behavior.
- A report-producing CLI is **not** a continuously running autonomous service. Independent runtime installation requires separate disk/backup/resource authorization.
- Research P&L and trial counts are not cash revenue.

Next boundary: a typed, signed strategy release plus independent shared risk gate prior to any separately authorized demo adapter connection. Live-money execution remains blocked.
