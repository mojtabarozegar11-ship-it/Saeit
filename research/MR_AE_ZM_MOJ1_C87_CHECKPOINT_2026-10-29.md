# R-01 | C87 checkpoint | 2026-10-29 (Asia/Tehran)

**run_id:** R-01-C87-20261029T0210+0330-R10 | **branch:** `research/mr-2026-001-novelty-audit` | **WIP=2:** (1) MR clean reviewer manuscript + source evidence ledger; (2) bilingual CV verification (no new credential proof). **Previous checkpoint:** [C86](../MR_AE_ZM_MOJ1_C86_CHECKPOINT_2026-10-29.md). No claim of author-approved or journal-submitted paper.

## Actual new substantive outputs (3; tests, commits and reports excluded)

1. **C87 clean scientific manuscript**, derived without altering C86 source-rich original. The 60,285-character working draft with appended Car/Amini/Cvejić adjudication is now a **45,148-character reader-facing manuscript** preserving the complete eight-case main argument, methods, source warnings and 17 cited works, while moving historical internal audit details out of the manuscript body and linking back to preserved C86/C78 source dossiers. The primary Car 46/73/80 figures remain quarantined; the 45/72 engagement and 53/72 reported consideration remain distinguished from event adherence. [Read C87](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C87_CLEAN_AUTHOR_REVIEW_MANUSCRIPT_2026-10-29.md). Git blob SHA-1: `4bc3f22d1a8f20177a80cd49246486153964fdf7`. **READY_FOR_REVIEW**, not final approval.
2. **C87 machine-readable eight-case source/claim ledger**, 8 records and 11 columns: DOI of cited source, observational unit, admissible claim, source type and locator, denominator status, forbidden inference, missing evidence and dated verification provenance. Car UNE abstract independently rechecked 2026-10-29; seven other cases explicitly marked as C86 carryover **not rechecked**, preventing invented current-source verification. No original participant data, new DOI or DEG generated. [Read TSV](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/MR-2026-001/MR-2026-001_C87_EIGHT_CASE_CLAIM_LEDGER_2026-10-29.tsv). Git blob SHA-1: `84dc471e6a47e9480a24579a341d456101e80e0e`. **READY_FOR_REVIEW**.
3. **Publisher-verified core bibliography correction:** completed author lists, full article titles and volume/page or article identifiers for all **eight included studies** using publisher pages and UNE institutional record. Updated C87 manuscript and eight ledger provenance fields; seven prior-source interpretations are explicitly not represented as newly verified full-methods. The remaining nine contextual references are still unverified in full. Commit `dbcab75340f8748f3156e37088c4eb6a98301f03` (bibliography) and `7a870321e4b963b3cfd59dfc1067749d3f437430` (ledger). **READY_FOR_REVIEW**; no new empirical result.

**Before/after evidence:** C86 source-rich original blob `ecc438dc46c33dbffa972f8b2ee33bbf01456f74` remains unchanged. New C87 clean manuscript and TSV are separate new paths. Commits `846eb637118fdbf8197ab06056995439cc940dc5` and `14282979bf24af76a2948d9a9c3ac668080ea398`; commit creation alone is not counted as implementation.

**Reproducible checks, exact branch read-back:** 9/9 initial structure checks passed; updated file read-back also confirmed 8/8 complete core source-title/author entries, 8/8 dated metadata flags, eight TSV rows with 11 columns and the Darouich 2020/2022 year-conflict flag. Initial checks: 8 case subsections, historical source appendix removed from reader copy, 17 source references, exact-version gate, 8 ledger rows, 11 columns per row, 7 carryover-source flags at initial creation (subsequently replaced with precise metadata-only verification labels), 8 distinct cited-source DOIs, and preserved Car/Amini/Cvejić source warnings. These are structural checks, not peer review, full-source validation or empirical data verification.

