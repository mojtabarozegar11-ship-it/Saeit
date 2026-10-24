# MR-2026-001 — Silvestri et al. (2025) Table 3 source-and-arithmetic reconciliation

**Prepared/checked:** 2026-10-24 (UTC date). **Scope:** one independently re-read published article and a transparent arithmetic audit of its Table 3. **Status:** source QA, not a systematic-review search, final eligibility decision, author correction, independent human double extraction, or evidence of original fieldwork by Mojtaba Roozegar.

## Bibliographic and source provenance

Silvestri R, Vecchio M, Pincheira M, Antonelli F. *Smart Irrigation with Fuzzy Decision Support Systems in Trentino Vineyards*. **Sensors**. 2025;25(23):7188. DOI: [10.3390/s25237188](https://doi.org/10.3390/s25237188); PMCID: [PMC12693864](https://pmc.ncbi.nlm.nih.gov/articles/PMC12693864/).

- Publisher full text: https://www.mdpi.com/1424-8220/25/23/7188 — Section 5.1 (counterfactual what-if), Section 6 (results), Table 3 and Table 4.
- NLM archived full-text Table 3: https://pmc.ncbi.nlm.nih.gov/articles/PMC12693864/ — Section 6 / Table 3. The web-indexed PMC text exposed all four sector rows and the total/average row, which was cross-checked against the publisher-indexed text.
- Publisher PDF page image and supplemental data were **not** independently inspected during this audit. The publisher's formal errata/corrigenda status has **not** been established.
- Source observation is **not** the same as independent verification of raw data or model validity. All quantities below are numbers *reported by Silvestri et al.*, not newly collected by MR-2026-001.

## Table 3 — faithful numerical transcription (water volume, L per row)

| Vineyard sector | Observed irrigation | Simulated Mamdani IDSS_M | Simulated ANFIS IDSS_TS |
| --- | ---: | ---: | ---: |
| 1 | 4,479 | 1,300 | 975 |
| 2 | 11,486 | 5,200 | 4,875 |
| 3 | 10,931 | 9,750 | 9,100 |
| 4 | 23,757 | 8,450 | 6,825 |
| **Published total** | **50,653** | **24,700** | **21,775** |
| **Published rounded average** | **12,663** | **6,175** | **5,444** |

**Verified within-table consistency:** adding the four displayed sector entries reproduces each printed total. Dividing totals by four gives observed **12,663.25**, Mamdani **6,175**, ANFIS **5,443.75** L/row; the published integer averages are consistent with rounding.

**Verified prose/table discrepancy:** The paragraph immediately before Table 3 says the observed average was **1,663 L/row**. Table 3 prints **12,663 L/row** and its sector totals imply **12,663.25 L/row**. Thus the paragraph's observed baseline is inconsistent with the source's own Table 3. The plausible missing leading digit is **an inference**, **not a published correction**. Never silently alter the quotation, and do not state that the authors have acknowledged an erratum.

**Arithmetic from published table totals** (computed independently, not reproduced simulations):

`percent reduction = 100 × (observed_total − simulated_total) / observed_total`

- Mamdani: `100 × (50,653 − 24,700) / 50,653 = 51.23684678...%` → **51.24%** from printed sector totals.
- ANFIS: `100 × (50,653 − 21,775) / 50,653 = 57.01143071...%` → **57.01%** from printed sector totals.
- The article's prose reports **51.25%** and **57.03%**. These differ by approximately **0.013** and **0.019 percentage points**, respectively, from recomputation using the displayed integer table entries. Such small discrepancies do not justify an allegation of error without the original calculation precision and aggregation rule.
- Using the paragraph's **1,663** as the baseline instead would yield *negative* reductions of roughly **−271.3%** and **−227.4%** against 6,175 and 5,444. This confirms why the prose baseline must not be used uncritically.

## Crucial interpretation for the review

Section 5.1 explicitly calls the treatment scenarios a **counterfactual 'what-if' simulation** based on historical 2023 sensor/irrigation records. The observed farmer-managed baseline is field-recorded; the two proposed DSS schedules and associated water/soil-tension outcomes are **model-generated**, not demonstrated on-farm changes after implementing those schedules. Therefore:

- Baseline irrigation: provenance **M** (observed field records, as reported).
- DSS irrigation volumes, critical days, and simulated savings: provenance **P** (model-predicted).
- Actual farmer adherence to either simulated schedule: **not established** in the inspected evaluation; **do not code O**.
- Sustained voluntary adoption, yield change, profit change: **not established** by these comparisons; mark **U**, not zero.
- Sector 4's simulated ANFIS schedule shows **33 critical days vs 29 observed** (Table 3), an adverse modeled stress trade-off that must not be omitted.

**Review synthesis boundary:** this paper can inform a separately labeled *counterfactual/model-validation evidence stratum* if the final protocol permits it. It must **not** contribute to a denominator of measured on-farm water savings or observed farmer adoption. If excluded from the primary field-deployment stratum, preserve the reason and bibliographic link in the search/screening log after a real search is run.

## Reproducibility

Companion standard-library script: [verify_silvestri_table3.py](verify_silvestri_table3.py). It checks the four-row totals, rounded means, the observed-baseline mismatch, and reduction calculations without accessing a database or fabricating a PRISMA record.

**Still required:** human second extraction; original publisher PDF/Table 3 visual check; any publisher correction/author clarification; formal eligibility adjudication after protocol freeze; actual two-database search/export and logged screening. No external journal submission or manuscript ID exists on the basis of this QA.

## Draft manuscript-safe wording (not final Results)

> In one retrospectively evaluated vineyard irrigation DSS study, observed irrigation records were compared with counterfactual model-generated recommendations rather than with irrigation outcomes measured after implementation of the recommendations (Silvestri et al., 2025). Such studies may inform model validation but cannot alone establish realized on-farm water savings or sustained farmer adoption. The source's narrative observed-baseline value is inconsistent with its tabulated average; consequently, the source's tabulated values and uncertainty must be reviewed before any numerical synthesis.

**Authorship and integrity:** This is a secondary check of the cited authors' published material. It neither transfers ownership of the primary study nor asserts a novel measured treatment effect.
