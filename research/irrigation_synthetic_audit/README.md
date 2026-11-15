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
# Run from the Saeit repository root with locally supplied, author-held CSVs.
python3 research/irrigation_synthetic_audit/paired_scenario_audit.py \
  --cohort-c /secure/path/CohortC1620.csv \
  --regime-r1 /secure/path/RegimeR2160.csv \
  --verify-paper > audit_results.json
python3 -m unittest -v research.irrigation_synthetic_audit.test_paired_scenario_audit
```

**Live workbook nomenclature:** Python family `R1` corresponds to actual
`RegimeR2160` scenario identifiers beginning with `R-`, not `R1-`.
See [SOURCE_CROSSWALK_20261115.md](SOURCE_CROSSWALK_20261115.md) for the
2026-11-15 direct live-data read and the limitations of its checks.
The `--verify-paper` switch compares numeric postprocessing checkpoints; it
must not be described as weather/controller replay, field calibration, or
peer-review verification.

The checker requires no dependencies outside Python's standard library.
It rejects malformed numeric fields, duplicate policy/scenario rows, missing
policies, overlong CSV rows, invalid climate-factor settings, cap violations,
incomplete climate factorials and disagreement with manuscript numeric
checkpoints. If no crossing scenario exists, its median switching threshold is
`null` instead of an invented number or an uncaught exception. The JSON also
includes paired differences summarized for each of the twelve climate paths
in each family, without treating those paths as 540 independent farm samples. It computes
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


## Independent educational enterprise-budget tool (not an R01 result)

A separate, dependency-free companion in this repository offers **transparent
farm-economics arithmetic from user-entered inputs**:

- `farm_enterprise_budget.py` — gross return, water and electricity cost,
  gross margin, net return *after entered allocated fixed costs*, break-even
  crop price/yield, physical irrigation-water productivity, and controlled
  same-crop/season/currency/area comparisons.
- `farm_enterprise_report_cli.py` — offline report generator accepting one
  local JSON baseline and an optional local JSON alternative. Duplicate JSON
  keys, nonfinite values, malformed decimals, unapproved currencies, symlink
  inputs and oversized files are rejected.
- `test_farm_enterprise_budget.py` and `test_farm_enterprise_report_cli.py`
  — standalone Python standard-library regressions.
- `FARM_ENTERPRISE_WATER_ECONOMICS_CHAPTER_FA_EN_20261115.md` — bilingual
  teaching chapter with explicitly fictional calculations and scientific limits.

**This utility does not ingest R01's 3,780 synthetic policy records as
measured farm costs or profits. No live farm input, contract, payment,
published journal submission, website deployment or verified customer sale is
implied.**

For a locally authorized scenario file with exact fields specified in
`FarmScenario`:

```bash
python3 -m research.irrigation_synthetic_audit.farm_enterprise_report_cli \
  --baseline /secure/input/scenario.json > /secure/output/enterprise-report.json
python3 -m unittest -v \
  research.irrigation_synthetic_audit.test_farm_enterprise_budget \
  research.irrigation_synthetic_audit.test_farm_enterprise_report_cli
```

A report may be offered as educational modeling **only after** legal rights,
input provenance, quotation terms, supported delivery and payment permissions
are separately approved. Its `payment_collected` and
`source_inputs_verified` fields are always false.
