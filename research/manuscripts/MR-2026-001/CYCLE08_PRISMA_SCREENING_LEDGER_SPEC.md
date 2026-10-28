# MR-2026-001 | Cycle 08 | PRISMA-ScR execution ledger schema and gate
Status 2026-10-25: PROSPECTIVE SPECIFICATION ONLY. No indexed search export, formal deduplication, human title/abstract screening, full-text eligibility decisions or PRISMA flow has occurred in this cycle. Do not use counts from Nsoh's *different review* as counts for MR-2026-001.
Standard: Tricco et al. 2018 PRISMA-ScR DOI 10.7326/M18-0850, https://www.prisma-statement.org/scoping

## Required raw-record table (one row per database record)
`record_id,source_database,platform,search_run_utc,query_version,raw_export_filename,raw_export_sha256,source_accession_id,doi_raw,doi_normalized,title,year,first_author,language,record_url`.
Keep exact raw records immutable and separately store derived dedup decisions.

## Required screening table (one row per independent decision)
`canonical_record_id,reviewer_id,reviewer_role,stage,decision,reason_code,decision_utc,protocol_version,notes`.
Stage in `title_abstract|full_text`; decision in `include|exclude|uncertain`. Reason taxonomy: `wrong_population|not_irrigation|not_DSS|no_farm_context|simulation_only|secondary_review|no_empirical_data|other`. Reviewer must be a real human; AI-generated labels can be proposals but cannot masquerade as independent human screening.

## Required extraction table (one row per study × farm/season × outcome)
`study_id,source_doi,source_page_table,design,site,crop,tool_recommendation,advice_delivered,decision_maker,implementation_measure,adoption_stage,denominator,followup_months,outcome,unit,comparator,measured_or_modelled,provenance_MOSPU,instrument,estimate,uncertainty,reviewer_id,verification_status`.
Preserve source-level traceability and avoid double-counting repeated harvests, fields and seasons.

## Gate and unresolved tasks
- Final PCC and eligible strata: author approval pending.
- Specialist review of search strings: pending.
- Two indexed-database exports and hashes: pending.
- Deduplication and dual human screening: pending.
- PRISMA-ScR checklist and actual flow: pending; counts UNKNOWN, not zero.
- Plagiarism/similarity software scan: NOT RUN; manual citation/originality checking only.
- This file creates an executable data dictionary, not screening evidence.
