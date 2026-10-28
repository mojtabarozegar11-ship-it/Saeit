# ZM-R01 C35 — EnsemblPlants 'refseqv2' page label does not identify assembly v2.0

**27 October 2026. New primary-source metadata reconciliation; no sequence download, read counts, checksum, DEG or FDR.**

## Direct source evidence

1. The official Ensembl Plants archive page at https://jun2026-plants.ensembl.org/Triticum_aestivum_refseqv2/Info/Annotation has the URL/species label **Triticum_aestivum_refseqv2**. However, the actual **Assembly** field reads **IWGSC_RefSeq_v2.1**, **INSDC accession GCA_018294505.1** (Jul 2022), and the displayed **database version is 116.1**. The visible gene count is 106,876 coding genes. These are page metadata, not independently downloaded files.
2. The IWGSC official v2.0 announcement https://www.wheatgenome.org/resources/sequences/iwgsc-refseq-v2.0-now-available-at-urgi says the initial v2.0 assembly was released without annotation and access required registration and a data agreement. This is a different source/version lineage from the v2.1 metadata above.
3. IWGSC official v2.1 announcement https://www.wheatgenome.org/resources/annotations/refseq-v2.1-assembly-and-annotation-now-freely-available-at-urgi-and-ncbi describes a freely accessible **v2.1** assembly and annotation. This availability does not retrospectively identify the exact v2.0 reference used in Milec et al. (2025).

## Newly established provenance risk

A file selected from a website path containing **'refseqv2'** may in fact refer to **v2.1**, not v2.0. Therefore **do not substitute** Ensembl Plants 'refseqv2' downloadable FASTA/GFF3 for the paper's stated **RefSeq v2.0** without confirming assembly metadata, source version, gene model and hashes. The URL slug alone is not an assembly accession. The presence of v2.1 metadata does **not** prove the original authors used a mismatched reference; their exact files remain unknown.

## Exact validation required

Record the actual FASTA assembly accession, release, contig names and checksum; annotation file and release with coordinate concordance; mapping parameters, unique/multimapping treatment, strandedness, and experimental-unit allocation. If using an alternative v2.1 reanalysis, label it a **different reference sensitivity analysis**, not an exact replication of a claimed v2.0 pipeline. Without genuine integer counts and independent experimental design, no DESeq2/FDR inference is allowed.

**Status:** reference identity clarified at metadata level, **exact FASTA/GTF pair unresolved**; no bulk 149.54 GB download, VPS, payment, fabricated DEG or publication. **DATA REBUILD / NO SUBMISSION**.