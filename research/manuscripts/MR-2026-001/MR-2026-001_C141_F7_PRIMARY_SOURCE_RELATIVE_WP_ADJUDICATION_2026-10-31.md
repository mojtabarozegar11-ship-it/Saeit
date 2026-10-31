# MR-2026-001 — C141 F7 primary-source adjudication (fixed version)

**Status:** SOURCE-DERIVED ARITHMETIC VERIFIED; ORIGINAL ESTIMAND/RAW DATA BLOCKED. This is a public-source evidence note, not a new manuscript version, corrected source paper, independent peer review, or permission to submit.

**Primary published source:** Amini, Emami & Dehghanisanij (2025), *Scientific Reports* 15:42480, DOI [10.1038/s41598-025-26567-z](https://doi.org/10.1038/s41598-025-26567-z); full original article at [PMC12660781](https://pmc.ncbi.nlm.nih.gov/articles/PMC12660781/), Tables 4–5, Results and Data availability.

| Printed F7 input | DSS | Control |
|---|---:|---:|
| Apple yield, t/ha (Table 5) | 48.9 | 45.6 |
| Gross applied irrigation depth, mm (Table 4) | 1057.6 | 764.9 |

For *irrigation-input* water productivity, WP = 100 × yield(t/ha)/depth(mm), the conventional same-pair relative contrast is:

`100 × [(48.9 × 764.9)/(45.6 × 1057.6) − 1] = −22.4418867943%`.

Conditional nearest-0.1 rounding (each printed yield/depth independently within ±0.05) gives:

- Lower: `100 × [(48.85 × 764.85)/(45.65 × 1057.65) − 1] = −22.6147689739%`.
- Upper: `100 × [(48.95 × 764.95)/(45.55 × 1057.55) − 1] = −22.2686063583%`.

The original Table 5 shows **−3.22** under a percentage-labelled WP-change column. That value is outside the conditional rounding envelope, so **one-decimal rounding alone cannot explain it under the same-pair ratio formula**. This does *not* prove a typographical error: an unreported mean of plot-level changes, alternative weighting or another estimand remains possible. The original datasets are described as available from the corresponding author on reasonable request; no unrounded observations or authenticated erratum have been received. No confidence interval, treatment effect, water saving, adoption rate or statistical significance is reconstructed.

**Disposition in the complete private C141 author-reader:** the source −3.22 entry is excluded from exact-effect synthesis; the conditional calculation and its uncertainty are disclosed in §3.1.1. The full DOCX/PDF is owner-private; no manuscript text or private storage link is committed here. Qualified independent methods review and author approval remain required before submission.

**Next evidence action:** obtain original Table 5 WP-change formula, observation-level numerator/denominator/weights and any journal correction; then review this fixed C141 without inventing values.
