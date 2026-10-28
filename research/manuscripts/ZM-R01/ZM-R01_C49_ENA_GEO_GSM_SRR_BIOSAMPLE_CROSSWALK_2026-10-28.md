# ZM-R01 C49 — source-pinned ENA/GEO crosswalk audit (metadata only)

**Date:** 2026-10-28. **Stage:** DATA REBUILD / NO SUBMISSION. No FASTQ was downloaded, no R/DESeq2 run, no new DEG/FDR result.

## Inputs and identity
- Source-pinned ENA metadata: `ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv`, Git blob SHA-1 `d9231121dc27bc13999e120349a80af05aad5e15`.
- Previously prepared GEO-derived factorial sample sheet: `ZM-R01_24_LIBRARY_FACTORIAL_SAMPLE_SHEET_DESIGN_ONLY_2026-10-27.tsv`, Git blob SHA-1 `988be37b2b8ae02f3c3c3546fb5e6f49865b2099`.
- This **new comparison** matched every sample-sheet `srr` to ENA `run_accession` and compared its `biosample` to ENA `sample_accession` (24/24, zero discrepancies). All 24 GSM, 24 SRR, and 24 ENA run identifiers were unique. The eight **nominal** D/H/C cells each contain three libraries.
- Sum of ENA-declared paired compressed FASTQ file sizes: **149,540,873,452 bytes (149.540873 decimal GB)**. These are *declared metadata sizes*, not independently downloaded/verified bytes.

## Scientific interpretation and unresolved gates
This crosswalk establishes internal consistency **between two retained snapshots**, not independent proof that ENA/GEO records are authentic, that a biological sample is an independent treatment-assignment unit, or that a title's treatment labels are experimentally correct. It also does not establish RefSeq v2.0 assembly/annotation compatibility, strandedness, multimapping assignment, FASTQ MD5 recomputation, or a complete 24-library integer-count matrix. A pilot one-library count vector cannot be promoted to a 24-library differential-expression result.

## Required machine gate
Before a full DESeq2 run, require the R analysis script to verify the exact pinned GEO sample-sheet bytes, check GSM→SRR against the submitted 24-row manifest, then check SRR→BioSample against pinned ENA, in addition to existing R1/R2 MD5 checks. Fail closed on any disagreement. The pinned-sheet check is provenance traceability, **not scientific verification of independent chambers**.

**Decision:** source crosswalk internally consistent; independent biological units and all other primary-data gates remain unresolved. **NO SUBMISSION.**
