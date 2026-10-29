# ZM-R01 C104 — same RefSeq assembly, different NCBI annotation releases

**Owner:** R-01. **Stage:** READY_FOR_REVIEW reference-source reconciliation; RNA-seq/DEG BLOCKED. **Date:** 2026-10-29.

## Newly verified official NCBI evidence

The original [NCBI Triticum aestivum Annotation Release 100](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/) and [updated annotation release GCF_018294505.1-RS_2025_04](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/) both refer to **the same RefSeq assembly GCF_018294505.1 / IWGSC CS RefSeq v2.1**, but not to the same feature annotation release. NCBI explicitly says the 2025 update placed known RefSeq transcripts current on 2025-04-16 and retained current models from Release 100 without recalculating those models.

| Feature category | AR100 | RS_2025_04 | Difference |
|---|---:|---:|---:|
| Protein-coding genes | 103,787 | 103,793 | +6 |
| Noncoding genes | 32,611 | 32,609 | −2 |
| Transcribed pseudogenes | 447 | 448 | +1 |
| Nontranscribed pseudogenes | 18,618 | 18,617 | −1 |
| Genes excluding pseudogenes (calculated) | 136,398 | 136,402 | +4 |
| Pseudogenes (calculated) | 19,065 | 19,065 | 0 |
| Genes and pseudogenes total | 155,463 | 155,467 | +4 |

Independent conservation: 103793+32609=136402; 448+18617=19065; 136402+19065=155467. The 2025 report **does not** mean the genome assembly changed; annotation product and annotation release identity changed. A 4-gene change in source feature totals is **not** a differential-expression result, biological gene gain/loss or evidence for a 1,167-DEG claim.

## Executable analysis hold

Lock the exact **assembly accession + annotation release + FASTA SHA-256 + GTF/GFF SHA-256 + gene-ID namespace** before counting. For any raw count matrix, do not combine AR100 gene identifiers with RS_2025_04 features without an explicit mapping and collision audit. Project-specific 24 FASTQ libraries, consent/collection provenance, actual alignments, independent biological replicates and count matrices remain unavailable. Maintain `BLOCKED_FASTQ_PROVENANCE` and `BLOCKED_ANNOTATION_HASH`; do not fabricate raw observations or infer FDR.
