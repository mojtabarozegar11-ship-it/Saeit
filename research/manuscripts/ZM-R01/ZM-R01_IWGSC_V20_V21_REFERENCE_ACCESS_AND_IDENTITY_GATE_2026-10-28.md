# ZM-R01 — official IWGSC RefSeq v2.0 vs v2.1 source-identity and access gate

**Date:** 2026-10-28. **Status:** READY_FOR_REVIEW for source decision; **BLOCKED** for actual FASTA/GTF provenance, FASTQ integrity, raw count matrix, alignment and DESeq2. **No genomic download or invented checksum.**

## Primary-source findings with concrete links

1. The [IWGSC official RefSeq v2.0 announcement](https://www.wheatgenome.org/resources/sequences/iwgsc-refseq-v2.0-now-available-at-urgi) identifies a v2.0 Chinese Spring assembly and an [URGI v2.0 assembly repository](https://urgi.versailles.inra.fr/download/iwgsc/IWGSC_RefSeq_Assemblies/v2.0/). It explicitly says access required registration and signature of an IWGSC Data Access Agreement; the original announcement says the release was *not yet annotated at that time*. This does **not** prove whether a matched v2.0 annotation was subsequently released. **No agreement was signed by this project.**
2. The [IWGSC official v2.1 release](https://www.wheatgenome.org/resources/annotations/refseq-v2.1-assembly-and-annotation-now-freely-available-at-urgi-and-ncbi) identifies **v2.1 assembly plus matched v2.1 annotation**, available without restriction at URGI and NCBI project **PRJNA669381**. NCBI identifies its RefSeq assembly as **GCF_018294505.1**, *IWGSC CS RefSeq v2.1*, in the [NCBI annotation release](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/).
3. The [URGI v2.1 assembly directory](https://urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Assemblies/v2.1/) lists `iwgsc_refseqv2.1_assembly.fa.zip` and a separate `.md5.txt` checksum locator; the [v2.1 annotation directory](https://urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Annotations/v2.1/) lists `iwgsc_refseqv2.1_gene_annotation_200916.zip` and its own checksum locator. **These are file locators, not locally downloaded or verified bytes**. The 4.1 GB v2.1 assembly ZIP is not downloaded in this cycle.
4. **Important non-equivalence:** `GCF_018294505.1` is explicitly labeled **v2.1** by NCBI. It cannot be used as proof that a pipeline used **v2.0**, even if a manifest contains a syntactically valid `GCF_` accession. The current [ZM preflight](../../quality_gates/zm_r01_preflight.py) validates `GCF_` syntax, file checksums and coordinate compatibility; it does **not** independently authenticate the assembly version or the source license. Thus a metadata-only PASS is not biological provenance validation.

## Practical, non-fabricated decision

| Route | Source identity | Data access and rights | Exact status |
|---|---|---|---|
| A: **Keep v2.0** | Use only exact v2.0 FASTA and annotation actually matched to that assembly | Check current URGI/IWGSC access terms and obtain authorized access if required; verify v2.0 annotation exists, filenames, hashes and license | **BLOCKED** — no authenticated exact FASTA/GTF or agreement evidence |
| B: **Amend methods to v2.1** | Use official matched **v2.1** assembly and annotation, with explicit methodological change | Official v2.1 release is unrestricted; source files, MD5, SHA256 and annotation coordinates must still be verified locally | **READY_FOR_REVIEW** as a possible methodology change; **not executed** |
| C: **Use NCBI latest annotation on v2.1** | `GCF_018294505.1` with named NCBI annotation release | Verify sequence/annotation matching, release dates and gene identifier namespace; do not assume IWGSC v2.1 gene models equal NCBI models | **NOT_DONE** |

**No silent substitution:** Routes B/C require explicit scientific author decision and a revised analysis protocol; changing assembly and gene models may alter quantification and the definition of the 105,200 FPKM feature identifiers. None of the **1,167 exploratory hypotheses** is a validated DEG/FDR finding.

## Before any DESeq2 acceptance

- Obtain the exact original reference FASTA, annotation GTF/GFF3, authoritative release metadata, matching contig IDs, gene model namespace and source rights. Compute *real* SHA256 locally from the actual bytes; no invented checksum.
- Verify actual paired-end FASTQ MD5s from their stored files, biological replicate independence, strandedness and multimapping policy; derive the 24-library raw integer count matrix from a documented quantification pipeline, with QC/alignment evidence.
- Record 2×2×2 design, 3 biological libraries per cell, design matrix and contrasts, multiple-testing policy and full provenance before statistical inference.
- Do not download the 149.54 GB FASTQ archive, use VPS, incur costs or assert any experimental or biological conclusion.

**First next action:** request/locate official, authorized exact v2.0 source-and-annotation manifest without downloading large files; if unavailable, prepare an explicit author decision on switching to v2.1. Keep code and analysis fail-closed until identity and rights are proven.
