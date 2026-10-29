# ZM-R01 — IWGSC RefSeq v2.0 versus v2.1 reference identity decision, C96
**Owner:** R-01 | **Status:** READY_FOR_REVIEW source-provenance decision; real RNA-seq data processing BLOCKED | **Date:** 2026-10-29

## Authoritative-source reconciliation
1. [IWGSC's official v2.0 announcement](https://www.wheatgenome.org/resources/sequences/iwgsc-refseq-v2.0-now-available-at-urgi) describes the **IWGSC RefSeq v2.0 assembly** released through URGI with registration and a signed data access agreement; it explicitly states the newly released sequence **had not yet been annotated at that announcement date**. This does not prove that no later v2.0 annotation exists.
2. [IWGSC's v2.1 announcement](https://www.wheatgenome.org/resources/annotations/refseq-v2.1-assembly-and-annotation-now-freely-available-at-urgi-and-ncbi) says the **v2.1 assembly and annotation** are freely available at URGI and NCBI under PRJNA669381. [NCBI Annotation Release 100](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/) identifies **GCF_018294505.1 as IWGSC CS RefSeq v2.1**, not v2.0.
3. Therefore a local file labelled `v2.0` must **not** be authenticated by merely finding the NCBI `GCF_018294505.1` v2.1 record. Nor may a v2.1 GTF be silently paired with v2.0 FASTA because both are called 'Chinese Spring'. Sequence, coordinates and annotation version must be proven compatible from the *same declared release*, or separately documented validated liftover.

## Required reference evidence fields (none supplied here)
`assembly_name`, `assembly_release`, `assembly_source_url`, `assembly_accession_if_applicable`, `annotation_release`, `annotation_source_url`, `FASTA_original_SHA256`, `GTF_original_SHA256`, `license_or_data_access_terms`, `sequence_header_and_coordinate_crosswalk`, `gene_id_namespace`, `acquisition_date_utc`. A GCF_ identifier is **not mandatory for an original URGI v2.0 deposit** merely because NCBI hosts v2.1. The existing `zm_r01_preflight.py` is a conservative NCBI-GCF-only file gate and is not sufficient to adjudicate URGI v2.0 source rights or provenance.

## Scientific and operational decision
- **BLOCKED:** exact v2.0 FASTA/GTF original bytes and SHA, access terms, FASTQ MD5s, aligner multimapping treatment, 24-library biological independence and raw integer counts. The preflight's successful synthetic tests are not RNA-seq validation.
- **Prohibited:** relabeling GCF_018294505.1 as v2.0, mixing annotation releases without verified liftover, using FPKM as DESeq2 raw counts, or calling 1,167 hypotheses significant DEGs/FDR.
- **No download:** no 149.54-GB batch, no VPS disk writes, no cost, no invented biological result.

**Next exact step:** obtain only the official URGI v2.0 assembly/annotation *manifest and license metadata* through authorized access, confirm whether a matching annotation release exists, and record exact source identifiers **before** considering any file acquisition.
