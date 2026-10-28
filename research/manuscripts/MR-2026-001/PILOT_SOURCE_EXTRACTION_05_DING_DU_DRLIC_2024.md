# MR-2026-001 — Targeted source audit 05: Ding & Du, DRLIC
**Status:** Primary-source calibration, NOT systematically included. Checked 2026-10-24. Source: Ding X, Du W. *Optimizing Irrigation Efficiency using Deep Reinforcement Learning in the Field*. ACM Transactions on Sensor Networks 20(4), article 99 (2024). DOI [10.1145/3662182](https://doi.org/10.1145/3662182). Public author preprint [arXiv:2304.01435v1](https://arxiv.org/html/2304.01435). Journal DOI/metadata independently corroborated by [DBLP](https://dblp.org/rec/journals/tosn/DingD24.html). The accessible line-level extraction below is from the **2023 preprint**; version-of-record wording/figures were not compared and must be checked before final inclusion.

## Design and provenance (preprint §6.1.3, §6.2, §6.3)
- Six almond trees, **two per arm**: DRLIC reinforcement-learning controller, evapotranspiration-based controller, and soil-sensor threshold controller. In-field deployment: **15 days**, not a growing season; no reported farmer-facing advisory workflow or voluntary adoption.
- Water use: field controller logs sprinkler actuation duration under a nominal regulated 30 psi and known sprinkler flow rate (§6.2.2). This is **field-operationally estimated volume**, NOT independently verified water-meter readings. Record as **M-proxy** (operational measurement/inference) with calibration uncertainty; never claim metered farm consumption.
- Field comparisons (§6.2.2, Figure 12): authors report **9.52% lower water use vs ET control**, **3.79% vs sensor control**. Percentages are source-reported; raw daily values/independent re-estimation from underlying time-series are not available in this audit.
- Plant response (§6.2.1, Figure 11): soil-water threshold adherence used as proxy for health. No harvest yield, crop quality or long-term tree-health measurement established. Sensor arm reportedly below the moisture threshold during four days; duration and per-tree effects require original figures.
- Separate **whole-season simulations** (§6.3.2, Figure 15) report 10.21% and 3.93% reductions vs ET and sensor respectively. These are **P**, not 15-day field effects.
- Economic return (§6.8): extrapolates field percentage, assumed water cost, tree density and device cost; projected savings/payback are **P**, not observed farm financial outcomes.

## Decision-support construct
DRLIC makes algorithmic control decisions and directly actuates sprinklers; the decision actor is the **automated controller**, not a farmer following advice. Classify `DSS_ACTIONABLE` / automation actor only if the final protocol includes autonomous DSS; **exclude from farmer-adoption stratum** unless independently documented human use is found. Do not infer farmer uptake from a physical field installation.

## Evidence gaps and bias
Tiny, site-specific and short-duration comparison; two trees per arm; no stated farm-level randomization; spatial position may confound treatment (upper/middle/lower trees); source does not establish crop yield or sustained water benefit; controller water-use measurement depends on flow/pressure assumptions; no independent economic records. This is not a formal risk-of-bias judgement by independent human assessors.

**Provisional charting:** measured field operation M-proxy; field soil moisture M; simulated season P; modeled economics P; farmer adoption U. **Eligibility: UNDECIDED.**
