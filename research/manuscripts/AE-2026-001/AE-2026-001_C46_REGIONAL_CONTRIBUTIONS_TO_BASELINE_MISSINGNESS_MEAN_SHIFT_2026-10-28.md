# AE-2026-001 C46 — Regional contributions to the 2019–2023 baseline-availability mean shift

**28 October 2026 | Independent computation on existing official WDI 2026 snapshot | MAJOR REVISION / NO SUBMISSION**

## Source, scope, and genuinely incremental result
Source: `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, blob SHA `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`; 217 nonaggregate economy/territory records. Values are the existing WDI `NV.AGR.EMPL.KD` 2026 snapshot, **not independently measured employment** and not an archival ILOSTAT release. For each strictly positive 2019 and 2023 pair, compute `g_i=100*ln(y2023/y2019)/4` in annual log-percentage points. A positive 2000 observation identifies the 153-case balanced group B; the 16 additional 2019/2023 observations form group M. The 169-case group is B union M.

C45 previously established the overall means (169: 0.810142320409; 153: 0.541735421491; 16: 3.3767832913), median contrast and regional membership. **New in C46:** a source-recomputed, exact *region-level additive decomposition* of the overall mean selection shift, not another count of C45 results.

Let `mu_B=mean(g_i | i in B)`, `N=169`, and `M_r` be the baseline-missing cases in region r. Define
`contribution_r = [sum_{i in M_r} g_i - |M_r|*mu_B]/169 = (|M_r|/169)*(mean(g_i | M_r)-mu_B)`.
Then `sum_r contribution_r = mean(g_i | B union M) - mean(g_i | B)` **exactly**, without a causal or random-missingness assumption.

| WDI region | Added M cases | Mean added growth (log-pp/year) | Exact contribution to 169-vs-153 mean difference (log-pp/year) |
|---|---:|---:|---:|
| East Asia & Pacific | 2 | -5.847537 | -0.075613 |
| Europe & Central Asia | 2 | 4.876674 | +0.051301 |
| Latin America & Caribbean | 0 | n/a | 0 |
| Middle East, North Africa, Afghanistan & Pakistan | 5 | 5.474357 | +0.145936 |
| North America | 0 | n/a | 0 |
| South Asia | 0 | n/a | 0 |
| Sub-Saharan Africa | 7 | 4.085496 | +0.146783 |
| **Total** | **16** | **3.376783** | **+0.268407** |

Independent JavaScript execution on the GitHub-fetched CSV gave: N=217 source rows, 169 positive 2019/2023 pairs, 153 with positive 2000 baseline, 16 without, `mu_B=0.5417354214909473`, `mu_all=0.8101423204089023`, difference `0.2684068989179550`; sum of regional contributions `0.26840689891795516` (floating-point tolerance). These values are a direct computation, not a claim that a separately committed Python script or R workflow ran.

## Interpretation and critical limits
- The positive contributions from Sub-Saharan Africa (+0.146783) and MENA/Afghanistan/Pakistan (+0.145936) are partly offset by East Asia/Pacific (-0.075613); these are **accounting contributions** relative to the *global balanced-panel mean*, not region-specific causal effects or equal-region standardized estimates.
- The mean shift is much larger than the **median shift of +0.084671** documented in C45. Do not transfer mean decomposition to the median.
- Selection is nonrandom and the 16 cases are concentrated in four regions; no causal explanation for missing 2000 endpoints is identified.
- This analysis **does not** resolve historical 2024/2025 WDI release identity, ILOSTAT employment-source dependence, countryatlas direct benchmark or novelty. It must not be presented as a novel estimator or an independently verified global growth trend.
- C13/C14 availability masks, C45 cohort means and the original data are prior work; only the **regional decomposition** is new here.

**Editorial disposition:** permissible as an explicitly descriptive sensitivity paragraph, not as a standalone discovery or evidence for journal submission. Human author approval and all release gates remain outstanding.
