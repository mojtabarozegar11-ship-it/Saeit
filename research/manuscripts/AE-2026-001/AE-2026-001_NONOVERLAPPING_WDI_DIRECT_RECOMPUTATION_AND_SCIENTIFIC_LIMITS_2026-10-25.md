# AE-2026-001 — genuine WDI country data, non-overlapping intervals: independently calculated results

**Source:** committed official World Bank WDI `NV.AGR.EMPL.KD` country panel dated 2026-10-25, `AE-2026-001_OFFICIAL_WDI_OBSERVED_COUNTRY_PANEL_2026-10-25.csv`, 217 non-aggregate economy records. **Method:** independent direct CSV recomputation in the research run, not simulated observations; full replay code `analysis/wdi_nonoverlapping_period_growth_from_archived_official_panel.py`; separate CI workflow `.github/workflows/ae-2026-001-independent-nonoverlapping-intervals.yml` **completed successfully** in [run 40227453001](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40227453001), with independently recomputed 153-economy values verified in the job log and preserved in [artifact 12611581604](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40227453001/artifacts/12611581604). This is computational reproducibility, not a proof of novel research. No statistical significance or novel causal inference claimed.

**Matched sample:** 153 economies with strictly positive values in all three years.

| Same 153 economies | Annualized log growth 2000–2019 | Annualized log growth 2019–2023 | Annualized log growth 2000–2023 |
|---|---:|---:|---:|
| Median | 0.023555752946417118 | 0.008904395335439335 | 0.022244837043986730 |
| Mean | 0.024020706240511433 | 0.005417354214909468 | 0.020785340670841517 |
| Positive | 128 | 90 | 132 |
| Negative | 25 | 63 | 21 |

**Paired within-economy late-minus-early rate:** mean **−0.018603352025601948**, median **−0.019258316149146346**, negative in **109** economies and positive in **44** (none exactly zero). The median of paired differences is **not** the difference of period medians. The log-rate identity `19*g(2000,2019)+4*g(2019,2023)=23*g(2000,2023)` holds for each positive observation.

**Regional descriptive coverage (all three dates):** East Asia & Pacific 22, Europe & Central Asia 45, Latin America & Caribbean 28, Middle East/North Africa/Afghanistan/Pakistan 15, North America 1, South Asia 6, Sub-Saharan Africa 36; total **153**. In the last interval, the region-specific median for Sub-Saharan Africa is **−0.003476**, but it describes **36 selected economies**, not the whole region. The North America subset of **one** cannot support regional inference.

**Scientific interpretation:** A true disjoint-period comparison resolves the previous *overlapping-window wording* error and demonstrates descriptive differences in the same economies. It does **not** establish a post-2019 causal shock, convergence, or a new economic law. WDI agriculture includes forestry and fishing and uses modeled employment denominators. Cross-vintage data revisions, composition and source methods must be examined before a publication-grade contribution can be asserted. **No journal submission or author approval** is implied.
