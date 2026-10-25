# MR-2026-001 — Reproducible search execution plan (not yet run)

**Prepared:** 2026-10-24  
**Status:** Methods development only. No bibliographic database search/export, registration, deduplication, eligibility screening, PRISMA flow or synthesis is represented as completed here.  
**Protocol relationship:** This is a prospective working appendix to `PROTOCOL.md`, subject to author and information-specialist review **before** execution and protocol freeze.

## 1. Narrower question to test

In real, farmer-facing deployments of irrigation decision-support systems (DSS) for crop production, **how are recommendations actually used, and how reliably are water, yield, energy and economic outcomes measured rather than predicted, simulated, or self-reported?**

This is a candidate question, **not** a demonstrated novel contribution. In particular, a farmer using advice for one monitored season is not evidence of sustained adoption. Do not interpret absence of follow-up as evidence that adoption failed.

### Population–Concept–Context (PCC)

- **Population:** farmers, growers, irrigation managers, and advisers serving irrigated crop farms.
- **Concept:** computerized/analytical DSS issuing actionable irrigation timing, depth, allocation or related crop-water decisions; distinguish the *tool*, its *recommendations*, and *farmer adherence/learning*.
- **Context:** on-farm use, farmer-facing pilots, and empirical field evaluations internationally; record physical and institutional water constraints, without requiring the exact phrase `water scarcity` in bibliographic queries.

## 2. Preliminary eligibility rules for pilot testing (not frozen)

**Potential inclusion:** primary empirical research, any language, directly concerning irrigation DSS on crop farms, and reporting one or more of: (a) measured field irrigation/yield/energy/economic outcome, (b) observation of DSS-guided decisions or uptake, (c) farmer-facing pilot validation with a documented real-world comparator. Keep nonrandomized designs but code limitations.

**Potential exclusion:** purely simulated or laboratory-only optimization with no farm implementation or measured field validation; weather/hydrology predictions with no irrigation decision; generic sensors with no decision-support component; agricultural technology adoption unrelated to an irrigation DSS; reviews (use for overlap and citation chasing, not primary-study synthesis); commentary/protocol-only reports.

**Borderline:** field-measured algorithm validation without farmer interaction belongs in a separately tagged validation-only stratum if eligible after piloting; it is *not* evidence of adoption. Do not require a positive result. Record null and adverse field outcomes.

**Dates:** No date restriction has yet been fixed. Test a no-year-limit search first and document volume and relevance of older results before justifying any modern-era cutoff. Exclude no language by default; log translation feasibility and limitations.

## 3. Search strings to review and adapt to exact database interfaces

### Scopus — primary-study candidate string (draft; NOT executed)

```text
TITLE-ABS-KEY(
  irrigat*
  AND ("decision support" OR "decision-support" OR "irrigation schedul*" OR
       "irrigation advisor*" OR "irrigation advisory" OR "smart irrigation")
  AND (farm* OR farmer* OR grower* OR field* OR plot* OR "on-farm")
  AND (validat* OR evaluat* OR trial* OR implement* OR deploy* OR
       adopt* OR "water use" OR yield* OR participat*)
)
```

### Web of Science Core Collection — primary-study candidate string (draft; NOT executed)

```text
TS=(
  irrigat*
  AND ("decision support" OR "decision-support" OR "irrigation schedul*" OR
       "irrigation advisor*" OR "irrigation advisory" OR "smart irrigation")
  AND (farm* OR farmer* OR grower* OR field* OR plot* OR "on-farm")
  AND (validat* OR evaluat* OR trial* OR implement* OR deploy* OR
       adopt* OR "water use" OR yield* OR participat*)
)
```

### Targeted overlapping-review sweep (apply each platform's exact syntax)

```text
irrigat* AND ("decision support" OR "decision-support" OR "irrigation scheduling" OR
"water productivity") AND (review OR "scoping review" OR "systematic review" OR survey)
```

**Execution rule:** Select at least two accessible, appropriate bibliographic databases (preferably Scopus plus Web of Science or CAB Abstracts; AGRICOLA is another candidate). Record license and interface. These strings are examples for the named interfaces, not claims of searches. A DOI lookup, publisher-page discovery, Google search, or a small curated seed list is **not** a substitute for the database search. Do not silently switch platforms and claim equivalent coverage.

## 4. Sensitivity and precision pilot (before protocol freeze)

1. Test whether the strategy retrieves known seed papers: Amini et al. (2025), DOI `10.1038/s41598-025-26567-z`; Conde et al. (2024), DOI `10.1016/j.compag.2024.108640`; and a relevant cotton DSS paper DOI `10.1016/j.atech.2023.100270`. Check actual bibliographic indexing and search results; absence can mean non-indexing, query mismatch, or a bad identifier.
2. Run the overlapping-review sweep separately against Ara et al. (2021), DOI `10.1016/j.agwat.2021.107161`, and Mabhaudhi et al. (2023), DOI `10.1016/j.agwat.2023.108590`. Do not require review papers to satisfy primary-study criteria.
3. Examine an actual random/purposive pilot set of titles and abstracts, log false exclusions, refine terms (including `irrigation management`, `advisory service`, decision-making spellings). Preserve both original and revised strings with timestamps.
4. After review-team agreement, freeze eligibility, platforms, full queries, limits and amendment rules. If protocol is registered, cite the actual registration ID; otherwise mark it unregistered.

