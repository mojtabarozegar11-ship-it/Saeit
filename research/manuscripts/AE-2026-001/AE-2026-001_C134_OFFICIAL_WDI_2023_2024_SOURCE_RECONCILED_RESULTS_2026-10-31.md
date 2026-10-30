# AE-2026-001 | C134 primary WDI source reconciliation | 2026-10-31

**State:** ORIGINAL-PROVIDER-API-VALUES VERIFIED for two India indicators (2023–2024), **NOT journal-ready**. Official API source lastupdated **2026-10-08**; original responses retrieved 2026-10-31 through browser extraction, not authenticated byte-identical HTTP download. Extracted JSON is stored in two linked source snapshot files. The modeled employment indicator originates in ILOEST, so independent ILOSTAT replication is **NOT** established.

| Year | Employment in agriculture (% of employment), SL.AGR.EMPL.ZS | Agriculture/forestry/fishing value added (% GDP), NV.AGR.TOTL.ZS | E−V (percentage points) | E/V (dimensionless) |
|---|---:|---:|---:|---:|
| 2023 | 43.51358112 | 17.65653893 | 25.85704219 | 2.46444568 |
| 2024 | 42.35477389 | 17.57357995 | 24.78119394 | 2.41013920 |
| 2024−2023 | -1.15880724 pp | -0.08295898 pp | -1.07584826 pp | -0.05430648 |

**Interpretation:** E/V is a ratio of two percentages with different denominators, **not labor productivity, per-worker value added, a causal effect, or a wage measure**. These descriptive changes are provider-vintage-specific and can be revised. No uncertainty intervals or causal inference are inferred.

**Sources:** [World Bank ILO-modeled agricultural employment](https://api.worldbank.org/v2/country/IND/indicator/SL.AGR.EMPL.ZS?format=json&date=2023%3A2024); [World Bank agricultural value-added share](https://api.worldbank.org/v2/country/IND/indicator/NV.AGR.TOTL.ZS?format=json&date=2023%3A2024). Provider sourceid=2, lastupdated=2026-10-08, country IND, years 2023/2024, two records per series. Browser-extracted JSON is preserved at research/manuscripts/AE-2026-001/source_snapshots/AE_C134_WDI_IND_SL_AGR_EMPL_ZS_2023_2024_EXTRACTED_2026-10-31.json and research/manuscripts/AE-2026-001/source_snapshots/AE_C134_WDI_IND_NV_AGR_TOTL_ZS_2023_2024_EXTRACTED_2026-10-31.json.

**Remaining gates:** retrieve independently byte-preserved provider responses with SHA-256 and retrieval headers; reconcile ILOEST revision/vintage with ILOSTAT without asserting independent replication; verify national accounts definition and year alignment; independent scientific review and author approval. No factory or master-agent interaction.
