# MR-C144 — independent denominator and counting reconciliation protocol
Version: 1.0 | 2026-11-07 | status: research QA, NOT scientific acceptance or journal submission

## Scope and evidence boundaries
This is a **public-safe original methodological protocol**, not a reproduction of copyrighted publisher tables and not a declaration that any named source is erroneous. The manuscript's existing unresolved references are labelled F7, Car, and Cvejić. No underlying publisher dataset was fetched or independently authenticated in this deliverable. Do not alter manuscript claims on the strength of this note alone.

## Counting discrepancy: formal test
Reported category counts in the prior private audit were six values summing to 74; a separate reported respondent count was 72. The arithmetic discrepancy is **74 − 72 = 2**. It is NOT necessarily a factual error: counts may reflect multi-response categories, repeated observations, overlapping subgroups, missing exclusions, or a transcription mismatch. A percentage such as 53/72 × 100 = 73.611111…% rounds to 73.61%, but only if the numerator and denominator refer to the same unit, time, population, and inclusion rule.

### Acceptance conditions
1. Retrieve primary publisher PDF, DOI, edition/date, table number and caption; record its exact file hash and rights to reuse excerpts.
2. Extract each category's exact definition, count, unit, overlap rule, missing-data rule, and stated total, with page/table pointers.
3. Identify whether each respondent may contribute to multiple categories; if yes, do NOT compare the category sum with unique respondent count as an equality requirement.
4. Recompute both unique respondent count and response count independently from source-licensed aggregate data; explicitly distinguish them.
5. If categories are mutually exclusive and exhaustive, require sum(counts) = unique N; otherwise document the permitted discrepancy.
6. Resolve the manuscript statement only with primary-source evidence and author confirmation. Until then, keep the reference as **unverified / HOLD**.

## F7 dimensional arithmetic gate
For any claimed water productivity, require a named numerator (mass, dry/fresh basis, area and harvest interval) and denominator (irrigation only, evapotranspiration, or total applied water). Verify unit transformations before computing ratios. Report displayed-value precision and rounding interval; do not infer original measurement precision from rounded table cells. Different denominator definitions must never be compared as though interchangeable.

## Cvejić denominator gate
Identify exactly what the cited percentage divides: individuals, holdings, responses, plots, hectares, events, or another observational unit. Record the publisher's population, survey wave, filtering, and missing-value treatment. Recompute only from commensurate counts; never silently substitute a manuscript sample denominator.

## Machine-checkable release criteria
- Source identity: publisher URL/DOI + page/table + retrieval date + file SHA-256.
- Numeric reproduction: formula, input cells, unit, rounding policy, computed result, discrepancy classification.
- Editorial control: approved replacement text with tracked provenance, independent reviewer evidence, author approval where needed.
- Release: all three source gates PASS, declarations truthful and author-confirmed, rights checked. Otherwise manuscript submission remains HOLD.

## Status
Source verification: NOT DONE. Author approval: NOT OBTAINED. Accepted WBS weight: 0. Journal submission: 0. Publication: 0. Verified revenue: none. This note is a usable internal review protocol, not an accepted research product.
