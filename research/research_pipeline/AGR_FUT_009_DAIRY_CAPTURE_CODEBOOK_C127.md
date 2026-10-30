# AGR-FUT-009 | Dairy pen-day primary-data capture instrument — C127
Status: **READY_FOR_DATA_COLLECTION**, not a completed experiment or article. Prepared 2026-10-30 by R-01.

## Operational instrument
Use [blank CSV](AGR_FUT_009_DAIRY_PEN_DAY_BLANK_C127.csv) for one record per `study_id × herd_code × pen_code × observation_date`. Do not publish animal/farm identities in the public repository; pseudonymous codes only. Store completed records privately with access control and integrity hash.

| Column | Required unit / format | Measurement rule |
|---|---|---|
| study_id, herd_code, pen_code | pseudonymous text | Stable identifiers; avoid names and geolocation |
| observation_date | ISO YYYY-MM-DD | Local farm date; preserve time zone separately in field protocol |
| cow_days | cow-days, >0 | Sum of animals present over observation intervals; not necessarily integer |
| feed_offered_asfed_kg | kg per pen-day | Calibrated scale; record feed offered, not predicted intake |
| feed_refused_asfed_kg | kg per pen-day | Same pen-day boundary; separately weighed refusals |
| offered_dm_fraction | 0–1 | Laboratory dry matter fraction of offered ration; timestamp and method retained separately |
| refused_dm_fraction | 0–1 | Laboratory dry matter fraction of refusals; not assumed equal to offered ration |
| feed_intake_dm_kg | kg DM per pen-day | Measured or derived mass balance; blank if unverified; never silently impute |
| milk_weight_kg | kg per pen-day | Calibrated aggregate milk measurement, not energy-corrected milk |
| quality_flag | controlled text | `VALID`, `REVIEW`, `EXCLUDE`; document reasons privately |

## Calculation and quality gate
DMI (kg DM/pen-day) = offered as-fed kg × offered DM fraction − refused as-fed kg × refused DM fraction. DMI per cow-day = DMI / cow-days only for records with nonzero denominator and defensible pen-day attribution. **Milk weight is not ECM** and cannot be compared as energy-corrected yield without verified fat/protein composition and an approved equation.

The existing [offline validator](../research_pipeline/AGR_FUT_009_DAIRY_PEN_DAY_QC_C121.py) checks identity, date, finite numeric fields, fractions, nonnegative measurements, dry-matter balance and duplicate pen-days. `PASS` verifies formatting and mass balance only, not truth of scale calibration, animal welfare approval, independent experimental replication or causal attribution. If the sampling design, treatment assignment, contemporaneous control and ethics permissions are absent, do not report a treatment effect.

## Collection acceptance
- Each farm supplies a private study protocol, calibration log, dry-matter assay method, feed-batch IDs and missingness codes.
- Records are entered prospectively and reconciled against the original milk/feed logs before analysis.
- The author approves design and scientific interpretation before a manuscript is drafted.
- No animal-level personal or customer information belongs in GitHub.

**Next:** collect genuine authorized records and run the offline validator on a private copy; do not generate synthetic observations as if measured.
