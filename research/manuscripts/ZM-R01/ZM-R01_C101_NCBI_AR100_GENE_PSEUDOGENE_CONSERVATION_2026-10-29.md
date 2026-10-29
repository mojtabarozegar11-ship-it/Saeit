# ZM-R01 C101 — NCBI AR100 gene-count decomposition, source-verified

**Owner:** R-01 · **2026-10-29** · **READY_FOR_REVIEW reference note; BLOCKED for RNA-seq/DEG findings**

## New primary-source reconciliation

The [NCBI Triticum aestivum Annotation Release 100 report](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/) identifies the reference as **IWGSC CS RefSeq v2.1, GCF_018294505.1** (assembly accession), but the **NCBI annotation product** has its own feature definitions. Its feature-count table prints:

| NCBI AR100 class | Printed count | Scope |
|---|---:|---|
| Protein-coding genes | 103,787 | Gene class |
| Non-coding genes | 32,611 | Gene class |
| Transcribed pseudogenes | 447 | Pseudogene class |
| Non-transcribed pseudogenes | 18,618 | Pseudogene class |
| Total genes **and pseudogenes** | 155,463 | All four classes |

Independent conservation checks: **103,787 + 32,611 = 136,398 non-pseudogene genes**; **447 + 18,618 = 19,065 pseudogenes**; **136,398 + 19,065 = 155,463**. The same NCBI report's separate *Detailed reports* section explicitly says those counts **exclude pseudogenes** and lists **136,398 genes**. These are internally reconcilable; **155,463 is not a valid denominator for “genes excluding pseudogenes.”**

The [IWGSC annotation v2.1 release](https://www.wheatgenome.org/resources/annotations/refseq-v2.1-assembly-and-annotation-now-freely-available-at-urgi-and-ncbi) instead counts **106,913 high-confidence + 159,840 low-confidence = 266,753** gene models, a different annotation product. This difference does not demonstrate gene gain/loss, DEG, mapping success or error in either source. Neither assembly accession nor source-reported total proves equality of GFF/GTF file bytes.

## Executable decision for ZM-R01

Before count normalization or differential expression, record the exact paired FASTA+GFF/GTF file checksums and release, the **24 project-specific FASTQ accession/checksum/sample-condition records**, a gene-ID namespace, and an integer raw-count matrix. For NCBI AR100, distinguish 136,398 non-pseudogene genes from 155,463 all genes+pseudogenes; do not substitute IWGSC's 266,753 gene-model total. NCBI's publicly listed RNA-seq evidence samples used to *build its annotation* are **not automatically the 24 samples of ZM-R01**. If project-specific sample provenance is absent, maintain **BLOCKED_SAMPLE_PROVENANCE**; no claim of 1,167 DEGs or computed FDR.

**New scientific correction:** one NCBI source's apparently competing 155,463 and 136,398 figures are different explicitly defined populations, exactly reconciled by the 19,065 pseudogenes. **No biological experiment or FASTQ was fabricated.**
