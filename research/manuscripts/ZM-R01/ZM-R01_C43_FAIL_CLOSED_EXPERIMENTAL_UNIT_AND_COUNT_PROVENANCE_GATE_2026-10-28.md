# ZM-R01 C43 — Fail-closed scientific release gate for the 24-library DESeq2 workflow

**28 October 2026 | Research-branch code correction, NOT an RNA-seq result | DATA REBUILD / NO SUBMISSION**

## Actual defect and correction

The existing `analysis/full_factorial_integer_counts.R` correctly checked that a supplied 24-column table contained nonnegative integers, had the eight nominal D×H×C groups, and that the library-level model matrix had rank eight. **It did not require primary evidence of 24 independent treatment-assignment units, a validated reference/annotation pair, byte-recomputed FASTQ MD5s, or a documented multimapping policy before fitting DESeq2.** This left a path to produce p-values from a superficially well-formed but scientifically unverified table.

The source file has now been changed **in the research branch only** to require **five explicit arguments**: `counts.tsv manifest.csv independent_units.csv provenance.json output_dir`. The script fails before creating an output directory if any evidence file is missing.

The independent-units CSV must have 24 distinct GSM records and these fields:
- `GSM`, `assignment_unit_id`, `chamber_id`, `assignment_unit_type`, `source_uri`, `verification_status`.
- Each treatment-assignment unit and chamber must be unique across all 24 libraries for this **unblocked** model; `assignment_unit_type=independently_assigned_chamber`, `verification_status=SOURCE_DOCUMENT_VERIFIED`, and source URLs are required. Shared-chamber or pot-within-chamber designs are **not** rejected as invalid experiments; rather, this *particular unblocked analysis* is not appropriate and a separate cluster-aware or otherwise justified design is required.

The JSON must explicitly attest to `raw_unnormalized_gene_counts`, `all_24_fastq_md5_recomputed_from_bytes`, `refseq_v2_assembly_fasta_verified`, `matching_annotation_gtf_verified`, `multimapping_policy_independently_validated`, `gene_universe_consistent`, and `independent_units_evidence_verified`, all strictly boolean true. It must supply valid 64-hex SHA256 strings for `counts_sha256`, `unit_evidence_sha256`, `reference_fasta_sha256`, and `annotation_gtf_sha256`. The script recomputes SHA256 of the supplied counts and independent-unit CSV before proceeding.

**Critical limitation:** metadata flags and source URLs are not independent proof of biological independence or reference identity. They are machine-checkable prerequisites only; the actual source records, allocation design, reference hashes and original FASTQ bytes still require real verification. No fictional evidence CSV, approval, checksum or counts has been created. This code was modified and re-fetched from GitHub, but **R execution has not been independently demonstrated in this cycle**.

## Current study status

The source GEO series has 24 nominal libraries in eight D/H/C cells and three labelled biological replicates per cell, but actual independent chamber assignment remains **unknown**. The preserved one-sample transcriptome-derived sparse table has 58,039 nonzero gene rows and 14,357,584 assigned counts; it is not a validated unique-mapping genome-based 24-sample count matrix. The original Bowtie2 categories refute the stronger unique-concordant-pair claim. The exact RefSeq v2.0 FASTA/GTF pair, source-level multimapping policy, and locally byte-recomputed MD5 for all 24 FASTQ pairs remain unresolved. FPKM and the 1,167 exploratory hypotheses must never be reported as DEGs or FDR findings.

**Release decision:** the new preflight gate deliberately blocks invalid premature DESeq2 output. It does **not** unblock a publication-grade expression analysis. No VPS, bulk FASTQ transfer, paid service, live website, human authorship claim or journal submission was involved.
