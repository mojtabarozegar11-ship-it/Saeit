# ZM-R01 — C107 RefSeq wheat gene/transcript/CDS feature-unit crosswalk
**Owner:** R-01 | **Date:** 2026-10-29 | **Reference note:** READY_FOR_REVIEW | **RNA-seq result:** BLOCKED_FASTQ_PROVENANCE

## Official NCBI release-level observations
Both [NCBI Annotation Release 100](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/) and [GCF_018294505.1-RS_2025_04](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/) describe annotation of the **GCF_018294505.1 / IWGSC CS RefSeq v2.1** assembly, but the feature sets and release dates differ. They are not different biological experiments.

| Counted object | Release 100 | RS_2025_04 | Unit of counting |
|---|---:|---:|---|
| Protein-coding genes | 103,787 | 103,793 | gene loci, not transcripts |
| Noncoding genes | 32,611 | 32,609 | gene loci, not ncRNA transcripts |
| Genes excluding pseudogenes | 136,398 | 136,402 | sum of two gene categories |
| Transcribed pseudogenes | 447 | 448 | pseudogene loci |
| Nontranscribed pseudogenes | 18,618 | 18,617 | pseudogene loci |
| Genes + pseudogenes | 155,463 | 155,467 | all gene/pseudogene features |
| mRNAs | 142,406 | 142,414 | transcript features; multiple isoforms per gene possible |
| CDS features | 142,442 | 142,450 | CDS features; **not** protein-coding gene loci |

**Newly resolved unit problem:** the figure **142,414 mRNAs** (2025 release) must not be reported as 142,414 genes or 142,414 independently expressed loci. The **142,450 CDS features** are likewise not 142,450 protein-coding genes. The gene-level denominator is 103,793 protein-coding loci (or 136,402 including noncoding genes, depending on the prespecified question); neither count represents observed expression. All numbers are source *annotation-feature totals*, not sample data, validated read counts or differentially expressed genes. The four-gene total difference across annotation releases is a release-content difference, not biological gene gain/loss.

## Reproducible count gate
1. Lock genome assembly accession and version; NCBI annotation release; GFF/GTF and FASTA SHA-256; gene-ID namespace and filtering rules.
2. Decide whether the estimand is gene, transcript or CDS before quantification. If transcript-level quantification is used, declare an explicit transcript-to-gene map and handling of multi-mapping/ambiguous transcripts; never substitute raw transcript rows for genes.
3. Require real FASTQ accession/file hash, sample metadata, replicate structure, library protocol, alignment/quantification version and a count-matrix provenance manifest.
4. Differential-expression estimates and FDR remain **BLOCKED** until all sample data, design and code have been validated. The published feature counts cannot support any purported 1,167-DEG finding.

**Next atomic action:** obtain authorized sample FASTQ identifiers and raw hashes, then pin the annotation file hashes and create an explicit transcript-to-gene map. Earlier [C104 release reconciliation](ZM-R01_C104_NCBI_SAME_ASSEMBLY_ANNOTATION_RELEASE_DELTA_2026-10-29.md) remains in force.
