# ZM-R01 C37 — Same v2.1 assembly, distinct gene annotation authorities and release dates

**27 October 2026 | New metadata-level original-source comparison.** No genome/FASTQ download, integer-count matrix, MD5 verification, DEG, FDR, or exact v2.0 replication.

## Verified source metadata (do not mix)

1. IWGSC consortium describes its **RefSeq v2.1 assembly** and **IWGSC Annotation v2.1** as a coordinated release; the IWGSC gene annotation contains **106,913 high-confidence (HC) genes and 159,840 low-confidence (LC) genes**, total **266,753 genes**. Its assembly and annotation were announced as freely available under NCBI BioProject **PRJNA669381**. Original consortium: https://www.wheatgenome.org/resources/annotations/refseq-v2.1-assembly-and-annotation-now-freely-available-at-urgi-and-ncbi ; corroborating archived announcement: https://graingenes.org/GG3/content/iwgsc-refseq-v21-assembly-and-annotation-now-freely-available-urgi-and-ncbi-and-graingenes .
2. **NCBI RefSeq annotation release GCF_018294505.1-RS_2025_04** uses the **IWGSC CS RefSeq v2.1 assembly GCF_018294505.1** but is an **NCBI Eukaryotic Genome Annotation Pipeline** product updated in April 2025. NCBI reports **155,467 genes and pseudogenes**, of which **103,793 protein-coding**. These counts use a **different gene/pseudogene classification** and annotation pipeline from IWGSC HC/LC, so the totals must not be treated as directly comparable measurements of the same feature definition. Original NCBI: https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/ .
3. NCBI earlier Annotation Release **100** also uses GCF_018294505.1, but reports **103,787 protein-coding genes**. Even within the NCBI pipeline, gene models and counts are release-specific. Original NCBI: https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/ .
4. The URGI v2.1 annotation directory contains `iwgsc_refseqv2.1_gene_annotation_200916.zip` (397 MB) with a separately listed MD5 file. The assembly directory contains `iwgsc_refseqv2.1_assembly.fa.zip` (4.1 GB) with its MD5 file. **Only directory metadata was inspected; neither archive nor checksum contents were downloaded or locally validated.** Sources: https://urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Annotations/v2.1/ and https://urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Assemblies/v2.1/ .

## New technical consequence

**Assembly identity alone is insufficient to identify the counting reference.** At least three distinct gene-model releases can be associated with the same v2.1 genome lineage (IWGSC Annotation v2.1, NCBI Annotation Release 100, NCBI RefSeq 2025_04). Replacing the original paper's unspecified `RefSeq v2.0` annotation with any of these would create a *new analysis with a different gene universe*, not an exact replication. A differential-expression matrix must be traced to **both** a sequence assembly and a precisely identified annotation file, including chromosome names, gene IDs, feature type and transcript-to-gene aggregation rules. Gene counts from different annotation authorities cannot validate the published 1167 hypotheses or turn FPKM into integer counts.

## Minimal release gate

- Identify the **exact original v2.0 FASTA and gene annotation provenance** from the Milec methods or authors; do not infer it from an Ensembl URL slug or v2.1 accession.
- Record `assembly_accession`, `fasta_filename`, `fasta_sha256/md5`, `annotation_authority`, `annotation_release`, `annotation_filename`, `annotation_sha256/md5`, `feature_type`, `gene_id_attribute`, `seqname_compatibility`.
- Validate multimapping, strandedness, biological replication, original FASTQ MD5 and genuine integer read counts before any differential-expression claim.
- If original v2.0 files cannot be recovered and rights verified, label any public v2.1/NCBI work **reference/annotation sensitivity reanalysis**, not a reproduction of the paper.
- No 149.54GB bulk download, VPS, cost, fabricated results, DEG/FDR or submission.

**Decision: DATA REBUILD / NO SUBMISSION.** The original v2.0 reference, annotation and counts remain unverified.
