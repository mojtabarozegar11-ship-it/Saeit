# MojTrade — Frozen Independent Out-of-Sample Diagnostics

**Status: offline research-only; not a trading validation.** This stage accepts
a fixed, checksum-verified Strategy Foundry report, the *exact* dataset used
to generate it, and a separate purportedly untouched period. It evaluates all
pre-registered birth certificates, with no strategy changes, model tuning,
network access, broker orders, public signals, or automatic promotion.

## Independent evidence boundary

1. Validate source format, timestamps, closed-candle availability, bar gaps,
   OHLC, market and interval against Foundry. Optionally accept the local CSV
   importer's `{ "dataset": ..., "manifest": ... }` artifact; its provenance
   remains **UNVERIFIED_LOCAL_EXPORT**.
2. Verify the Foundry report checksum, training dataset digest and source ID,
   all candidate birth certificate checksums and program hashes, immutable
   research-only permissions, and internal accounting for every discovery and
   candidate-search attempt.
3. Reject unseen series with fewer than 300 complete bars, incompatible
   symbol/interval, overlapping dates, or less than a 10-bar purge/embargo
   after the **last observed training bar**. A matching 32-candle sequence of
   OHLC/spread values is rejected even if timestamps/source IDs are changed.
4. Evaluate **every** frozen candidate at three execution-cost assumptions:
   base, maximum of 10 bps or 3× base, and maximum of 25 bps or 5× base
   (bounded at 200 bps). Check three chronological subperiods and a zero-order
   baseline. No winning candidate is used to retroactively change the family.
5. Record an explicitly *diagnostic-only* one-sided Hoeffding bound on winning
   trade counts and a Bonferroni upper bound using **all** primitive and
   candidate attempts. Overlapping trades, nonstationarity and serial
   dependence can invalidate the iid premise. These values are **not**
   calibrated financial p-values and do not establish profitability.
6. Store the first evaluation for each Foundry report in a private append-only
   lock-protected hash-chained journal. Identical reruns return the prior
   receipt; a different unseen dataset under the same report is refused.

## Usage

First create a private journal directory, mode `0700`, owned by the operator:

```bash
install -d -m 700 /path/to/private-oos
python3 scripts/mojtrade_independent_validation.py \
  --foundry-report /path/to/frozen-foundry-report.json \
  --training-data /path/to/exact-training-data.json \
  --unseen-data /path/to/new-unseen-period.json \
  --private-ledger /path/to/private-oos/one-shot.jsonl
```

All inputs are local JSON files (up to 3 MB each), including either the exact
Foundry dataset object or the strict CSV importer's artifact. The ledger uses
`0600` permissions and rejects public parent directories, symlinks, invalid
hash chains, concurrent duplicate writes, and changed unseen inputs. CLI
output contains only research status, number of candidates, and zero real
orders/public signals; it never exports trading instructions.

## What this cannot establish

- A user-supplied CSV or its declared availability timestamps are **not**
  authenticated by SHA-256. Independent capture/provenance must be verified.
- The private journal only detects reuse within that particular journal; a
  user can copy/reset it or create a fresh Foundry report. Use independently
  retained, access-controlled evidence for a stronger scientific audit.
- Purging 10 bars and checking 32-candle duplicates do not prove the period
  has never influenced prior human/model decisions, data preparation or
  strategy selection. A prospective forward trial is still needed.
- The research OHLC fill approximation is not a live order-book execution
  model. Neither positive returns nor small reported diagnostic bounds
  authorize public signals, broker connectivity, funded trading, or deployment.

For methodological context, see Halbert White, [*A Reality Check for Data
Snooping*](https://onlinelibrary.wiley.com/doi/10.1111/1468-0262.00152),
and Bailey et al., [*Pseudo-Mathematics and Financial Charlatanism: Effects of
Backtest Overfitting*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659).
The present iid-bound calculation is **not** an implementation of White's
Reality Check, a dependence-aware bootstrap, or Bailey's overfitting estimate.

### Regressions

Run `python3 -m unittest -q tests/test_mojtrade_independent_validation.py`
inside the repository (or the same test file alongside the source in offline
workspace). All regression inputs are **synthetic** and cannot serve as
independent market evidence.
