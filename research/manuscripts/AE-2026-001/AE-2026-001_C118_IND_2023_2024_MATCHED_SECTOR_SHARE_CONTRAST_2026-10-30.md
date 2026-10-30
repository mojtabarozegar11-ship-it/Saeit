# AE-2026-001 — India matched-year WDI descriptive sector-share contrast (C118; 2026-10-30)

**Stage:** READER-USABLE DERIVED ANALYSIS, not a finished empirical article. Reproduced from R-owned [C115 normalized WDI extract](AE-2026-001_C115_WDI_ACTUAL_IND_CAN_2023_2024_EXTRACT_2026-10-30.tsv), whose API source reports WDI source 2 lastupdated 2026-10-08. **Raw response bytes and SHA-256 were NOT captured**, so this is not a raw-archived dataset. Values are a current-vintage transcription, not an immutable historical vintage.

| Country | Year | Agricultural employment share of total employment (%) | Agriculture/forestry/fishing value added share of GDP (%) | Employment share minus GDP share (percentage points) |
|---|---:|---:|---:|---:|
| India | 2023 | 43.5135811245793 | 17.6565389328245 | 25.85704219 |
| India | 2024 | 42.3547738876441 | 17.5735799524173 | 24.78119394 |

The difference is an **arithmetic descriptive contrast between two percentages with different denominators**, not a measure of labor productivity, wages, farm profitability, employment growth, causation, statistical significance or physical output. The sector definitions, WDI vintages and modeled ILO employment estimates require reconciliation before cross-country interpretation. Canada 2023/24 value-added observations in the C115 capture are **null** and are deliberately excluded; no interpolation or fabricated values. The change in the gap between the two displayed years is -1.07584826 percentage points, descriptive only; no inference from two years.

## Exact inputs and reproducibility

- Employment: `SL.AGR.EMPL.ZS`, WDI/ILO modeled estimate, denominator total employment. https://api.worldbank.org/v2/country/IND/indicator/SL.AGR.EMPL.ZS?format=json&date=2023:2024
- Value added: `NV.AGR.TOTL.ZS`, WDI national accounts, denominator GDP. https://api.worldbank.org/v2/country/IND/indicator/NV.AGR.TOTL.ZS?format=json&date=2023:2024
- Calculation: `employment_share_percent - sector_value_added_share_percent`; arithmetic independently recomputed from C115 values on 2026-10-30.
- QA: no missing Indian cells in this two-year pair; no standard errors, raw-response hash or ILOSTAT independent source replication. **Do not use as a publication-ready statistical result.**

**Next:** capture source JSON response bytes outside the factory, hash with SHA-256, store privately with retrieval UTC time and upstream release metadata; then compare against the above normalized extract before advancing AE manuscript. No fabricated ILOSTAT data.
