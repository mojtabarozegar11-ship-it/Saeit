# MR-2026-001 — Source audit 09: Nxumalo et al., Vhembe EO–AI irrigation model
Checked: 2026-10-24. **Published 6 January 2026** (journal volume labelled 2025).
Version of record: https://www.frontiersin.org/journals/agronomy/articles/10.3389/fagro.2025.1697188/full
DOI: 10.3389/fagro.2025.1697188
Authors on publisher: Gift Siphiwe Nxumalo, Tondani Sanah Ramabulana, Zibuyile Dlamini, Angura Louis, Attila Nagy.

## Source-location extraction
- Abstract and §2.2: maize crop evapotranspiration mapping in Vhembe District, South Africa; Sentinel-2/MODIS, OPTRAM, station weather data and ARC soil-moisture probes. 2020–2024 data period.
- §2.2.2 Steps 3a and 4, Table 2: **prediction target** is FAO-56 Penman–Monteith-derived ETc, not independent lysimeter-measured ETc or directly metered irrigation use. Approximately 10,000 sampled points per year; stated 70/30 train/test split; authors report no spatial or temporal overlap, but split code was not examined.
- §3 and Discussion: authors report RF and KNN R²>0.99 and RMSE<0.06 mm/day against the specified calculated benchmark. These values do **not** independently prove actual irrigation water savings, farm profitability or farmer adoption.
- §2.2, §4 and Conclusion: framework yields proposed actionable water-deficit alerts, but the reviewed text does not demonstrate a farmer-level deployment, compliance log, measured post-alert water reduction, or multi-season adoption. Authors themselves call for expanded field validation and embedding in farmer-centric digital platforms.
- Soil-moisture probes contribute to model calibration/validation; this is **not** equivalent to observing irrigation decisions or harvest yield.

## Provenance and provisional eligibility
P = modeled ETc and advisory recommendation; M-input = soil moisture and weather station observations; O-DSS-use = not established; M-irrigation-volume = not established; S-adoption = not established. Classify as **model-development/contextual technical validation**, not a field-evaluated farmer-adoption outcome. No PRISMA inclusion decision.
The label 'operational prototype' should not be treated as proof of operational farm adoption. Strong model accuracy against an engineered target must not be described as measured farm water saving.

## QA gaps
Reproduce model target construction and split from accessible code/data before asserting spatial independence; verify external validation against independently measured ETc; determine whether any deployed advisory channel exists in supplement. No raw ML reanalysis or independent field verification was performed.
