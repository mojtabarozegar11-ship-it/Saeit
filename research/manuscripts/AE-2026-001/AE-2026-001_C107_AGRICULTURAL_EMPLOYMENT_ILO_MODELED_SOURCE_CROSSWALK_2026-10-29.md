# AE-2026-001 — C107 WDI/ILOSTAT agriculture-employment construct crosswalk
**Owner:** R-01 | **Date:** 2026-10-29 | **Artifact:** source-grounded measurement decision sheet, READY_FOR_REVIEW | **Empirical panel:** BLOCKED (no downloaded checksummed observations)

## Primary-source correction
The official World Bank indicator [SL.AGR.EMPL.ZS](https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS) is **Employment in agriculture (% of total employment), modeled ILO estimate**. Its numerator concerns *employment in the agricultural sector*, including agriculture, forestry and fishing (ISIC Rev. 4 section A); its denominator is **total employment**, not the working-age population, number of farms, rural residents or total agricultural workers. A value of 20 means 20 percent of total employed persons, **not** 20 percent of national population or a count of 20 agricultural jobs. The World Bank lists ILO Modelled Estimates (ILOEST) as its upstream source and indicates that the displayed series source was accessed **17 January 2026**; this metadata access date is not a guarantee that an October 2026 WDI archive or an independent ILOSTAT download is identical. [World Bank current indicator page](https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS); [World Bank WDI metadata](https://databank.worldbank.org/metadataglossary/World-Development-Indicators/series/page/9).

## Admissible vs inadmissible AE claims
| Field | Admissible interpretation | Prohibited shortcut |
|---|---|---|
| SL.AGR.EMPL.ZS | modeled agricultural employment share, % of total employment | headcount, agricultural output, measured productivity |
| SL.AGR.EMPL.FE.ZS | modeled agricultural share of **female employment** | female share of all agricultural workers |
| SL.AGR.EMPL.MA.ZS | modeled agricultural share of **male employment** | male share of all agricultural workers |
| WDI vs ILOSTAT | potentially shared upstream ILOEST series; verify release and filters | treat matching numbers as two independent datasets or replications |
| Historical WDI archive | edition-specific observation + definition + SHA256 | replace an earlier archive with today's API response |
| 2026 metadata access | source retrieval provenance | claim latest year observed is 2026 or a 2026 policy effect |

## Operational acceptance contract (without synthetic observations)
A valid input row must preserve `source_system`, `dataset_family`, `release_date`, `retrieved_utc`, `archive_url`, `raw_sha256`, `country_iso3`, `indicator_code`, `year`, `value`, `unit`, `isic_revision`, `sex`, `modelled_vs_survey`, `definition_snapshot_sha256`, `quality_flag`. Missing values remain NA, not 0. For the female and male percentages, do **not** compute a national total by unweighted averaging; weights would require independently verified female/male employment counts for the same year and vintage. Country-year matching alone is insufficient to combine modelled ILOEST with survey ILOSTAT estimates.

**Acceptance:** historical archive bytes and their hashes match; official metadata captured at each vintage; consistent country/ISIC/sex/model status; independent check of revisions. **Stop states:** BLOCKED_RAW_ARCHIVE, BLOCKED_HISTORICAL_METADATA, BLOCKED_ILOSTAT_RELEASE, BLOCKED_SEX_DENOMINATOR. No regression, causal result, sample size or publication is claimed.

**Next atomic action:** acquire a dated official WDI archive and a dated ILOSTAT release, compute SHA-256 from downloaded bytes, and join only definition-compatible records. Existing [C104 vintage gate](AE-2026-001_C104_WDI_HISTORICAL_DEFINITION_VINTAGE_GATE_2026-10-29.md) remains controlling.
