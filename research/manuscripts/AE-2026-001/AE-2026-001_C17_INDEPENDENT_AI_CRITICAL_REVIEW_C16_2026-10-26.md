# AE-2026-001 C17 — Critical internal AI review of C16 region decomposition

**26 October 2026 | AI internal review, not human peer review | Verdict: MAJOR REVISION / NO SUBMISSION**

## Verified object of review

[C16 source-locked descriptive decomposition](AE-2026-001_C16_REGION_STANDARDIZED_COHORT_MEAN_DECOMPOSITION_2026-10-26.md) of the 2019–2023 mean-growth difference between the 153-economy three-endpoint WDI sample and the 169-economy 2019/2023 sample. Underlying source SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`. The reproducible script implements the algebraic identity and checks 217/153/16 records. Source code and analysis are **not** independent experimental replication or external peer review.

## Scientific criticism

1. **Correct but reference-dependent accounting.** The formula `Δ = Σ(w_P−w_B)m_B + Σw_P(m_P−m_B)` is an exact identity, not an identified causal Oaxaca–Blinder effect. Reversing reference group changes attribution; do not label the within-region component as a treatment effect or source of economic growth.
2. **Selection, not paired change.** All 153 baseline countries remain in the pooled 169. Added 16 economies have missing/nonpositive 2000 endpoints; their 2019–2023 rates are observed but may not be missing at random. The regional terms cannot establish why those 16 lack 2000 observations.
3. **High influence and post-selection.** Two added countries, CAF and DJI, dominate the pooled-mean sensitivity. Excluding them post hoc reduces the mean gap from +0.268407 to +0.006171 log-pp/year. They must remain in the main analysis; there is no source proof of erroneous observations.
4. **Unequal regional sample sizes.** North America contributes one country and South Asia six in the baseline. Region comparisons must not be interpreted as regional population means, regional causal effects or formal inference. Region group labels are World Bank operational classifications, not harmonized economic systems.
5. **Alternative reference decomposition needed.** For a robustness supplement, compute the equally valid pooled-reference identity `Δ = Σ(w_P−w_B)m_P + Σw_B(m_P−m_B)` and compare contributions. A symmetric average of both identities is another descriptive convention. This is a clear, testable next action; not yet performed in C16.
6. **Inferential uncertainty absent.** No prespecified sampling frame, model for missingness, error bars, multiple-testing control or preregistered hypothesis. Bootstrap resampling would be sensitivity, not global confidence intervals.
7. **Novelty constrained.** Standard shift-share decomposition and historical WDI comparison software (countryatlas) predate this application. This can strengthen transparency of a narrowly scoped data-quality case study but does not establish publishable methodological novelty.
8. **Submission gate remains.** Historical 2024/2025 ILOSTAT archived source reconstruction and a matched numeric countryatlas benchmark are still absent. The ILOSTAT and WDI employment series share source lineage; current-source agreement is not independent validation.

## Editorial decision

**Retain C16 as a transparent supplementary sensitivity, not a primary result or a new method.** Manuscript §§2.11 and 3.21 can report its numbers with the above restrictions. Do not change the main abstract or conclusion to imply global causal or regional effects. No journal submission, author signature, ORCID or publication claim.

**Next high-value scientific actions:** (i) compute pooled-reference and symmetric shift-share decompositions from the same SHA-locked source; (ii) compare medians and trimmed means without deleting outliers; (iii) obtain historical ILOSTAT archives if legally available; (iv) execute numerical matched-vintage countryatlas benchmark; (v) critical review and human author approval.
