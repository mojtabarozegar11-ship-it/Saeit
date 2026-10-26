# ZM-R01 C27 — IWGSC v2.0 original-reference access and scientific-method decision

**Date:** 26 October 2026. **Decision:** original-study replication **BLOCKED** at exact reference/annotation and access-rights gates; no paid compute, FASTQ bulk download or DESeq2 result authorized. This is a research preproduction decision, not evidence of a completed analysis.

## New primary-source access finding

The original Milec et al. 2025 Methods (see C23/C26) name **HISAT2 with IWGSC RefSeq v2.0 (EnsemblPlants)**. The **official IWGSC v2.0 release announcement**, https://www.wheatgenome.org/resources/sequences/iwgsc-refseq-v2.0-now-available-at-urgi , explicitly states:
1. The v2.0 assembly was released through URGI under a **registration and IWGSC General Data Access Agreement** requirement; the announcement points to a login-gated `/IWGSC_RefSeq_Assemblies/v2.0/` repository.
2. **At that original release**, the v2.0 assembly was **not yet annotated**; annotation v2.0 was planned, not shown in this announcement to be available with a versioned checksum. This historical statement does **not** prove that no v2.0 annotation was ever later released.
3. The IWGSC's separate 2021 announcement, https://internet6-national-wheatgenome.custom.hub.inrae.fr/news/refseq-v2.1-assembly-and-annotation-now-freely-available-at-urgi-and-ncbi , identifies **v2.1 assembly plus annotation v2.1** as publicly available without restriction under BioProject **PRJNA669381**. Ensembl's v2.1 record explicitly identifies **GCA_018294505.1**; NCBI RefSeq **GCF_018294505.1**. This is **not proof** that v2.1 was used by Milec.
4. The official IWGSC annotation resources page, https://www.wheatgenome.org/resources/annotations , lists publicly available v2.1, v1.1 and v1.0 resources; it does **not** independently establish the exact v2.0 gene models, gene-ID namespace, checksum or a publicly downloadable matching GTF.

**Therefore:** zero monetary price cannot be conflated with unrestricted access or permission to accept an agreement. We have **not** registered, accepted legal terms, obtained v2.0 credentials, fetched a v2.0 genome or annotation, or measured the peak memory/disk for a genome index. No GCA/GCF accession for the exact v2.0 reference was verified.

## Scientifically legitimate choices (not interchangeable)

| Route | Prerequisites | Claim permitted | Current disposition |
|---|---|---|---|
| **A. Original-method replication** (preferred) | Authenticated, properly licensed v2.0 FASTA; *matching* v2.0 annotation/GTF and gene IDs; source checksums; original paired-read strandedness/counting policy | Qualified attempt to reproduce original reference-based results | **BLOCKED**; no access agreement accepted and no source-matched pair verified |
| **B. Transparent new analysis with v2.1** | Open v2.1 GCA/GCF_018294505.1 FASTA and annotation v2.1; exact SHA256; consistent gene IDs; declared counting policy; resources and 48 actual mate MD5 | **Independent reanalysis with a different reference**, not exact reproduction of Milec v2.0 | **CONDITIONALLY FEASIBLE**, not executed or selected as equivalent |
| **C. Continue original Bowtie2 transcriptome pilot** | Would still have unresolved multi-mapping and wrong reference/quantification strategy | No publication-grade unique gene-count claim | **REJECTED** by C22 |

## Concrete next production gate

- Determine whether an openly available and legally usable **v2.0 FASTA plus matching GTF** exists, and whether its sequence/gene identifiers match the original paper. Otherwise do not claim exact replication.
- If v2.0 requires an access agreement, flag **owner/legal approval needed**; do not click acceptance, use another person's credentials or bypass restrictions.
- If v2.1 is deliberately chosen, amend the study question and Methods to **independent reanalysis using v2.1**, explicitly distinguish gene-model changes from original results, and never pool with the Bowtie2 pilot.
- For either route, preflight genome-index RAM/disk and free runner scratch reserve, download one paired FASTQ library only after exact mate checksum and license gates, then a consistent 24-sample integer gene-count matrix before DESeq2 `~D*H*C` and FDR.

**Impact:** a previously vague reference-access blocker is now a concrete **rights + reference-version + annotation** decision. No gene counts, DEG, FDR, mechanism or publication-ready result has been produced by this memo.
