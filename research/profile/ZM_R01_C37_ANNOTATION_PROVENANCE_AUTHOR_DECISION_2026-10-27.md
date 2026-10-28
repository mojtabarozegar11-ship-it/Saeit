# ZM-R01 — C37 author provenance decision packet (internal)

**27 October 2026.** AI methodological audit only; no human-author approval or manuscript submission.

## Verified and unresolved
- **Verified from official metadata:** IWGSC v2.1 annotation reports 106,913 high-confidence genes; NCBI GCF_018294505.1-RS_2025_04 on v2.1 reports 103,793 protein-coding genes. Different gene-model definitions and pipelines: these numbers are **not comparable as the same denominator**. See [C37](../manuscripts/ZM-R01/C37_SAME_ASSEMBLY_DIFFERENT_GENE_ANNOTATION_RELEASES_2026-10-27.md).
- **Unresolved:** original Milec reference's exact v2.0 FASTA, accompanying gene annotation and file hashes; whether its annotation is IWGSC or a separately remapped release; FASTQ byte-level MD5; library strandedness; unique/multimapping handling; actual integer counts; biological replication and statistical design.
- **Not permissible:** presenting FPKM as raw counts; claiming the 1167 proposed hypotheses are DEG with FDR; substituting an accessible v2.1 assembly without marking a new reference sensitivity analysis.

## Author decisions pending
1. Supply or independently verify the exact original analysis protocol and any legitimate original reference/annotation manifest. If it cannot be found, approve a **clearly different v2.1 reanalysis** only after licensing and data feasibility checks.
2. Identify the sample-level raw data provenance and whether independent biological replicates and raw counts are obtainable without downloading 149.54GB or using VPS.
3. Verify authorship contributions, final manuscript wording, affiliation, funding, COI, AI-use, data rights, journal/APC and cover letter before any external action.

**Status: DATA REBUILD / NO SUBMISSION.** No real counts, differential expression, author signature or publisher approval.
