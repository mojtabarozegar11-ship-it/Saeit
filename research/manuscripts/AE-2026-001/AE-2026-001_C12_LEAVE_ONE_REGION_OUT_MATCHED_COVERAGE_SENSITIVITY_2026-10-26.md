# AE-2026-001 C12 — Leave-one-region-out coverage-selection sensitivity

**Date:** 26 October 2026. **Type:** new secondary *sensitivity analysis* of the seven-region 157-economy source-locked summary, **not** newly downloaded observations or historical-vintage evidence. **Decision:** descriptive selection imbalance is materially concentrated in Sub-Saharan Africa, but does not vanish when that region is removed; inference to the world or to the original 155-economy historical-vintage cohort is not justified.

## Input provenance and estimand

The input is the 7×2 matched/unmatched country-count table in [C11](AE-2026-001_C11_REGIONAL_COVERAGE_CHI_SQUARE_CONTRIBUTION_AUDIT_2026-10-26.md), itself from [source-locked run 40317629788](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40317629788), artifact 12647203753. Counts in fixed order (matched/total): ECA 32/46, LAC 16/28, EAP 12/22, MENA+Afghanistan/Pakistan 6/17, South Asia 2/6, Sub-Saharan Africa 4/37, North America 1/1. Sum: 73/157. This **157-economy** current-source coverage panel must not be silently conflated with the **155-economy** three-vintage historical WDI analysis.

For each region, *delete that entire row*, recompute both margins and expected counts, then calculate Pearson X² = Σ(O−E)²/E and Cramer's V = sqrt(X²/N) for the remaining 2-column table. The 7 leave-one-out analyses have **different N and region compositions**; raw chi-square statistics are not comparable as if they shared a common sample.

| Deleted region | Remaining N | Matched | Pearson X² | Cramer's V |
|---|---:|---:|---:|---:|
| None (full seven regions) | 157 | 73 | 33.0553 | 0.4588 |
| Europe/Central Asia | 111 | 41 | 20.4388 | 0.4291 |
| Latin America/Caribbean | 129 | 57 | 31.7778 | 0.4963 |
| East Asia/Pacific | 135 | 61 | 32.5317 | 0.4909 |
| MENA/Afghanistan/Pakistan | 140 | 67 | 31.9947 | 0.4781 |
| South Asia | 151 | 71 | 32.5763 | 0.4645 |
| **Sub-Saharan Africa** | **120** | **69** | **8.4235** | **0.2649** |
| North America | 156 | 72 | 31.9296 | 0.4524 |

**Interpretation:** deleting Sub-Saharan Africa changes the descriptive association magnitude from V=0.4588 to 0.2649; deleting any other single region yields V between 0.4291 and 0.4963. The strongest driver of the original seven-region association is the low coverage of Sub-Saharan Africa, consistent with C11's cell-level decomposition; however V=0.2649 is not zero. This is a *post-hoc influence diagnostic*, not a new inferential significance test or an unbiased correction for selection.

## Focused fixed-panel contrast (descriptive only)

Sub-Saharan Africa: 4 matched, 33 unmatched (4/37=10.81%); all other regions: 69 matched, 51 unmatched (69/120=57.50%). Descriptive coverage risk ratio = (4/37)/(69/120) = **0.1880**; descriptive coverage odds ratio = (4×51)/(33×69) = **0.08959**. A two-sided Fisher exact calculation on the fixed 2×2 table gives **p≈3.66×10⁻⁷**, **conditional on a hypothetical exchangeability/null model**. Because these economies are **not a random sample** and selection into matched ILOSTAT data is not randomised, this p-value **must not** be represented as population-level evidence or a causal missingness mechanism. A conventional Wald odds-ratio interval would additionally require a justified sampling model; none is asserted here.

## Reproducible arithmetic (standard-library Python)

```python
from math import sqrt
rows = {
    "ECA": (32,46), "LAC": (16,28), "EAP": (12,22),
    "MENA_AP": (6,17), "SA": (2,6), "SSA": (4,37), "NA": (1,1)
}
def summary(omit=None):
    selected=[(m,n) for k,(m,n) in rows.items() if k != omit]
    M=sum(m for m,n in selected); N=sum(n for m,n in selected)
    x2=0.0
    for m,n in selected:
        for observed,expected in ((m,n*M/N),(n-m,n*(N-M)/N)):
            x2+=(observed-expected)**2/expected
    return N,M,round(x2,4),round(sqrt(x2/N),4)
for key in [None,*rows]: print(key,summary(key))
```

## Consequence for AE-2026-001

Add an explicit sentence to Results 3.18 and Limitations that regional availability imbalance is strongly influenced by the under-covered Sub-Saharan Africa stratum; the observed 73-economy matched subset cannot establish global representativeness or a causal source-vintage mechanism. This sensitivity analysis does **not** establish novelty over countryatlas, provide 2024/2025 archived ILOSTAT series, validate an independent employment denominator for the historical WDI vintages, or authorise journal submission. **MAJOR REVISION / NO SUBMISSION.**
