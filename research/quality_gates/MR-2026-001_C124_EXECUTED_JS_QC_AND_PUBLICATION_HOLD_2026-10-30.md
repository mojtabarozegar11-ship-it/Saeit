# R-01 C124 — executed full-content QC and publication hold

**Date:** 2026-10-30. The entire C123 manuscript and its 11-row ledger were fetched through authenticated GitHub access. A corrected C124 full manuscript and 12-row source/claim ledger were created on the R-owned research branch and **both were fetched back and compared for exact text equality**.

## Actual checks performed
- Executed JavaScript equivalent of the 11 structural checks in `r01_submission_gate_C122.py` on the complete revised manuscript and claim ledger: **11/11 PASS** (required sections, review type, consecutive bibliography numbering, DOI syntax, nine required ledger fields, nonempty rows, unique IDs, populated fields, HTTPS sources, no editorial banner, no TODO/TBD markers).
- **25** consecutively numbered references; **12** complete claim rows; **8** source rows retain explicit `BLOCKED` statuses. These are structural checks, not independent source certification.
- Original Amini Tables 4–5 cross-check: F7 displayed WP 4.6 vs 6.0 kg/m³ implies **−23.333333%** relative change, nearest-tenth rounding interval approximately **−24.793388% to −21.848739%**. Source Table 5 prints **−3.22** under a percentage-change heading.
- F5 displayed WP 8.4 vs 4.6 kg/m³ implies **+82.608696%**, rounding interval **+79.569892% to +85.714286%**; source Table 5 prints **+3.87**. No silent reconstruction of the source's intended percent metric.
- Primary source: https://www.nature.com/articles/s41598-025-26567-z ; C124 ledger corrects F7 source location to **Figure 12**, Tables 4–5, Results and Conclusion.

**Explicit limitations:** The Python CLI was **not executed** on the full C124 files; the JavaScript checks were executed instead. No source raw-byte hash, independent peer review, journal-specific editorial screening, human author sign-off, journal submission or acceptance was obtained.

**Decision: READY_FOR_REVIEW / BLOCK_SUBMISSION.** Car 74/72 and 41/40, Amini exact F7/percentage definition, Cvejić respondent roster and Baroni supplement remain unadjudicated. No factory/VPS, live-site, payment or deployment operations.

**Next:** run the existing Python CLI on C124 outside the factory, obtain independent scholarly review and the author's decision on explicit limitations, then select journal and prepare a submission package for author approval.
