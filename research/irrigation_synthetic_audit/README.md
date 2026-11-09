# Synthetic irrigation scenario audit — verification package

This archive is a **private, author-review computational appendix** to the
irrigation scheduling manuscript. It does not report field measurements,
experimental trials, realized crop yield, verified water savings, or profit.

## Input files and origin

The two CSV inputs are a 6 November 2026 snapshot of the existing author-owned
Google Sheets workbook `ZM-IRR-MODEL-2026-01 — Research Data Workbook — 4260 Records`:

https://docs.google.com/spreadsheets/d/1NC1pgdb1Dkhk1HdgdF_sFvnx1i86O88u_fgVdxvvKQA/edit

| File | Rows excluding header | Policy scenarios | Matched scenario keys |
| --- | ---: | ---: | ---: |
| `CohortC1620.csv` | 1,620 | 3 | 540 |
| `RegimeR2160.csv` | 2,160 | 4 | 540 |

Rows encode simulated **policy–scenario outcomes**. A matched key comprises
the climate-path ID, seed, climate class, volumetric soil-sensor bias,
ET forecast factor and rainfall-information case. All keys are replayed
under the policies of their own family. The 540 keys in a family are a
structured factorial grid with only 12 climate paths, **not 540 independent
farm trials**.

## Run

```bash
python3 paired_scenario_audit.py \
  --cohort-c CohortC1620.csv \
  --regime-r1 RegimeR2160.csv \
  --verify-paper > audit_results.json
python3 -m unittest -v test_paired_scenario_audit.py
```

The checker requires no dependencies outside Python's standard library.
It rejects malformed numeric fields, duplicate policy/scenario rows, missing
policies, invalid climate-factor settings, cap violations, incomplete climate
factorials and disagreement with manuscript numeric checkpoints. It computes
means, water/Q Pareto comparisons, eight illustrative post hoc decision weights,
break-even weights, and climate-stratified preferences. Output includes SHA-256
digests for the **exact snapshot CSV bytes**; these digests do not constitute
hashes of the original Google Sheets backend or an already-submitted journal file.

## Interpretation and limits

* `Q100` is a prescribed simulated below-100-mm end-storage count, not a
  field-measured stress or yield response.
* `V + lambda*Q100` is an illustrative proxy loss, not a currency valuation,
  causal treatment-effect estimator or agronomic recommendation.
* The checker post-processes archived outcomes; it does **not** independently
  reconstruct the weather generator, controller day-level simulation or input
  archive. That deeper reproducibility remains a separate requirement.
* The snapshot is prepared for technical author review. Journal appendices,
  external redistribution, public release, licensing and revised submission
  remain separate author/editorial decisions.

