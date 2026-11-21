# R01: preregistered analysis specification and claim-boundary checklist (2026-11-15)

**Status: methodological specification only; NOT a field study, validated efficacy claim, or submission-ready manuscript.** This document does not assert that any newly proposed check has been run. All R01 outcome rows described in PR #1999 are **synthetic model outputs**.

## Estimand and unit
For each family separately (C and R1), pair policy v3 and v2 within identical climate path, bias, ET multiplier and forecast scenario. Let d_i = Y(v3,i) - Y(v2,i). Report arithmetic paired mean over the 540 scenario keys **descriptively**, and summarize the 12 path-specific means. Do not interpret 540 dependent keys as 540 independently randomized farms. If the path-specific effect is heterogeneous, report the distribution rather than suppressing it.

## Auditable evidence matrix (20 independently falsifiable gates)
| ID | Check and acceptance criterion | Evidence required | Status |
|---|---|---|---|
| G01 | Original C export byte SHA-256 matches independently frozen manifest | author-held manifest + digest | UNVERIFIED |
| G02 | Original R1 export byte SHA-256 matches independently frozen manifest | author-held manifest + digest | UNVERIFIED |
| G03 | Raw export license/ownership and permitted publication scope documented | signed permission | UNVERIFIED |
| G04 | C has 1620 rows with unique policy×scenario keys | original CSV audit | UNVERIFIED this cycle |
| G05 | R1 has 2160 rows with unique policy×scenario keys | original CSV audit | UNVERIFIED this cycle |
| G06 | Exactly 540 v2-v3 paired keys per family, no unmatched keys | join audit | UNVERIFIED this cycle |
| G07 | Exactly 12 climate paths per family; path identifiers immutable | original metadata | UNVERIFIED this cycle |
| G08 | Climate class assignments equal original metadata | source crosswalk | UNVERIFIED this cycle |
| G09 | Units water m³, drainage mm, counts in days/events consistent | schema + code inspection | UNVERIFIED this cycle |
| G10 | All missing/nonfinite values rejected or disclosed | parser output | UNVERIFIED this cycle |
| G11 | Full original generator replay reproduces archived exports | generator + pinned environment | UNVERIFIED |
| G12 | Random seeds, path weather and configuration recorded | versioned inputs | UNVERIFIED |
| G13 | At every decision time, controller inputs were observable ex ante | timestamped data lineage | UNVERIFIED |
| G14 | Both policies receive identical forecast information sets | paired controller trace | UNVERIFIED |
| G15 | Water balance residual within predeclared tolerance per path | daily flux ledger | UNVERIFIED |
| G16 | Paired water, Q98/Q100, irrigation and drainage results recomputed | independent script + source | UNVERIFIED this cycle |
| G17 | Leave-one-path-out values recomputed without claiming inferential CI | 12 deletions/family | UNVERIFIED this cycle |
| G18 | Cluster-aware uncertainty method specified and justified; 12 paths is small | statistical review | UNVERIFIED |
| G19 | Field calibration/independent validation exists before field efficacy claims | measurements + protocol | UNVERIFIED |
| G20 | Economic evaluation includes costs, prices, uncertainty and author sign-off | auditable cost model | UNVERIFIED |

**Status semantics:** UNVERIFIED this cycle is not FAILED. Earlier PR descriptions may report historical checks; they are not independently re-established by this specification.

## Statistical analysis plan
1. Freeze source files and hashes before computing outcomes; retain original files read-only.
2. Define primary endpoints before inspection: simulated applied water volume (m³) and modeled threshold-exceedance days (Q98 and Q100), with tradeoff interpretation. Secondary: modeled irrigation events and drainage (mm).
3. Use paired differences per identical scenario key. Display means, medians, min/max and climate-class stratification for C and R1 separately; avoid pooling unlike families.
4. Aggregate within each of 12 climate paths before any path-level inference. Provide all 12 path estimates and leave-one-path-out sensitivity. Do not call leave-one-out an uncertainty interval.
5. If formal inference is requested, specify an independently defensible climate-path sampling model and small-cluster method in advance; do not manufacture p-values or confidence intervals.
6. Conduct a decision-time leakage audit: realized same-day rainfall is not a legitimate forecast unless demonstrably issued before irrigation decisions. Rerun both controllers under the same information set before prospective comparisons.
7. Reconcile modeled applied water, ET, runoff, soil-water storage change and drainage at daily and seasonal scales, with sign conventions and units documented.
8. For economic claims, specify pumping energy, labor, capital depreciation, water tariff, yield response and market price with provenance and sensitivity bounds; absent these inputs, profit is **not estimable**.

## Manuscript-safe interpretation
In archived synthetic scenarios, v3 may reduce modeled threshold-exceedance days while increasing irrigation frequency, drainage and/or applied water. Such outcomes are a multi-objective simulation tradeoff, not measured water conservation, yield improvement or farm profit. The analysis is not a randomized field experiment, and scenario keys are not independent farms.

## Source anchors (not newly retrieved or independently verified here)
- Allen, R.G. et al. (1998). *Crop evapotranspiration: Guidelines for computing crop water requirements*. FAO Irrigation and Drainage Paper 56. https://www.fao.org/4/x0490e/x0490e00.htm
- Cameron, A.C. & Miller, D.L. (2015). A practitioner's guide to cluster-robust inference. *Journal of Human Resources*, 50(2), 317–372. https://doi.org/10.3368/jhr.50.2.317
- PR #1999 historical synthetic-source and arithmetic description: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1999

No manuscript submission, production deployment, merge, payment, trade or external email is authorized by this document.
