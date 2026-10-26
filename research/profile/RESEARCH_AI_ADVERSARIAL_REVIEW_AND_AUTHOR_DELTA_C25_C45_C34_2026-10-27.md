# Internal AI adversarial scientific review and human-author delta — 27 October 2026

**Internal reviewer:** ChatGPT (AI), **not** an independent human referee, manuscript author, publisher or legal representative. **Scope:** newly created C25 (AE), C45 (MR), C34 (ZM), source-aligned manuscript text changes. No journal submission, human sign-off, legal declarations or publication is implied.

## MR-2026-001 — C45 (new conditional arithmetic bound)
- **Pass, narrow:** 6 counts sum to 74, displayed total 72; there are 6 ways to subtract 2 from one count and 15 ways to subtract 1 from two distinct counts = 21 distinct minimal nonnegative two-count repairs. Groups 1–3 can only sum 34–36 after these hypothetical deletions; 68% of 72 would require ~49. Hence the table total alone does not identify a unique correction, and a two-count-only repair cannot reconcile the prose's 68%.
- **Major limitations:** input is a text extraction from an author-uploaded version; publisher typeset page image remains unauthenticated. The 68% may refer to a different population/definition; categories could overlap or have an erroneous total. The mathematical premise is not evidence of a source error mechanism. Do not state any repaired group proportion as fact. This proof **does not validate G/D/R/A** or demonstrate novelty.
- **Release gate:** original publisher Table 5 or author clarification, Amini F7, Cvejić denominator, event-linked independent field evidence and a comparator study. **MAJOR REVISION / NO SUBMISSION.**

## AE-2026-001 — C25 (new matched-pair robustness)
- **Pass, narrow:** 153 fixed three-endpoint countries, matched per-country differences, source-locked arithmetic. Paired median d −1.925832 log-pp/year, 10% trimmed mean −1.837483; conditional country-resampling percentile interval [−2.540285, −1.382149], seven-region cluster-resampling [−2.538920, −0.785653]. These do not use the 155-country historical-vintage fixed cohort.
- **Major limitations:** country-level bootstrap treats selected countries as exchangeable; seven regions are too few for reliable cluster-robust coverage, and the region bootstrap weights large regions by their repeated country counts. Unequal 19-year and 4-year periods, overlap of the 2019 boundary, non-random missingness, and region dependence undermine global/causal interpretation. Do not call intervals confidence intervals for world agriculture. This descriptive robustness cannot establish historical WDI revision mechanism, independent ILO data, novel estimator or publication priority.
- **Release gate:** historical ILOSTAT 2024/2025 provenance, original countryatlas three-vintage comparison, novelty comparison and author approval. **MAJOR REVISION / NO SUBMISSION.**

## ZM-R01 — C34 (new official version-lineage clarification)
- **Pass, narrow:** IWGSC contemporaneous documentation confirms original 2019 v2.0 assembly preceded its planned annotation; official v2.1 README documents subsequent assembly corrections and a distinct version. Thus the published phrase 'RefSeq v2.0, EnsemblPlants' is insufficient to recover the exact FASTA/GTF pair.
- **Major limitations:** **do not infer** that Milec used an incompatible annotation or misreported the reference. A 2025 workflow may have accessed a later valid annotation; the exact files are unknown. No raw counts, chamber randomization, independent read QC or FDR can be reconstructed from FPKM. No genome or FASTQ bulk download authorized.
- **Release gate:** exact source manifest and rights, treatment-unit independence, genuine integer counts, multimapping policy, prespecified model and source-linked biological validation. **DATA REBUILD / NO SUBMISSION.**

## Exact author-review decision packet (human action required before any submission)
The manuscript texts were revised on the research branch, but the previous MR/AE Word artifacts **predate these new C45/C25 changes**. They must be regenerated and verified against the new text before any author sign-off. The author must personally confirm actual intellectual contribution, author identity/affiliation, all references, funding/COI/AI-use disclosures, publication rights, journal/APC and cover letter. No assistant-generated approval or signature substitutes for this decision.

**Stage transitions in this cycle:** MR and AE manuscript text **revised within MAJOR REVISION**; ZM **source lineage clarified within DATA REBUILD**. **0** to author-approved, submitted, peer-reviewed, accepted or published. **No live site deployment**; PR #1054 must remain draft/unmerged.
