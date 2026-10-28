# AE-2026-001 C18 — Alternative reference and symmetric shift-share sensitivity

**Date:** 26 October 2026. **Input:** source-locked 217-economy official WDI panel, SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. Same 153 baseline and 169 eligible 2019/2023 economies as C15/C16. This is an **additional exploratory accounting sensitivity**, not a new estimator, causal decomposition or historical-vintage result.

## Scientific question and exact formulas

C16 chose baseline regional means to decompose the pooled-minus-baseline equal-country mean gap. Because the decomposition is reference-dependent, the **equally valid pooled-reference identity** uses `Δ = Σ_r (w_P,r−w_B,r)m_P,r + Σ_r w_B,r(m_P,r−m_B,r)`. The **symmetric reference** is the arithmetic average of the baseline- and pooled-reference composition and within-region terms. Both identities must equal the same total gap. This test addresses the C17 AI-review criticism of arbitrary reference selection.

## Computed findings (annual log-percentage points)

| Sample | Reference | Region composition | Within-region sample means | Exact gap |
|---|---|---:|---:|---:|
| All 169 | Baseline means (C16) | **−0.044876** | **+0.313283** | **+0.268407** |
| All 169 | Pooled means (C18) | **−0.001310** | **+0.269717** | **+0.268407** |
| All 169 | Symmetric (C18) | **−0.023093** | **+0.291500** | **+0.268407** |
| Excluding CAF/DJI, 167 (post hoc) | Baseline | −0.032963 | +0.039134 | +0.006171 |
| Excluding CAF/DJI, 167 (post hoc) | Pooled | −0.023497 | +0.029668 | +0.006171 |
| Excluding CAF/DJI, 167 (post hoc) | Symmetric | −0.028230 | +0.034401 | +0.006171 |

**Interpretation:** The *size* of the composition contribution depends materially on the chosen reference, from −0.044876 to −0.001310 log-pp/y, while the within-region component remains positive and accounts for the bulk of the full-sample gap under all three accounting conventions. The apparent mean gap remains extremely sensitive to CAF/DJI; their exclusion is **post hoc only**, not a recommendation to discard them. No inference about missingness causes, regional economic mechanisms, global productivity or independent ILOSTAT vintages is justified.

## Reproduction and status

The actual arithmetic was independently calculated on the same GitHub source CSV with both identities checked. Reproducible fail-closed standard-library implementation: `analysis/ae_2026_001_c18_reference_decomposition.py`, with source SHA256 and 153/16 gates; GitHub workflow `.github/workflows/ae-2026-001-c18-reference-sensitivity.yml`. **Do not claim successful Actions execution or an artifact until separately verified.** This is a supplementary robustness analysis; it does not establish publication novelty over countryatlas or alter the **MAJOR REVISION / NO SUBMISSION** decision.
