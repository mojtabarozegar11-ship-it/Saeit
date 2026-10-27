# Research author decision packet — MR C53 / AE C39 / ZM C38
**27 October 2026 | Internal AI scientific critique only. Not a human peer review, author signature or publication authorization.**

## MR-2026-001 — substantive novelty revision
- **New primary-literature challenge:** Lorite et al. (2012), DOI https://doi.org/10.1007/s11269-012-0023-3, already evaluated actual farmer irrigation versus local advisory recommendations with ARIS_LIAS over five years in southern Spain. Springer-indexed abstract and independent Wiley bibliography verified; full Lorite methods/tables not accessed. The published abstract gives approximate actual/recommended ratios 0.23 (wheat/sunflower) and 0.94 (maize); these are NOT event adherence rates or causal savings.
- Manuscript introduction, critical argument and references were revised to explicitly reject claims of priority over this earlier comparison. Audit: [C53](../manuscripts/MR-2026-001/MR-2026-001_C53_LORITE_2012_DIRECT_ADVICE_VS_APPLIED_ARIS_PRIOR_ART_2026-10-27.md).
- **Still required:** full Lorite methods; original Car Tables 5/6 image and denominator reconciliation; Amini F7; Cvejić respondent denominator; full Baroni and Elia methods; empirical G/D/R/A; human author scientific contribution and manuscript approval.
- Decision: **MAJOR REVISION / NO SUBMISSION**.

## AE-2026-001 — provenance and version control
- countryatlas WDI archives are API source 57; a 2025-10 API label is not automatically identical to a dated local October 2025 ZIP. Current package reference docs are version 4.0.0, whereas earlier project CAGR execution used 3.0.0; version pin and 2000/2019 endpoint matching are mandatory. Audit: [C39](../manuscripts/AE-2026-001/AE-2026-001_C39_COUNTRYATLAS_SOURCE57_RELEASE_IDENTITY_AND_YEAR_MATCH_GATE_2026-10-27.md).
- **Independent fresh calculation check:** the existing source-locked 217-row CSV was reparsed in JavaScript; exactly 157 valid endpoint pairs and 60 missing were found. Counts of annual growth exceeding thresholds 0/1/2/3/5 were **132/114/87/64/19**, respectively, matching C38. Regional counts also matched. This is a new independent reproducibility check of **previous** C38, **not a new finding**.
- **Still required:** matched source-57 countryatlas benchmark, ILOSTAT 2024/2025 historical files, source overlap and employment-denominator caveats, innovation argument, human author review.
- Decision: **MAJOR REVISION / NO SUBMISSION**.

## ZM-R01 — sample-level provenance, not differential expression
- Indexed original GEO records link GSE294406 to **GSM8904977 / SRX28347593 / SAMN47891429** and **GSM8904978 / SRX28347592 / SAMN47891428**. These are only two sample examples. Submitter descriptions mention RefSeq v2.0/EnsemblPlants and FPKM. See [C38](../manuscripts/ZM-R01/C38_GSE294406_TWO_SAMPLE_METADATA_AND_MD5_VERIFICATION_BOUNDARY_2026-10-27.md).
- **Still required:** complete accession/run manifest; exact FASTA/GTF and checksum; original sample/condition/replicate map; strandedness, multimapping and actual integer counts; byte-verified FASTQ MD5 if permitted. Do not convert FPKM or 1,167 hypotheses into DEG/FDR claims.
- Decision: **DATA REBUILD / NO SUBMISSION**.

## Publication and rights firewall
No submission, fee, contract, external outreach, legal commitment, author signature, manuscript ID, journal/APC selection, live website deployment or interaction with prohibited Instagram/Facebook accounts. Human author must explicitly approve final text, actual intellectual contribution, identity/affiliation, funding, COI, AI use, rights and cover letter. PR #1054 remains outside the permitted merge scope.
