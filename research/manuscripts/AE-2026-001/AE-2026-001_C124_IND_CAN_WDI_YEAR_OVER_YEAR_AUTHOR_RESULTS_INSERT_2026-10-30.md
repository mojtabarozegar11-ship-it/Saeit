# AE-2026-001 | C124 journal-methods-ready WDI descriptive results insert

**Source:** [R-owned C115 normalized WDI extraction](AE-2026-001_C115_WDI_ACTUAL_IND_CAN_2023_2024_EXTRACT_2026-10-30.tsv), source metadata WDI source 2, lastupdated 2026-10-08; downloaded API response bytes and SHA-256 were not retained. This is a derived *current-vintage transcription*, not a raw reproducible dataset or independent ILOSTAT validation.

## Results paragraph (for author review, not a submitted article)
India's agriculture/forestry/fishing employment share (World Bank indicator `SL.AGR.EMPL.ZS`, modeled ILO estimate) moved from **43.51358112% (2023)** to **42.35477389% (2024)**, a change of **-1.15880724 percentage points**. Agriculture/forestry/fishing value added as a share of GDP (`NV.AGR.TOTL.ZS`) moved from **17.65653893%** to **17.57357995%**, a change of **-0.08295898 percentage points**. The arithmetic gap between the two differently denominated percentages moved from **25.85704219** to **24.78119394 percentage points** (change **-1.07584826**). This is descriptive; it is **not** labor productivity, causal evidence, an estimate of agricultural wages, or an inferential time-series result. For Canada, the employment share changed from **1.27154304%** to **1.12952160%** (**-0.14202143 percentage points**), but the paired GDP-share values were null in the captured source and no Canadian gap was calculated.

## Reproduction and acceptance
- Formula: `delta_pp = percentage_2024 - percentage_2023`; `gap_pp = employment_share_percent - value_added_share_percent`.
- Source: https://api.worldbank.org/v2/country/IND/indicator/SL.AGR.EMPL.ZS?format=json&date=2023:2024 and https://api.worldbank.org/v2/country/IND/indicator/NV.AGR.TOTL.ZS?format=json&date=2023:2024 .
- Source of Canadian employment: https://api.worldbank.org/v2/country/CAN/indicator/SL.AGR.EMPL.ZS?format=json&date=2023:2024 .
- Data QC from fetched C115: 8 normalized records, 2 missing values, all four India matched-year values present. No extrapolation or missing-value imputation.
- **BLOCKED for empirical submission** until source JSON bytes are archived and hashed, indicator definitions/ILOSTAT releases independently reconciled, a defensible research design is specified, and the human author approves.
