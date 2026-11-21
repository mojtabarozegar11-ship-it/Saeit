# MojTrade — Dependency-Aware Sensitivity on Frozen OOS Research

**Offline research only; not calibrated financial inference.** This optional
stage extends the immutable independent out-of-sample diagnostics with a
fixed-grid time-dependence sensitivity check. It never modifies, overwrites,
promotes or retunes a strategy, and never sends orders or public signals.

## Why a second stage exists

Counting winning trades as independent trials can understate uncertainty
when trading decisions depend on the same market conditions. The first OOS
stage labels its iid sign calculation as unverified. This stage applies a
deterministic *stationary block bootstrap* to realized hypothetical return
sequences on the same **market-bar timeline**, using the same sampled indices
for every pre-registered strategy in each replication. That better preserves
short-run time dependence and co-movement between strategies **within the
resampled blocks**, subject to strong and unverified assumptions.

Source: Politis and Romano (1994), [*The Stationary Bootstrap*, Journal of
the American Statistical Association](https://doi.org/10.1080/01621459.1994.10476870).
This local implementation is **not** a theorem-backed claim that the data are
stationary, or that the resulting p estimates are valid for market returns.

## Fixed, non-tunable diagnostic configuration

- Frozen Strategy Foundry report with exact training dataset, and entirely
  separate alleged unseen dataset (minimum 300 closed bars, 10-bar embargo,
  replay-pattern protection, matched symbol/interval).
- First use of the OOS dataset goes through the existing private `0600`
  append-only journal, in a `0700` directory; subsequent runs return the
  original receipt or reject a different held-out dataset for the same report.
- Recompute the OOS receipt and require bit-for-bit equality with the supplied
  frozen receipt; never silently replace it.
- Construct one bar-level additive series for each frozen candidate, using
  only its **simulated net returns booked on the exit bar**. The approximation
  is **not** true mark-to-market equity and ignores unrealized drawdowns.
- Preselected mean block lengths **8, 16 and 32 market bars**; exactly
  **256** geometric-block repetitions per length; deterministic seed tied to
  the frozen independent OOS receipt and block length.
- Center each candidate's realized-bar series under a zero-mean null;
  compare its observed mean with the **maximum across all frozen candidates**
  in each jointly resampled null replicate. Report conservative Monte Carlo
  rank estimates `(1 + exceedances) / 257` for each candidate and all three
  block lengths; **no strategy ranking or automatic acceptance** follows.
- The family is *all Foundry births in this frozen OOS*. Previous primitive
  search attempts, omitted adaptive data choices and human search are **not**
  fully accounted for by this bootstrap. The first stage separately documents
  its uncalibrated Bonferroni bounds over the broader recorded attempt count.

## Run with private, already frozen research inputs

```bash
install -d -m 700 /path/to/private-oos
python3 scripts/mojtrade_dependency_diagnostics.py \
  --foundry-report /path/to/frozen-foundry-report.json \
  --training-data /path/to/exact-training-data.json \
  --unseen-data /path/to/separate-unseen-data.json \
  --private-ledger /path/to/private-oos/one-shot.jsonl
```

Only a compact offline audit checksum, candidate count and explicit zero
real-orders/public-signals appear on stdout. The detailed deterministic
research-only result is available through the Python `audit()` function;
running it requires a matching frozen OOS receipt. Inputs can be exact
Foundry datasets or timestamp-safe CSV artifacts marked unverified.

## Non-negotiable limitations

1. A saved file and checksum **do not verify** a provider, exchange, execution
   timestamp, or the data's independence from earlier analysis.
2. Resampling assumes approximately weakly stationary, short-memory
   observations; financial regimes, clustered volatility and sparse exits can
   violate these conditions. **No claimed valid p-value or profitability.**
3. Booking a complete trade outcome at its exit gives a sparse proxy series;
   it is not an executable broker portfolio or intratrade risk measurement.
4. Finite Monte Carlo runs and block length sensitivity are not a prospective
   trial, not an independent broker DEMO reconciliation, and not proof that a
   strategy can be traded at those modeled prices.
5. The source code has **no broker orders, funded actions, email or network
   publishing**. All test fixtures are synthetic research-only illustrations.

## Regression check

`python3 -m unittest -q tests/test_mojtrade_dependency_diagnostics.py`

Even if the diagnostics look favorable, status remains
`DEPENDENCE_SENSITIVITY_NOT_STATISTICAL_VALIDATION`, with every candidate
`broker_eligible = false`.
