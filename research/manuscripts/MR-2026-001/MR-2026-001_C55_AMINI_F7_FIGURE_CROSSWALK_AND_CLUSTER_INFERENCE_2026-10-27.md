# MR-2026-001 C55 — Amini (2025): F7 is a farm, not Figure 7; field-pair and inference audit

**Date:** 2026-10-27. **Status:** internal AI critical source audit; not a new field result, human review, verified randomization, or final author approval.

## Primary publisher evidence
Amini, Emami & Dehghanisanij (2025), *Scientific Reports* 15, 42480, DOI [10.1038/s41598-025-26567-z](https://doi.org/10.1038/s41598-025-26567-z). Original full-text sections **Characteristics of selected farms**, **Irrigation management**, **Water productivity and crop yield**, **Participatory evaluation**:
https://www.nature.com/articles/s41598-025-26567-z

### Figure-to-farm identity — an easily confused but consequential distinction
- **Figure 7 depicts farm F3**, not farm F7 (the publisher caption explicitly says "farm 3"). The publisher **Figure 12 depicts farm F7**.
- The original Results explicitly say **F7 and F4 received greater irrigation depth in treatment than control** because long water-advance times constrained surface/basin irrigation; F7 treatment minus control is reported as **+292.7 mm**.
- The publisher's Water Productivity section reports an **F7 decrease of 1.3 kg/m³**; a subsequent paragraph says **1.4 kg/m³ decrease**; the conclusion says **0.1 kg/m³ decrease**. These are incompatible statements for the same F7 comparison without a documented alternative denominator, rounding or different outcome definition. The previously source-audited Table 4 values 4.6 versus 6.0 kg/m³ imply **−1.4 kg/m³**. **Do not choose a definitive effect from conflicting prose without checking the publisher table and source corrections.**
- The F7 **+292.7 mm** is an irrigation-depth difference, not a farmer-adherence percentage, and it cannot be replaced by the F3 plot of Figure 7.

### Study design and statistical inference
- The publisher says **80 farms/orchards were selected**, of which **eight** were monitored, **two per village** across four villages. Each monitored farm was split into a customary-management control section and DSS-managed treatment section.
- This is **eight within-farm comparisons**, not 80 independent experimental treatment replications. The text does not establish randomized allocation of sections. Farm sections share weather, crop and operator and are not independent units for a naive unpaired test.
- The authors report a paired t-test (p < 0.05) and variability estimates, but the accessible Results do not specify enough detail here to independently reproduce the test, verify the precise pairing unit or account for village clustering and heterogeneous crops. **No new p-value or effect estimate is inferred here.**
- The publisher describes workshops and participatory feedback involving additional farmers. Workshop attendance is **not** the denominator of independent experimental farm-pair outcomes, and workshop approval is not post-trial independently logged adherence.

## Consequence for MR manuscript
Use Amini as an example of *measured within-farm water/yield contrasts and participatory feedback*, not randomized proof of adoption or validated G/D/R/A event-chain adherence. Separate: (i) field F7 from Figure 7, (ii) eight monitored pairs from 80 candidate farms and workshop participants, (iii) water-depth contrasts from water-productivity contrasts, and (iv) field measurements from independent long-term voluntary adoption. Retain the unresolved WP numerical conflict prominently.

**Release gate:** major revision / no submission. The original figure caption disambiguation is verified from publisher full text; the conflicting F7 WP values remain unresolved. No new human author approval, data, trial, DOI, or manuscript submission is claimed.
