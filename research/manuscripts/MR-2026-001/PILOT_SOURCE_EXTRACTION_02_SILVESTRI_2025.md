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

## Resolved Table 3 source reconciliation (2026-10-24; manuscript still on hold)

A second source read of the NLM/PMC **Table 3** and the publisher-indexed full text has now established that the four observed sector volumes are **4,479; 11,486; 10,931; 23,757 L/row**. Their sum is **50,653** and mean is **12,663.25 L/row** (the published table rounds to **12,663**). The paragraph immediately before Table 3 instead prints **1,663 L/row**. **This is a confirmed inconsistency between published prose and the published table**, not a verified publisher erratum.

The same table's four-sector totals are **24,700 L/row** (Mamdani counterfactual) and **21,775 L/row** (ANFIS counterfactual). Independent arithmetic using the table totals yields **51.24%** and **57.01%** model-implied reductions, respectively; the narrative's **51.25%** and **57.03%** differ slightly. Do not claim this establishes a numerical correction without original precision and any publisher response.

**Most important:** Section 5.1 labels the DSS scenarios retrospective **counterfactual simulations**, not irrigation reductions directly measured after actual farmer adoption. The field-observed baseline is provenance **M**, but simulated DSS effects are **P**; farmer adherence and sustained uptake remain **U**. Sector 4 also shows **33 modeled critical days for ANFIS versus 29 observed**, which must be retained as a possible adverse modeled trade-off.

Full four-row transcription, source locations, equations and standard-library verification script: [TABLE3_SOURCE_QA_RECONCILIATION_2026-10-24.md](TABLE3_SOURCE_QA_RECONCILIATION_2026-10-24.md) and [verify_silvestri_table3.py](verify_silvestri_table3.py). Publisher PDF visual inspection, human second extraction and erratum check remain pending. This source QA is not a formal inclusion decision or a journal submission.

## Next-step verification checklist

- [x] Independently transcribe Table 3 four sector-level rows and totals from PMC/publisher-indexed HTML (see linked source QA).\n- [ ] Visually inspect the publisher PDF Table 3 and confirm the status of any correction/erratum.
- [x] Reconcile arithmetic against published Table 3; observed prose baseline is inconsistent with table.\n- [ ] Check for any publisher erratum or author response before alleging a published correction.
- [ ] Inspect Methods 5.1 and data availability for the exact observed-vs-counterfactual boundary.
- [ ] Have a human second extractor check source passages and resolve disagreements.
- [ ] After protocol freeze, determine if the validation-only stratum includes retrospective counterfactual DSS evaluations; do not contaminate the field-adoption denominator.
- [ ] Verify if this primary paper is indexed by the **actual executed** database searches; its discovery here is not a PRISMA retrieval count.

**Scientific-integrity status:** This chart describes an article by Silvestri and colleagues, **not** original fieldwork by Mojtaba Roozegar. No DOI, outcome, data collection, independent review, or manuscript submission is claimed for MR-2026-001.
