# AE-2026-001 C20 — Internal AI critical review of C19 and revised manuscript

**Date:** 26 October 2026. **Reviewer:** AI internal methodological critique only; **not a human referee**. **Decision:** MAJOR REVISION / NO SUBMISSION.

## Positive evidence
1. The original source-locked 217-economy WDI CSV is accessible in the research branch; C19 recomputes the 153/16/169 cohorts and their 2019–2023 annual log growth.
2. The identity `mean(B∪A)-mean(B) = Σ_{i∈A}(g_i-mean(B))/169` is exact, and the directly recomputed 16 terms sum to **+0.2684068989** log-pp/year.
3. Single-added-economy deletion exposes mean sensitivity without changing the primary data. The numerical distinction between median and mean is clearly reported.
4. Methods 2.12, Results 3.22 and Limitations explicitly state post-hoc design and source-dependence.

## Major scientific objections requiring action
- **Novelty is unproven.** This identity is elementary algebra; countryatlas prior art and published WDI vintage studies require a direct estimand-level and numerical benchmark. C19 does not solve it.
- **Reference dependence:** CAF/DJI “97.73%” is a ratio of signed baseline-relative contributions to a net difference, **not** a share of causal influence, explained variance or unique economic attribution. It could exceed 100% under cancellation. The author should avoid using this ratio in an abstract/headline without its qualifications.
- **Post-hoc selection:** CAF and DJI were noticed after viewing large observations. Leave-one-out diagnostics are descriptive; no prespecified outlier rule, robust-estimator justification or source-level error confirmation is available.
- **Endpoint selection is not historical revision:** the 153/169 contrast is 2000-availability attrition within the **2026** release, not a difference between archived 2024/2025 ILOSTAT source versions. The historical-vintage mechanism remains unknown.
- **Sampling:** the country-equal-weighted mean is not worker-weighted, agricultural-output-weighted or a representative global growth estimator. The 16 additional economies are nonrandom.
- **Source overlap:** independent retrieval of ILOSTAT files does not imply independent generation of WDI employment. A head-to-head source definition and historical version audit is still required.
- **Reproducibility:** the C19 script and GitHub workflow have been committed, but a successful Actions run, artifact SHA and the latest manuscript-aligned Word are **not independently verified in this review**. They must not be asserted as completed.

## Required next scientific decisions
1. Acquire legally usable 2024 and 2025 archived ILOSTAT extracts with date, series definition, units, ISIC/source codes and checksums; if unavailable, narrow the causal/mechanistic language rather than fabricate data.
2. Run a direct numerical countryatlas comparison on a common source and cohort, documenting estimand, package version, data snapshot and nonidentical targets.
3. Reassess whether the WDI manuscript's core novelty survives existing literature, and consider repositioning as a transparent data note if it does not.
4. Verify a new source-locked Word for the updated AE text; obtain genuine human author review and declarations before any submission.

**Conclusion:** C19 is a legitimate reproducible descriptive analysis of observed sample selection, but it **does not make AE publication-ready**. No human authorship, external peer review, submission, acceptance or manuscript ID is claimed.
