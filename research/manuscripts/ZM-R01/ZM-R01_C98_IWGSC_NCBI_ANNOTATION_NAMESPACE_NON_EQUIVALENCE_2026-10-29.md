# ZM-R01 — source-verified IWGSC vs NCBI annotation non-equivalence (C98)
**Owner:** R-01 | **Date:** 2026-10-29 | **Document:** usable reference-identity decision; RNA-seq reconstruction remains BLOCKED.

## Primary-source comparison
| Component | IWGSC release | NCBI release | Interpretation |
|---|---|---|---|
| Genome assembly | IWGSC CS RefSeq **v2.1**, published via URGI/NCBI | NCBI Annotation Release 100 uses **GCF_018294505.1**, explicitly labelled IWGSC CS RefSeq v2.1 | Same named assembly accession; not proof of identical downloaded FASTA bytes |
| Gene annotation | **IWGSC Annotation v2.1**; consortium reports **266,753 genes**, comprising **106,913 high-confidence** and **159,840 low-confidence** gene models | NCBI Eukaryotic Annotation Release **100** reports **155,463 genes and pseudogenes**, of which **103,787 protein-coding** | Different annotation products and inclusion definitions. Neither gene total is a valid substitute for the other, even on a related assembly |
| Gene identifiers | IWGSC annotation release and HC/LC identifiers | NCBI RefSeq GeneID, NM/XM/NR/XR accessions | A gene-ID namespace crosswalk is required before combining or comparing counts |
| v2.0 release | Separate URGI distribution/access conditions and historical annotation status | GCF_018294505.1 is **v2.1**, not v2.0 | Cannot relabel NCBI v2.1 as IWGSC v2.0 |

**Primary sources:**
- [IWGSC release of RefSeq v2.1 and Annotation v2.1](https://www.wheatgenome.org/resources/annotations/refseq-v2.1-assembly-and-annotation-now-freely-available-at-urgi-and-ncbi), including 266,753 = 106,913 + 159,840 gene models.
- [NCBI Triticum aestivum Annotation Release 100](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/), including assembly GCF_018294505.1 and 155,463 genes/pseudogenes.
- [Prior R-01 v2.0/v2.1 source decision](ZM-R01_C96_IWGSC_V20_V21_ASSEMBLY_ANNOTATION_IDENTITY_GATE_2026-10-29.md).

## Executable admission decision for future raw-count analysis
1. Require an **explicit pair** of FASTA release and annotation release, source URLs, original SHA-256 checksums, accession/contig dictionary and terms; do not treat the assembly accession alone as a gene annotation accession.
2. Require a gene namespace tag in each count matrix: `IWGSC_v2.1_HC`, `IWGSC_v2.1_HC_LC`, `NCBI_AR100`, or separately verified version; the first two are **not** equivalent to the third.
3. Reject silent joins between IWGSC HC/LC and NCBI GeneIDs. Only allow a versioned mapping with unique mapping multiplicities, ambiguous mappings retained as unresolved, and feature-type definitions.
4. Require the 24 original independent sample accessions, FASTQ checksums, alignment method and raw integer gene counts; a reference gene total is **not** a count of differentially expressed genes.
5. If any of these are missing, `BLOCKED_REFERENCE_OR_SAMPLE_PROVENANCE`; do not report FDR, 1,167 significant genes, or a completed factorial analysis.

**Current result:** This is a scientifically actionable reference/annotation selection and validation rule. No FASTA/GTF/FASTQ downloaded, no VPS disk used, no raw counts, DEG or FDR computed. **READY_FOR_REVIEW for reference decision; BLOCKED for biological analysis.**

**Next exact step:** select the intended original reference/annotation release from the project's actual methods or deposit; record the paired file manifest and checksums before any alignment or featureCounts/DESeq2 work.