## 5. Executable log format (fill using real exported results only)

| Field | Required evidence |
| --- | --- |
| Database and provider/platform | E.g., Scopus/Elsevier or WoS Core Collection/Clarivate |
| Searcher and UTC execution timestamp | Real user/tool identity and time |
| Coverage/access date | From actual interface |
| Exact executed query and all limits | Copy verbatim, not a paraphrase |
| Raw result count and full export | RIS/CSV/BibTeX with date and original filename; secure location |
| Export checksum | SHA-256; exact bytes |
| Search amendments | Version, reason, test evidence, approver |
| Citation chase | Seed DOI, direction, date, discovered record IDs |
| Deduplication | DOI normalized; exact title + year + first-author candidates, manual review for collisions; keep source record IDs |
| Screening | Human reviewer IDs, timestamps, title/abstract and full-text decisions, reason taxonomy, disagreements and resolution |
| Extraction | Study ID, source page/section/table, verbatim measurement definition, comparator, outcome direction, provenance, uncertainty |

**Record provenance classes:** M = directly measured on-farm; O = directly observed decision/adherence; S = farmer/stakeholder self-report; P = model-predicted/simulated; U = unclear or unverified. One paper may have multiple classes; never collapse a modeled recommendation into a measured saving.

**Adoption stages:** offered/trained; pilot-use observed; voluntary continued use; multi-season sustained use; wider independent uptake. Record duration and denominator. Missing data = not reported, not zero.

## 6. Review conduct and reporting gates

- PRISMA-ScR (Tricco et al., 2018): https://doi.org/10.7326/M18-0850
- JBI Scoping Review Network and latest methodology: https://jbi.global/scoping-review-network/resources and https://jbi.global/news/jbi-updates-its-scoping-review-methodology
- Independent dual human screening where available; otherwise disclose single-screening limitation. AI assistance can support organization, but must not be presented as a second human reviewer or independent human verification.
- Pre-specify descriptive evidence maps and transparent limitations; no meta-analysis or pooled savings rate is presumed.
- Do not report any search count, PRISMA flow count, included-study count or definitive novelty claim until the corresponding work really happened.

**Next gate:** a researcher with legitimate database access and the named author must review the question and protocol, execute and archive actual database exports, then undertake documented screening and source-checking.

---

## 2026-10-25 executed-index pilot: evidence-backed update (post-plan; not final search)

**Actual execution:** 2026-10-25T02:40:52.349Z. The prior blanket statement `no bibliographic index search executed` is now superseded **for these two precise preliminary queries only**. Do not erase the original prospective design or present this narrow pilot as comprehensive searching.

1. **Europe PMC (bibliographic indexed database; lite metadata):** exact query `TITLE_ABS:irrigat* AND TITLE_ABS:"decision support" AND TITLE_ABS:farmer*` returned **95/95** records. API: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=TITLE_ABS%3Airrigat%2A%20AND%20TITLE_ABS%3A%22decision%20support%22%20AND%20TITLE_ABS%3Afarmer%2A&format=json&pageSize=100&resultType=lite . Snapshot: [Europe PMC JSON](index_search_2026-10-25/EUROPE_PMC_EXECUTED_SEARCH_2026-10-25.json).
2. **OpenAlex (bibliographic discovery index; selected metadata):** exact title-and-abstract query `"irrigation decision support" AND farmer` returned **52/52** records. API: https://api.openalex.org/works?search.title_and_abstract=%22irrigation%20decision%20support%22%20AND%20farmer&per_page=100&select=id,doi,title,publication_year,type . Snapshot: [OpenAlex JSON](index_search_2026-10-25/OPENALEX_EXECUTED_SEARCH_2026-10-25.json).
3. **Cross-source preparation:** 147 returned index entries; seven candidate duplicate matches on normalized DOI or exact normalized title+year; **140 unique candidate citations** in [metadata-only screening queue](index_search_2026-10-25/SCREENING_QUEUE_METADATA_ONLY_2026-10-25.csv). This is a preliminary machine deduplication, requiring human collision checks and potentially merging translated titles, preprints and later publisher versions.
4. **Limitations:** neither search is an exhaustive union of irrigation DSS synonyms; Europe PMC's coverage is limited for agriculture outside biomedical-adjacent publications; OpenAlex is an aggregator (not equivalent to independent Scopus/WoS indexing); the archive has titles and identifiers but **not all abstracts/full texts**; neither includes human screening, full-text appraisal, PRISMA flow counts or final novelty confirmation. API responses were captured via web-extraction service and reserialized into UTF-8 JSON. These preserved normalized records are **not guaranteed byte-identical raw HTTP responses**. GitHub blob hashes evidence the stored exports, not the original HTTP body.
5. **Next scientifically necessary execution:** expand synonyms to cover farmer-facing irrigation advisory, on-farm scheduling and adoption; validate seed-paper recall; add independent agricultural coverage using AGRIS/AGRICOLA or licensed CAB/Scopus/WoS when available; retrieve missing abstracts/full texts; freeze query versions after expert review; conduct genuine human eligibility screening and resolve DOI/title collisions; retain source IDs and PRISMA-ScR audit trail. The approved scope decision is separately documented in `AUTHOR_APPROVED_SCOPE_DECISION_2026-10-25.md`.

**Submission remains NOT SUBMITTED**. Existence of an index-export queue does not constitute a complete review.