**Fresh source check:** [UNE institutional record of Car 2012](https://researchers.une.edu.au/en/publications/using-a-mobile-phone-short-messaging-service-sms-for-irrigation-s-5/) confirms the 45/13/14 categories and the source-reported 80% usefulness assertion. The unresolved 17/14 and 74/72 conflicts are not corrected by that abstract. The source is not publisher-authenticated Table 5/6. No full publisher article bytes obtained.

## X/25 — MR and AE
| # | Independent target | This run |
|---:|---|---|
| 1 | C87 clean full manuscript, audit appendix separated | موفق؛ READY_FOR_REVIEW |
| 2 | C87 eight-case machine-readable source-to-claim ledger | موفق؛ READY_FOR_REVIEW |
| 3 | Car publisher-authenticated Tables 5/6 | ناقص؛ BLOCKED |
| 4 | Car Table 5 74 vs 72 and group 4/5 reversal | ناقص؛ BLOCKED |
| 5 | Eight core publisher-source bibliography entries corrected and verified | موفق؛ READY_FOR_REVIEW |
| 6 | Car Table 6 41 vs 40 | ناقص؛ BLOCKED |
| 7 | Car institutional 14 vs author-table 17 | ناقص؛ BLOCKED |
| 8 | Car 80% usefulness item denominator | ناقص؛ BLOCKED |
| 9 | Amini F7 -1.4/-1.3/-0.1 | ناقص؛ BLOCKED |
| 10 | Cvejić per-question denominator | ناقص؛ BLOCKED |
| 11 | Cvejić 46 vs 35 sampling frames | ناقص؛ BLOCKED |
| 12 | Lorite full methods | ناقص؛ BLOCKED |
| 13 | Baroni full methods | ناقص؛ BLOCKED |
| 14 | Elia full methods | ناقص؛ BLOCKED |
| 15 | G/D/R/A prospective field validation | ناقص؛ BLOCKED |
| 16 | MR independent human critical review | ناقص؛ BLOCKED |
| 17 | MR author's substantive contribution and exact-version approval | ناقص؛ BLOCKED |
| 18 | MR journal submission gate | ناقص؛ BLOCKED |
| 19 | AE C13/C14 recovery | تکمیل قبلی؛ بدون شمارش |
| 20 | AE WDI 2024 original ZIP and SHA | ناقص؛ BLOCKED |
| 21 | AE WDI 2025 original ZIP and SHA | ناقص؛ BLOCKED |
| 22 | AE WDI 2026 original ZIP and SHA | ناقص؛ BLOCKED |
| 23 | AE historical ILOSTAT independent provenance | ناقص؛ BLOCKED |
| 24 | AE direct countryatlas benchmark | ناقص؛ BLOCKED |
| 25 | AE full author-review manuscript and novelty | ناقص؛ BLOCKED |

**X: 3 fresh successful content outputs; 21 incomplete; 1 previously completed; 0 new verified failures.**

## Y/25 — ZM, CV, staging and MOJ1
| # | Independent target | This run |
|---:|---|---|
| 1 | ZM RefSeq v2.0 exact FASTA/GTF | ناقص؛ BLOCKED |
| 2 | ZM reference original checksum | ناقص؛ BLOCKED |
| 3 | ZM biological replicate independence | ناقص؛ BLOCKED |
| 4 | ZM actual FASTQ MD5s | ناقص؛ BLOCKED |
| 5 | ZM strandedness evidence | ناقص؛ BLOCKED |
| 6 | ZM multimapping adjudication | ناقص؛ BLOCKED |
| 7 | ZM 24-library integer counts | ناقص؛ BLOCKED |
| 8 | ZM actual DESeq2 analysis | ناقص؛ BLOCKED |
| 9 | ZM valid DEG/FDR | ناقص؛ BLOCKED |
| 10 | ZM author-review paper | ناقص؛ BLOCKED |
| 11 | EN CV externally verified credentials | ناقص؛ BLOCKED |
| 12 | FA CV externally verified credentials | ناقص؛ BLOCKED |
| 13 | EN staging deployed | ناقص؛ NOT_DONE |
| 14 | FA staging deployed | ناقص؛ NOT_DONE |
| 15 | Independent university-degree proof | ناقص؛ BLOCKED |
| 16 | Independent role/residence proof | ناقص؛ BLOCKED |
| 17 | Verified peer-reviewed bibliography | ناقص؛ BLOCKED |
| 18 | Future topics originality/data/rights gate | ناقص؛ NOT_DONE |
| 19 | Exact CV version owner approval | ناقص؛ BLOCKED |
| 20 | S-01 backup/rollback/public release gate | ناقص؛ NOT_DONE |
| 21 | MOJ1 new contract/security progress | ناقص؛ NOT_DONE |
| 22 | MOJ1 sponsor/Guardian Grants reply | ناقص؛ NOT_DONE |
| 23 | MOJ1 independent audit signed | ناقص؛ BLOCKED |
| 24 | MOJ1 private audit artifact 12406875421 | تکمیل قبلی؛ بدون شمارش |
| 25 | MOJ1 legal launch authorization | ناقص؛ BLOCKED |

**Y: 0 fresh; 24 incomplete; 1 previously completed; 0 new verified failures.**

## Stage, result and handoff

- **3/50 new substantive outputs**, 45 incomplete, 2 historical completed (excluded from fresh count), 0 new verified failures. Five-action floor **not met**; carry forward 2-action shortfall without padding. A single source-checked clean MR candidate is a usable internal deliverable, not a finished peer-reviewed article.
- MR **MAJOR REVISION → MAJOR REVISION**, C87 manuscript **READY_FOR_REVIEW**; AE **MAJOR REVISION** unchanged; ZM **DATA REBUILD** unchanged. CV EN/FA v3 **READY_FOR_REVIEW** unchanged; staging **NOT_DONE**; MOJ1 **BLOCKED**. **Stage transfers 0**; approved final papers 0; submissions 0; public deployment 0.
- External gates: original Car publisher table/erratum, Amini F7, Cvejić item-specific N, full Lorite/Baroni/Elia methods, prospective G/D/R/A validation or conceptual-only framing, reference titles and authors, actual human author contribution and exact-version sign-off, disclosures, journal and APC/rights. AE historical original archives and ZM exact raw inputs remain unavailable. No 149.54GB download, VPS work, MOJ1 financial/token action, Instagram/Facebook interaction, PR #1054 merge or live-site changes.
- **First exact next action:** if Car original publisher Table 5/6 is newly accessible, authenticate and adjudicate 74/72, 17/14 and 40/41; otherwise verify exact titles/author lists for contextual references 9–17 and repair the C87 bibliography without claiming full-methods validation.
