# AE-2026-001 C48 — Exact minimum-deletion fragility of the 169-versus-153 mean contrast

**2026-10-28 | Internal source-locked descriptive sensitivity | MAJOR REVISION / NO SUBMISSION**

## Precise estimand and original data
The sole input is the committed 217-economy 2026 WDI CSV `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv` (Git blob `d4910ff78219f9e5097c6301a6fbfa7752bbf4f9`; file SHA256 `715ff36b3b817dcf58a4170eadad872b0bd629bd66a424a73fac077dac869169`). Positive 2019/2023 values define 169 economies. Of these, 153 have positive 2000 values (baseline-observed B) and 16 lack the 2000 baseline (M). The annual growth measure is `g=100*ln(P2023/P2019)/4` in log-percentage-points per year. B's mean is held fixed at 0.5417354214909473. The original 169-case mean is 0.8101423204089023; the original difference is +0.268406898917955.

## New exact deletion result (executed directly against GitHub-fetched source rows)
For each k, delete the k *largest-growth* members of M only, then recompute the mean over the remaining `169-k` economies; B remains untouched. This is a deliberately adversarial diagnostic, **not** an objective exclusion rule, preregistered cleaning policy, or recommended sample selection.

| Deleted from the 16 baseline-missing economies | Remaining N | Mean difference versus unchanged B |
|---|---:|---:|
| None | 169 | +0.268406899 |
| CAF | 168 | +0.105647061 |
| CAF, DJI | 167 | +0.006171270 |
| CAF, DJI, GHA | 166 | **-0.030859922** |

CAF growth = +28.15379505749145, DJI = +17.259839592493087, GHA = +6.695084524539084 (same units). **Three** is the minimum number of deletions *from M* that can reverse the sign of this particular unadjusted mean contrast: for any fixed k, deleting the k largest observations minimizes the remaining sum and, with the same remaining denominator, the remaining mean. The best possible k=2 deletion still leaves +0.006171270, while k=3 crosses zero. This is an exact finite-list ordering argument, not a p-value, significance test, or causal effect.

## Critical limits and editorial decision
- These are post hoc *worst-case* exclusions chosen to stress-test fragility. They must never be presented as justified outlier removals, robust population estimates, or a prespecified model.
- The result is conditional on this dated 2026 API snapshot, the positive-endpoint definition, and the baseline-observed B comparison. It is **not** a 2024/2025 WDI vintage comparison, historical ILOSTAT validation, or countryatlas benchmark.
- It does not diagnose whether CAF/DJI/GHA values are wrong. The observed extremes could reflect actual dynamics, denominator revisions, or other factors; no adjudication is made.
- It does not identify the 48 economies lacking 2019/2023 endpoint pairs, solve missing-not-at-random identification, or support a journal-level novelty claim.
- Companion Python code `analysis/c48_minimum_deletion_sign_flip.py` fails closed on file SHA256 and cohort sizes. The values above were computed directly from the full GitHub-fetched CSV in JavaScript in this cycle; **no GitHub Actions Python execution is claimed**.

**Scientific decision:** add a transparent fragility paragraph; retain MAJOR REVISION / NO SUBMISSION pending primary WDI/ILOSTAT provenance, direct comparator, scientific author review and publication gates.
