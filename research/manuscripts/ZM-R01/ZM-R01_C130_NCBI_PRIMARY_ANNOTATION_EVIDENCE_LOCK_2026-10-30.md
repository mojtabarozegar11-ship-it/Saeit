# ZM-R01 | C130 NCBI primary-source annotation release lock and data gate

Date checked: 2026-10-30. Owner: R-01. **Reference metadata only; no experimental RNA-seq inference.**

## Authenticated source and exact scope

Primary NCBI report: https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/

| Field | Source-reported value | Required downstream interpretation |
|---|---|---|
| Organism | *Triticum aestivum* | Bread wheat, not another cereal |
| Reference assembly | IWGSC CS RefSeq v2.1, `GCF_018294505.1` | FASTA and feature annotation must use exactly this assembly accession |
| NCBI annotation | `GCF_018294505.1-RS_2025_04` | An annotation update, not a new genome assembly |
| Entrez transcript/protein query date | 2025-04-16 | Evidence vintage; not experimental sample collection date |
| Annotation public submission | 2025-04-18 | Distinct from assembly date |
| Pipeline | NCBI Eukaryotic Genome Annotation Pipeline 10.3 | Automated annotation; not independently measured gene expression |
| Assembly content | 22 assembled chromosomes **plus unplaced scaffolds** | Do not assume exactly 22 sequence records in FASTA |
| Gene/pseudogene features | 155,467 | Includes pseudogenes and noncoding; not 155,467 protein-coding genes |
| Protein-coding genes | 103,793 | Source's feature category, not a differential-expression result |
| mRNAs | 142,414 | Transcript count, not independent genes |
| CDS features | 142,450 | Not an experimental transcript read count |

The NCBI report explicitly says the 2025 update retained prior predicted RefSeq models that were still current and **did not recalculate those models**. Thus a change in release metadata cannot be interpreted as new biological evidence from the planned ZM experiment.

## Fail-closed accession and sample gate

Before alignment, store both the downloaded reference FASTA and matching GFF/GTF with source URL, byte count, SHA-256, retrieval time and assembly identifier. Verify contig/sequence IDs in GFF/GTF occur in FASTA, and lock the annotation release in the analysis manifest. Do not mix release 100 features with the 2025 update without an explicit reproducible remapping.

For the proposed 24-library factorial experiment, require an authenticated sample manifest with 24 distinct sample IDs, biological treatment, replicate, experimental provenance, FASTQ paths/links, read layout and cryptographic checksums. Public NCBI annotation support evidence is **not** a substitute for experimental reads. Until these inputs exist, differential expression, statistical significance, gene regulation and treatment effects are **BLOCKED**.

## Decision

**REFERENCE_METADATA_VERIFIED / EXPERIMENT_BLOCKED**. This file is a reusable version-locked reference specification for a qualified bioinformatics reviewer, not a completed RNA-seq analysis. Next: receive legitimate 24-sample FASTQ provenance and archive the exact reference files, then perform read integrity/metadata validation offline.
