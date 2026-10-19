# MojPlayWin — Game Economy Stress Lab 1.0.0

**Free original digital tool, private QA candidate — NOT listed in a live store.**

A deterministic, offline Python 3.10+ game-economy sandbox for designers to test how virtual currency earnings, spending demand, wallet caps, growth and assumed session retention interact. It generates a per-session ledger and retention-weighted cohort totals. It uses only the Python standard library; no network requests, payments, ads, analytics, personal data or random loot.

## Run

```bash
python3 economy_lab.py --config example.json --format json
python3 economy_lab.py --config example.json --format csv > session-ledger.csv
python3 -m unittest discover -s tests -p 'test_mpw_game_economy_stress_lab.py' -v
```

All currency units are **fictional in-game units**; nothing is a real-world price, financial recommendation or player-behavior forecast.

## Inputs

| Field | Meaning | Bounds |
| --- | --- | --- |
| `sessions` | Number of successive sessions | integer 1–360 |
| `session_minutes` | Minutes per session | 0.1–1440 |
| `initial_wallet` | Virtual balance before session 1 | 0–1e9 |
| `earn_per_minute` | Currency minted per minute in session 1 | 0–1e7 |
| `spend_per_minute` | Desired sink per minute in session 1 | 0–1e7 |
| `earn_growth_per_session` | Multiplicative session-to-session change in earn rate | -0.5–0.5 |
| `spend_growth_per_session` | Multiplicative session-to-session change in spend rate | -0.5–0.5 |
| `wallet_cap` | Maximum carryover wallet | 0–1e12 |
| `players` | Starting cohort size | integer 1–10,000,000 |
| `retention_per_session` | Assumed fraction remaining for next session | 0–1 |

Unspecified inputs use example defaults. Unknown inputs, NaN/infinity, negative balances, excessive growth, malformed files, and oversized configs are rejected.

## Model and interpretation

For session `i`, `earned_i = earn_rate_i × minutes`; `requested_i = spend_rate_i × minutes`; `spent_i = min(requested_i, wallet_before_i + earned_i)`; `overflow_i = max(0, wallet_before_i + earned_i - spent_i - cap)`; `wallet_after_i = wallet_before_i + earned_i - spent_i - overflow_i`. Conservation is checked every session. The next session's rates are multiplied by `(1 + growth)` and active cohort by `retention`. Weighted cohort totals multiply each session's representative-player flow by its expected active player count.

**Important limits:** The cohort model does not track heterogeneity, churn selection, conversion, real purchase behaviour, market value, psychological effects or actual retention. The same representative player ledger is applied to each expected active player. This is a hypothetical design stress test, not validated behavioural science. Rounded display values may differ slightly from exact internal ledger identities. No product or commercial quality approval is implied by automated unit tests.

## Release status and rights

Version: `1.0.0`. License: MIT (see LICENSE). Authoring: new standalone implementation. Product ID: `mpw-game-economy-stress-lab-v1`. Proposed price: zero; no actual storefront listing, delivery link, FactoryReleaseManifest or owner approval exists yet. An independent rights/security/content review, native store registration, safe deployment and binary HTTP retrieval test remain mandatory.
