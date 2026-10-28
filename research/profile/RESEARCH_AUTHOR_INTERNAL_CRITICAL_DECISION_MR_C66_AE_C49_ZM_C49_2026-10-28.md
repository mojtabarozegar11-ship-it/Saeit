# Internal AI critical review and human-author decision packet — MR C66 / AE C49 / ZM C49

**28 October 2026. INTERNAL ONLY.** Prepared by AI as scientific/administrative assistance; **not** a human peer review, authorship, approval, journal decision or publication.

## Newly completed in this cycle

**MR-2026-001 — MAJOR REVISION.** Source-level cross-publication audit of the Lorite/García-Vila/Santos research cluster at Genil–Cabra, Spain: same irrigation district and overlapping author teams across 2008, 2010, 2012 and 2013 reports. Exact plot/sample/year overlap is **not proven**. The author-review manuscript now prohibits treating the papers as independent site replications or summing plot totals without original methods. New source audit: [C66](../manuscripts/MR-2026-001/MR-2026-001_C66_GENIL_CABRA_EVIDENCE_CLUSTER_NONINDEPENDENCE_AUDIT_2026-10-28.md).

**AE-2026-001 — MAJOR REVISION.** Historical countryatlas comparator script now fails closed on unpinned 155-country cohort SHA256, nonmatching World Bank source-57 YYYYMM release IDs and any API warning including unit mismatch. Public 4.0.0 docs were inspected; required package 3.0.0 **not executed**. Original C13/C14 records were recovered as historical controls, not new findings. New note: [C49](../manuscripts/AE-2026-001/AE-2026-001_C49_COUNTRYATLAS_RELEASE_ID_COHORT_HASH_WARNING_GATES_2026-10-28.md).

**ZM-R01 — DATA REBUILD.** An independent comparison of two pinned metadata snapshots found 24/24 matching GSM→SRR→BioSample links, 8 nominal treatment cells with 3 libraries each and 149,540,873,452 ENA-declared compressed bytes. The analysis R code now refuses to proceed if those pinned mappings differ from the submitted manifest. This **does not** verify the independence of chambers, source authenticity, reference/annotation, 48 actual FASTQ hashes or the full integer-count matrix. New note: [C49](../manuscripts/ZM-R01/ZM-R01_C49_ENA_GEO_GSM_SRR_BIOSAMPLE_CROSSWALK_2026-10-28.md).

## Nondelegable author decisions (ALL PENDING)
- Personally assess and substantively revise the scientific argument and all source interpretations; verify relevant original full texts and contradictory Car/Amini/Cvejić figures.
- Approve final manuscript text, actual contribution statement, identity, affiliation, funding/COI/AI disclosures, intellectual-property rights and journal/APC terms **separately and explicitly**.
- Confirm source-provenance and ethical/data-use permissions; do not claim original biological experiments, author signatures or external peer review without evidence.
- Do not generate a cover letter, manuscript submission, acceptance or Manuscript ID before explicit final authorization.

## Scientific gate decisions
| Manuscript | Current stage | Newly resolved scope | Still blocks final approval |
|---|---|---|---|
| MR | MAJOR REVISION | Source dependence risk documented and text qualified | Car Table 5, Amini F7, Cvejić respondent denominator, Lorite/Baroni/Elia full methods, independent G/D/R/A validation, human scientific contribution |
| AE | MAJOR REVISION | Historical benchmark input/release/warning guards implemented | Independently verified 155 cohort, actual API benchmark, WDI/ILOSTAT vintages, current-source and common-source limitation, novelty and author review |
| ZM | DATA REBUILD | 24/24 pinned crosswalk checked; R gate added | Exact RefSeq v2.0 FASTA/GTF checksums, real 48 FASTQ MD5, multimapping, independent biological units, 24-column integer counts, valid DEG/FDR |

**Stage transitions to approved/submitted/accepted/published: ZERO.** No live-site write, VPS use, bulk download, payment, contract, prohibited social interaction or merge of PR #1054. **ALL THREE: NO SUBMISSION.**
