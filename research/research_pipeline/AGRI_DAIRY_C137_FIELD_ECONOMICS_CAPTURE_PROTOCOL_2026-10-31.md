# R-01 C137 — Dairy production-economics field-data capture protocol
Date: 2026-10-31 | Rotation: future agricultural research | Stage: READY_FOR_REVIEW (data instrument, no collected observations)
Research question: Which measured farm-level management and input-cost differences are associated with net milk margin per cow-year, conditional on herd size, production stage, feed composition and season?

## Sampling and estimands
- Unit: farm × calendar month; cows in milk and all-cow denominators stored separately. Prospective longitudinal panel, **not** a randomized intervention or causal design.
- Primary endpoint: monthly contribution margin per kg saleable milk = (milk revenue + documented byproduct revenue − variable operating costs) / saleable milk kg. Report both per kg and per lactating cow-month; do not substitute one for the other.
- Secondary: feed conversion proxy kg saleable milk / kg dry-matter intake; annualized net margin only after 12 complete months or explicit incomplete-year sensitivity.
- Sampling frame, target region, consent, planned sample size, sampling weights and analysis plan must be approved **before** collecting personal or commercial data. No invented farms or observations.

## Machine-readable column contract
| Column | Type / unit | Validation |
|---|---|---|
| anonymized_farm_id | opaque string | Unique pseudonym; key stored separately in restricted system |
| month | YYYY-MM | Valid reporting month; one row per farm-month |
| region_code | controlled string | No precise farm address in public data |
| cows_total | integer heads | >= cows_lactating; > 0 |
| cows_lactating | integer heads | > 0 for per-lactating-cow analyses |
| saleable_milk_kg | decimal kg | >=0; milk sold, excludes discarded |
| discarded_milk_kg | decimal kg | >=0; recorded separately |
| dry_matter_feed_kg | decimal kg | >0 if feed-efficiency estimate used |
| feed_cost_local | decimal currency | >=0; same currency and nominal month |
| labor_cost_local | decimal currency | >=0; imputed family labor separately |
| veterinary_cost_local | decimal currency | >=0 |
| energy_water_cost_local | decimal currency | >=0 |
| other_variable_cost_local | decimal currency | >=0; define inclusions |
| milk_revenue_local | decimal currency | >=0; actual realized, not asking price |
| byproduct_revenue_local | decimal currency | >=0; avoid double count |
| fixed_cost_local | decimal currency | >=0; report separately from contribution margin |
| currency_code | ISO 4217 | No cross-currency pooling without dated FX/PPP rule |
| source_record_type | enum | invoice, meter, farm_log, interview |
| source_verified | boolean | independent receipt/meter check vs self-report |
| missingness_reason | enum | none, not_recorded, not_applicable, withheld |
| consent_research_use | boolean | must be true for inclusion; no public identities |

## Preanalysis quality gates
1. Range, month, herd consistency, duplicate farm-month, invoice/currency checks.
2. Missing data reported by variable and farm; do not silently fill absent costs with zero.
3. Distinguish accounting contribution margin from full economic profit (fixed capital, depreciation, land, family labor, opportunity cost).
4. Predeclare cluster-robust farm-level inference, season and region controls; do not imply causality from association.
5. Access restricted: no customer, employee or identifiable farm data in GitHub. Only blank template and methodology may be public.
6. Validate any animal welfare, biosafety and local legal constraints before fieldwork.

## Computation contract
variable_cost = feed + labor + veterinary + energy_water + other_variable
contribution_margin = milk_revenue + byproduct_revenue − variable_cost
margin_per_kg = contribution_margin / saleable_milk_kg (undefined if denominator 0)
feed_efficiency = saleable_milk_kg / dry_matter_feed_kg (undefined if denominator 0)
**Do not annualize a partial panel without explicitly labeled assumptions.**

**Next:** owner R to approve research protocol, secure ethically permitted real data and preregister the analysis plan. No fabricated WDI/ILOSTAT or farm observations; no recruitment authorized by this document.
