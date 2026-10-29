# ZM-R01 C110 — verified NCBI wheat RefSeq release pin / RNA-seq acceptance boundary
Owner R-01 | 2026-10-30 | Document FILE READY_FOR_REVIEW; RNA-seq analysis BLOCKED_FASTQ_PROVENANCE.

## Reference identity verified against original NCBI release report
- Organism: *Triticum aestivum*; assembly **GCF_018294505.1**, IWGSC CS RefSeq v2.1; 22 assembled chromosomes plus unplaced scaffolds.
- Annotation **GCF_018294505.1-RS_2025_04**; transcript/protein evidence queried 2025-04-16; submission 2025-04-18; NCBI pipeline 10.3.
- NCBI reports **103,793 protein-coding gene loci**, **32,609 noncoding gene loci**, **448 transcribed pseudogenes**, **18,617 nontranscribed pseudogenes**: 155,467 gene/pseudogene features in total. 142,414 mRNA and 142,450 CDS features are NOT unique gene counts.
- Prior release 100 reports 103,787 protein-coding loci and 32,611 noncoding loci on the same assembly. Differences are annotation-release changes, not experimental gain/loss.
- Primary sources: https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/ and https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/

## Machine-actionable acceptance matrix
| Artifact | Required identity | Current disposition |
|---|---|---|
| Genome assembly FASTA | GCF_018294505.1; file URL, download UTC, byte size, SHA-256 | BLOCKED: raw bytes/hash not captured |
| Gene annotation GFF3 | same assembly + RS_2025_04; file SHA-256 and feature-type schema | BLOCKED: raw bytes/hash not captured |
| Sample FASTQ | accession, paired/single, library prep, biological replicate, raw byte SHA-256, sample metadata | BLOCKED: no authenticated sample input |
| Count matrix | gene IDs, annotation release, quantifier version, library sizes, mapping rate | BLOCKED: no real reads |
| Differential expression | contrast, biological replicates, dispersion model, multiple-testing correction | BLOCKED: cannot claim DEGs/FDR |
| Human author decision | organism/trait hypothesis and experimental design approved | READY_FOR_REVIEW, not approved |

**Use rule:** NCBI feature totals are reference annotation metadata only. Do not report them as observed expression, biological treatment effects, sample count or validated novel genes. First atomic next action: obtain authorized FASTQ accession/file manifest and hashes; pin the NCBI GFF3/FASTA bytes and verify IDs before building any count matrix.
