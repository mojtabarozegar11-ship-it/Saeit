# MR-2026-001 — Second primary-source pilot: Silvestri et al. (2025)

**Checked:** 2026-10-24 | **Status:** publisher-full-text **pilot charting**, NOT a final inclusion decision, formal dual extraction, systematic search result, or verified numerical efficacy estimate.

## Source identity and traceability

Silvestri R, Vecchio M, Pincheira M, Antonelli F. *Smart Irrigation with Fuzzy Decision Support Systems in Trentino Vineyards*. Sensors. 2025;25(23):7188. DOI: [10.3390/s25237188](https://doi.org/10.3390/s25237188). Publisher full text: https://www.mdpi.com/1424-8220/25/23/7188 . Public archive: https://pmc.ncbi.nlm.nih.gov/articles/PMC12693864/ (PMCID PMC12693864; PMID 41374563).

**Source sections examined via publisher-indexed full text (2026-10-24):** Introduction; Section 3, Fuzzy-Based Decision Support Systems; Section 4.2, Study Area and Dataset Description; Section 5.1, Counterfactual What-If Analysis; Results/Discussion surrounding Fig. 10 and Table 3; Section 7, Conclusions; Data Availability Statement. The live publisher site intermittently rate-limited direct requests; the source-indexed publisher text was readable. Table 3 cell-by-cell and PDF/supplement verification are still required. Do not call this an independently validated full-table audit.

## Design and outcome-provenance chart

| Field | Source-grounded observation | Evidence category / limitation |
| --- | --- | --- |
| Study setting | Four vineyard irrigation sectors in Trentino, Italy; historical data 1 May–31 August 2023 | Real-world historical sensor and irrigation data; **not** four independently randomized farms |
| DSS systems | Mamdani fuzzy rule-based DSS vs Takagi–Sugeno/ANFIS DSS | Model-generated irrigation recommendations |
| Observed baseline | Recorded farmer-managed irrigation schedule and tensiometer/weather observations | **M** for field-recorded inputs and baseline events |
| Evaluation | Retrospective *counterfactual what-if simulation* driven by historical field data, with soil-tension responses forecast under hypothetical DSS decisions | **P**, not observed DSS treatment irrigation or verified field water saving |
| Bootstrap | Stratified block bootstrap of weather trajectories; 1,000 simulations reported for one sector | **P**; quantifies model-based variability, not randomized treatment uncertainty |
| Water use / critical dry days | Modeled irrigation volumes and modeled soil-tension outcomes compared with observed management | Mixed **M baseline + P DSS**; do not code as measured intervention effects |
| Adoption / recommendation adherence | No independently observed farmer adherence to both hypothetical DSS schedules established in sections reviewed | **U** (unestablished), not a measured adoption outcome |
| Crop yield, profit, energy | No independent comparative field measurements established in sections reviewed | **U**; cannot infer farm-level economic benefit |
| Generalizability | Four local sectors; model trained on local data; commercial-project data not readily accessible | Local, retrospective; reproducibility and transportability constrained |

**Coding rule:** A study can use authentic field data and still have **simulated treatment outcomes**. Do not let the phrases “field-based” or “real-world” substitute for observed implementation. This study should be evaluated for a **validation-only / counterfactual stratum** under the draft eligibility rules, not automatically counted as a field intervention or adoption study.

## Critical internal numeric-consistency flag (requires verification, NOT an allegation)

The publisher-indexed Results paragraph around **Table 3** states an observed average of **1,663 L/row**, simulated Mamdani **6,175 L/row**, and simulated ANFIS **5,444 L/row**, yet reports **51.25%** and **57.03%** savings relative to the observed baseline. Taken literally, both simulated volumes **exceed** 1,663 L/row; they cannot represent savings against that denominator.

Reproducible arithmetic using *only the numbers printed in that paragraph*:

- `100 * (1 - 6175/1663) = -271.3%` (negative saving = increased use).
- `100 * (1 - 5444/1663) = -227.4%`.
- Implied observed baselines if the stated positive savings percentages were correct: `6175/(1-0.5125) ≈ 12666.7 L/row` and `5444/(1-0.5703) ≈ 12669.3 L/row`.

These are **internal reconciliation calculations, not empirical estimates**. The indexed paragraph may contain a missing digit, an aggregation/unit mismatch, or a publisher rendering issue. **Do not silently replace 1,663 with a guessed value.** Retrieve and compare the publisher PDF Table 3, table notes and any erratum, and if necessary request clarification from the original authors before transcribing any water-saving percentage into MR-2026-001.

The study also reports that in one sector the more conservative ANFIS schedule had **more critical dry days than observed management**. Preserve potential adverse outcomes and model assumptions in any future evidence map.

## Next-step verification checklist

- [ ] Open publisher PDF and independently transcribe all four sector-level rows of Table 3, including units, baseline, and denominators.
- [ ] Reconcile the baseline arithmetic with original Table 3; log any erratum or author response; do not publish a correction allegation without evidence.
- [ ] Inspect Methods 5.1 and data availability for the exact observed-vs-counterfactual boundary.
- [ ] Have a human second extractor check source passages and resolve disagreements.
- [ ] After protocol freeze, determine if the validation-only stratum includes retrospective counterfactual DSS evaluations; do not contaminate the field-adoption denominator.
- [ ] Verify if this primary paper is indexed by the **actual executed** database searches; its discovery here is not a PRISMA retrieval count.

**Scientific-integrity status:** This chart describes an article by Silvestri and colleagues, **not** original fieldwork by Mojtaba Roozegar. No DOI, outcome, data collection, independent review, or manuscript submission is claimed for MR-2026-001.
