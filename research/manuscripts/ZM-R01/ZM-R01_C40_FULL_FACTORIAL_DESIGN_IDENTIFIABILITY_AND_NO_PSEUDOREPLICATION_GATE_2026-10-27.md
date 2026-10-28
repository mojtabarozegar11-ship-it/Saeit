# ZM-R01 C40 — 24-library 2×2×2 factorial design: algebraic estimability versus biological independence

**Date:** 2026-10-27. **Status:** executed metadata-only design-matrix derivation, no FASTQ download, no read counts, no DEGs, no FDR, no statistical test, no VPS.

## Exact input
[Previously source-verified GEO/BioSample/SRR/factor crosswalk](GSE294406_24_GSM_BIOSAMPLE_SRR_VERIFIED_CROSSWALK_2026-10-26.tsv), blob `6057129e53563bc5c85b9fbe1cf136c67a84e9c0`. This cycle generated a [24-row machine-readable sample sheet](ZM-R01_24_LIBRARY_FACTORIAL_SAMPLE_SHEET_DESIGN_ONLY_2026-10-27.tsv), preserving every original accession and factor bit. The within-cell index 1–3 is **only a nominal metadata order**, NOT evidence of a biological replicate identity.

## Executed design-matrix algebra
For each library with binary nominal factors D, H and C, construct the columns:
`[1, D, H, C, D*H, D*C, H*C, D*H*C]`.
The 24×8 matrix has **rank 8** by exact Gaussian elimination over its binary entries. All **eight cells have exactly three labelled libraries**, and no two of the 24 GSM, BioSample or SRR identifiers are repeated in the original crosswalk.

This means the *metadata-coded model is algebraically full rank*. It does **NOT** mean the 24 libraries represent 24 independent biological experimental units. The often quoted `24 - 8 = 16` residual degrees of freedom applies **only conditionally** if the relevant independent unit is the library/sample and no blocking, repeated plant, pooled biological material, common chamber or other clustering invalidates that assumption.

## Analysis plan gated on real source material
- Obtain original methods on experimental-unit allocation, chambers/pots, blocking, randomization, pooling, tissue harvest and library preparation. Specify the unit of biological replication and any nested or paired design before fitting a model.
- Identify the exact **RefSeq v2.0 assembly FASTA and annotation GTF/GFF pair** and verify source/checksum/rights. Do not silently substitute IWGSC v2.1 or NCBI's alternative annotation.
- Establish strand specificity and multimapping rules, and validate FASTQ content MD5 against provider manifest. The 48 provider-listed MD5 strings are not local verification.
- Produce a **raw nonnegative integer gene×24-library count matrix** with uniquely matched sample columns and documented common mapping/counting pipeline. FPKM values are not raw counts and cannot be used as a drop-in DESeq2 count matrix.
- Only then, conditional on valid independent units and adequate quality, consider a DESeq2 design `~ D*H*C` (R formula), inspect dispersion and diagnostics, and predefine contrasts. With 0/1 reference coding, the coefficient for D is its effect **at H=0,C=0**; the marginal D effect across H/C is not identical when interactions exist. Three-way interaction interpretation requires predeclared contrasts, uncertainty and multiple-testing adjustment.
- Predefine primary questions and family-wise/FDR strategy before inspecting gene-wise results. **1,167 historical candidate hypotheses are not 1,167 validated DEGs**. Report no FDR, p-values, biological effects or independent replication from this metadata audit.

## Critical AI release decision
The sample sheet and rank-8 design are genuine new **metadata processing outputs**, not evidence of treatment effects or experimental validity. **DATA REBUILD / NO SUBMISSION** until raw counts, reference identity, local integrity and biological independence are independently evidenced. No manuscript submission or human author approval.
