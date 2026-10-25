# AE-2026-001 — independent official-data robustness audit and adversarial originality decision

**Date:** 2026-10-25. **Status:** completed supplementary descriptive sensitivity computation on actual, archived World Bank WDI country observations; not scientific proof of a new theory, not a causally identified finding, not an author-approved or submitted article. AI reviewer separate from existing empirical-manuscript drafting; human author must critically re-evaluate the research claims.

## Input and exact computations
Input file: `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv` (217 named non-aggregate World Bank economy entries; 2000/2019/2023 observations for `NV.AGR.EMPL.KD`; 153 positive complete observations across all three years). Re-read the **actual committed CSV from GitHub**, parsed every row and independently computed annualized log growth `g_i(2000,t) = ln(y_it / y_i2000)/(t - 2000)`. No simulated values, copied web-country estimates, unweighted-into-worker-weighted substitutions or inferred causal effects were used.

Reproducible **Python standard-library** script (requires only the archived actual input): `analysis/wdi_geographic_robustness_from_archived_real_panel.py`. Independent execution CI specification: `.github/workflows/ae-2026-001-archive-backed-sensitivity.yml`. **Independent CI evidence verified:** GitHub Actions [run 40215198124](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40215198124), completed **2026-10-25 17:10:53 UTC**, conclusion **success**. Its `reproducibility-check` job executed the exact committed Python script against the archived real WDI CSV and uploaded [artifact 12606854021](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40215198124/artifacts/12606854021) (`AE-2026-001-WDI-geographical-robustness`, 1,760-byte ZIP; artifact digest `sha256:b8c5d36ee131a1bda998147857b137f36eff01429df3d79e17b142ba4ace7ec0`). The decoded job log confirms all seven region-exclusion values and the 5%-tail-trimming results reported below. This is a **verified computational reproducibility exit** only, not verification of publication novelty or journal acceptance.

### A. Country coverage and balanced sample: direct recomputation
| Estimand | Country pairs | Median annual log growth | Mean annual log growth |
|---|---:|---:|---:|
| 2000–2019, all available pairs | 157 | 0.023555752946417118 | 0.023984983654433946 |
| 2000–2023, all available pairs | 153 | 0.022244837043986730 | 0.020785340670841517 |
| 2000–2019, SAME 153 countries with all three years | 153 | 0.023555752946417118 | 0.024020706240511433 |
| 2000–2023, SAME 153 countries with all three years | 153 | 0.022244837043986730 | 0.020785340670841517 |

**Interpretation:** Four additional country pairs for the earlier interval alter its mean slightly but **not** its median at the displayed precision; thus it is misleading to attribute the difference between the two median rates chiefly to country entry/attrition.

### B. Entire-region exclusion robustness on the same 153-country sample
Values below are annualized **log changes**, not percent differences or genuine measured productivity at individual farms. `Δ` is 2000–2023 median minus 2000–2019 median; both windows begin in 2000 and overlap, so Δ **cannot be called the stand-alone impact of 2019–2023 events**.

| Whole World Bank region excluded | Countries remaining | Median, 2000–2019 | Median, 2000–2023 | Δ |
|---|---:|---:|---:|---:|
| None | 153 | 0.023556 | 0.022245 | −0.001311 |
| East Asia & Pacific | 131 | 0.023617 | 0.023054 | −0.000564 |
| Europe & Central Asia | 108 | 0.017299 | 0.015483 | −0.001816 |
| Latin America & Caribbean | 125 | 0.027116 | 0.023946 | −0.003170 |
| Middle East, North Africa, Afghanistan & Pakistan | 138 | 0.023587 | 0.021960 | −0.001627 |
| North America | 152 | 0.023507 | 0.021960 | −0.001547 |
| South Asia | 147 | 0.023457 | 0.021675 | −0.001783 |
| Sub-Saharan Africa | 117 | 0.027119 | 0.024433 | −0.002686 |

**Nontrivial descriptive result:** Excluding Europe & Central Asia shifts the balanced-sample median over 2000–2019 from about **2.36 to 1.73 log-percentage-points per year**, whereas excluding Latin America/Caribbean yields **2.71**. This is *composition sensitivity*; no statistical hypothesis test or causal region contribution is implied. North America contributes only ONE complete economy in this WDI country-classification snapshot; it does not represent its whole region.

### C. Robustness to tails and regionally uneven coverage
Removing the outermost **seven observed economy rates from each tail** (5% of 153 rounded down) and recomputing on 139 remaining economies:

| Year endpoint | Untrimmed balanced mean | Trimmed mean | Median (both) |
|---|---:|---:|---:|
| 2019 | 0.024020706240511433 | 0.024140554927116720 | 0.023555752946417118 |
| 2023 | 0.020785340670841517 | 0.021260027906917132 | 0.022244837043986730 |

Country coverage differs notably by region: of 37 East Asia/Pacific economies 22 have all three years; 45/58 Europe/Central Asia, 28/42 Latin America/Caribbean, 15/23 MENA/Afghanistan/Pakistan, 1/3 North America, 6/6 South Asia, and 36/48 Sub-Saharan Africa. A balanced panel retains an already selected group and does not correct these regional coverage differences.

## Scientific novelty decision: NOT YET DEMONSTRATED

**Overlapping primary prior art (explicitly challenged):**

- **Dieppe & Matsuoka (2025), Empirical Economics**, DOI [10.1007/s00181-024-02692-y](https://doi.org/10.1007/s00181-024-02692-y), already reports convergence and sectoral reallocation in agriculture and studies panel construction. Their scope, estimands and sector dataset differ; our study is not the first investigation of agriculture's productivity evolution.
- **Inklaar & Marapin (2025), STEG Working Paper 121**, [official PDF landing page](https://steg.cepr.org/publications/accounting-productivity-convergence-role-sectors-and-structural-change) provides 66-country 1990–2018 sector-specific convergence analyses; it already discusses labor productivity and sector-composition effects.
- **Lagakos & Waugh (2013), American Economic Review**, DOI [10.1257/aer.103.2.948](https://doi.org/10.1257/aer.103.2.948), models selection effects affecting measured cross-country agricultural productivity differences.
- **USDA ERS (2026) International Agricultural Productivity** [official data documentation](https://ers.usda.gov/data-products/international-agricultural-productivity) provides a different productivity concept—multi-input **total factor productivity**, not WDI sector value added per worker. Conflating the two would invalidate cross-dataset comparisons.

**Adversarial editorial disposition:** a descriptive three-year WDI trend plus a conventional leave-one-region-out sensitivity test does **not currently establish publication-grade methodological or theoretical novelty** for a conventional Research article. Treat it as a genuine *reproducible empirical audit* whose potential contribution would be quantitative documentation of selection/coverage vulnerability at a specific WDI vintage. Before submission, the human author must select a sufficiently differentiated falsifiable question and evaluate comparable existing coverage-sensitivity methods; a journal may accept an appropriately framed Data Note/Brief Report only if its article-type requirements, reproducible data rights and editorial originality standards are met. Do not claim first-ever country panel, first convergence finding, causal agricultural policy effect or proof of 2019–2023 slowdown.

**Next scientific gate:** systematic cross-vintage comparison using immutable older WDI snapshots OR independent uncertainty/measurement-sensitivity validation with honestly differentiated estimands and a second comparison dataset (e.g. USDA TFP only with concept distinction). If an incremental finding cannot be established, terminate or redesign the paper rather than fabricate novelty. No journal submission or Manuscript ID.
