# MR-2026-001 C122 full-file quality control — source-backed decision
**Date:** 2026-10-30. **Status:** READY_FOR_REVIEW; **publication gate:** BLOCK_SUBMISSION.

## Exact files inspected
- Manuscript: [C122 full text](../manuscripts/MR-2026-001/MR-2026-001_C122_SOURCE_VERIFIED_REFERENCE_COMPLETION_AUTHOR_REVIEW_MANUSCRIPT_2026-10-30.md); GitHub blob SHA 2a69f0522a3eab754908f3122ad797826387ea00; 122995 Unicode code units.
- Evidence: [C122 claim matrix](../manuscripts/MR-2026-001/MR-2026-001_C122_SOURCE_TO_CLAIM_REVIEW_MATRIX_2026-10-30.tsv); GitHub blob SHA 46cff81af7b8e61d897b238e06262c4d7ead0282; 9 claim rows, 6 blocked.
- Offline gate: [C122 corrected Python implementation](r01_submission_gate_C122.py). This review ran equivalent structural checks directly on GitHub-fetched file contents in a JS analysis, **not** the Python CLI on a full local copy; no claim of executed Python regression or SHA-256 digest. GitHub blob SHA is not SHA-256.

## Deterministic actual-file checks
| Check | Result |
|---|---|
| full_sections | PASS |
| reference_sequence | PASS |
| ledger_schema | PASS |
| ledger_nonempty | PASS |
| ledger_unique | PASS |
| ledger_complete | PASS |
| https_sources | PASS |
| fan_reference | PASS |
| no_editorial_tail | PASS |
| no_internal_version_banner | PASS |
| no_placeholder | PASS |
| Bibliography | 25 consecutively numbered entries |
| Claim matrix | 9 rows; 6 source-blocked |
| C120 old gate schema | Incompatible with C121/C122 matrix: missing expected columns id, locator, printed_evidence, status; C122 gate fixes column mapping |

## Scientific resolution and limits
- **Actual bibliographic correction:** Fan & McCann (2020) was cited in the manuscript but absent from C121's numbered references. C122 adds the complete citation as reference 25 and source-to-claim row C122-09. Original primary article PDF lists *Journal of Agricultural and Resource Economics* 45(2), pp. 352–375 and DOI 10.22004/ag.econ.302459: https://ageconsearch.umn.edu/record/302459/files/JARE%2C45.2%2CMay2020_11%2CFan%2C352-375w_Supplement.pdf . The journal landing page displays 354–377; retain the original PDF page range pending publisher clarification: https://jareonline.org/articles/adoption-of-pressure-irrigation-systems-and-scientific-irrigation-scheduling-practices-by-u-s-farmers-an-application-of-multilevel-models/ .
- Fan & McCann distinguish adoption of pressure irrigation hardware from scientific scheduling practices in the 2013 FRIS; this is prior art, not evidence of independently observed advice-event adherence or causal savings.
- Car's university original institutional record verifies 72 and 45+13+14, but **does not** reconcile original Table 5 74/72 or Table 6 41/40: https://researchers.une.edu.au/en/publications/using-a-mobile-phone-short-messaging-service-sms-for-irrigation-s-5/ .
- SANRA (Baethge et al., 2019) has six items rated 0–2 by human raters; **no independent SANRA score** is assigned here: https://doi.org/10.1186/s41073-019-0064-8 .
- Remaining source-blocked claim IDs: C120-02, C120-03, C120-04, C120-06, C120-07, C120-08. No numerical replacement, invented respondent roster, or fabricated supplementary data was made.

## Release decision
**BLOCK_SUBMISSION.** The structural checks do not establish factual accuracy of all 25 citations. Author contribution and approval, independent source appraisal, journal-specific author instructions, rights/COI disclosures, approved source-limitations treatment and exact manuscript hash signoff are absent. No journal submission, editorial acceptance or publication receipt is evidenced.

**Next:** obtain independent source review and author approval of C122; choose a journal after verifying article-type and length limits; run the C122 Python CLI on exact downloaded C122 files with a human-signed manifest. No factory VPS changes.
