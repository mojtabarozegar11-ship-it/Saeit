# Research and MOJ1 evidence checkpoint — 2026-10-28 / C69

**Status:** READY_FOR_REVIEW for the updated MR working draft and author packet; **BLOCKED** for scientific finalization, external audit, public release and any financial engagement. This file is a checkpoint, not a scientific or commercial deliverable by itself.

## New, source-supported manuscript improvement

**ID:** MR-C69-20261028-v1. **Before:** the active eight-case MR manuscript lacked Berthold et al. (2021) as a direct adoption-survey prior-art comparator. **After:** Section 1.2d and the bibliography now explicitly distinguish mailed/returned/usable and item-specific denominators; the C67 author decision packet links the same source extraction.

- [New primary-source extraction](manuscripts/MR-2026-001/MR-2026-001_C69_BERTHOLD_2021_SURVEY_ATTRITION_ADOPTION_EVIDENCE_2026-10-28.md), Git blob `03fb1300a4e77b6d9a6673127906a14182961b49`.
- [Updated working manuscript](manuscripts/MR-2026-001/MR-2026-001_C50_CLEAN_EIGHT_CASE_AUTHOR_REVIEW_MANUSCRIPT_2026-10-27.md), Git blob `ea6206a455b6ffa25ac111ee0b983e5ab3fd2a7c`.
- [Updated author decision packet](manuscripts/MR-2026-001/MR-2026-001_C67_AUTHOR_REVIEW_CLAIM_EVIDENCE_DECISION_PACKET_2026-10-28.md), Git blob `40879c8165753fb8eece9e84626fe04c154caa83`.
- **Primary publication:** Berthold TA et al., *Smart Agricultural Technology* (2021), DOI https://doi.org/10.1016/j.atech.2021.100016 ; open publisher Methods section 2 and Table 1 inspected. **Reported:** 1,500 mailed, 96 undeliverable, 310 returned, 77 usable, item-specific n=41–54. **Derived:** 310/1404=22.08% returned/deliverable; 77/1404=5.48% usable/deliverable. Not independently observed recommendation adherence.
- **Reproduction:** `python -c "assert round(310/(1500-96)*100,2)==22.08; assert round(77/(1500-96)*100,2)==5.48"`. This checks arithmetic only, not the survey's field data.
- **Read-back test:** all three GitHub files re-fetched at the research branch after writes, and their C69 markers, DOI and status guards checked. No journal peer review or source data replication.
- **Next gate:** original Car Table 5 image, Amini F7, Cvejić survey denominator, Lorite/Baroni/Elia full methods, G/D/R/A evidence; substantive sole-human-author decisions and exact-version approval. **MR remains MAJOR REVISION / NO SUBMISSION.**

## AE, ZM and CV — retained state, not fresh completion

- AE: historical [C13](manuscripts/AE-2026-001/AE-2026-001_C13_FOUR_ECONOMY_2023_ATTRITION_ORDER_STATISTIC_AUDIT_2026-10-26.md) and [C14](manuscripts/AE-2026-001/AE-2026-001_C14_THREE_ENDPOINT_AVAILABILITY_MASK_CENSUS_2026-10-26.md) re-fetched; blob SHAs `18b9ad91b521589ecba2629162d5c738737e337b` and `ec5fb36b573e068a56d1c6fd4b32c48d4cb45fab`. No historical ILOSTAT or countryatlas benchmark completed. **MAJOR REVISION / NO SUBMISSION**.
- ZM: exact RefSeq v2.0 FASTA/GTF and verified checksums, 48 FASTQ MD5 recomputations, independent sample units and 24-library integer-count matrix still unavailable. No DEG/FDR. **DATA REBUILD / NO SUBMISSION**. No bulk FASTQ/VPS use.
- [English CV](profile/cv/MOJ_ROOZEGAR_CV_EN_2026-10-28_v1_REVIEW_ONLY.md) and [Persian CV](profile/cv/MOJ_ROOZEGAR_CV_FA_2026-10-28_v1_REVIEW_ONLY.md) remain **READY_FOR_REVIEW**, not independently credential-verified; no public personal-site release or institutional submission.

## MOJ1 — public-safe external security funding checkpoint

- [Independent-security Mainnet NO-GO issue](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853) and [reward-claims NO-GO issue](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1055) remain gating. No independent final report or verified release authorization.
- [Public sponsor issue #1395](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1395) updated 2026-10-28 to distinguish a provider's willingness to receive direct third-party fee coverage from **an actual funded award**. Another provider's preliminary USD 800 audit scope still requires an independently identified sponsor, written authorization, KYC and a payer deposit. **No sponsor secured; no fee waiver or independent audit awarded.**
- **Privacy:** this public checkpoint does not reproduce private email bodies, recipient identities, financial account details or sensitive credentials. Original email conversations remain in authorized Gmail.
- **Next gate:** independently identified legitimate sponsor and verified all-in scope/terms; separate owner approval of any contract, payer, cost, compliance and audit. No token allocation, Mainnet, sale, reward payout, deposit, or commitment authorized.

**Global safety:** no production website changes, VPS work, large FASTQ download, prohibited social-account interactions, journal submissions, contracts or payments. PR #1054 must remain unmerged. No new scientific finding is asserted from old C13/C14 or old CV files.
