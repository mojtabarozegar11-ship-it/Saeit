# ZM-R01 C47 — Replace self-declared FASTQ MD5 flag with 48-file byte-level fail-closed verification

**28 October 2026 | Code-level scientific integrity correction | DATA REBUILD / NO SUBMISSION**

## Original defect
The previous `analysis/full_factorial_integer_counts.R` required a JSON Boolean `all_24_fastq_md5_recomputed_from_bytes = true` but did not itself inspect any actual FASTQ bytes. A Boolean in an untrusted provenance JSON is not independent evidence that 48 paired FASTQ files were checked against ENA-reported MD5s. This left a material path for unjustified provenance assertions even after the FASTA/GTF SHA256 checks added in C46.

## Actual source change
The R entry point now requires **eight** explicit arguments, adding `48_fastq_manifest.tsv`. The new manifest must have exactly 48 rows and four columns: `SRR`, `read` (R1/R2), `fastq_path` (local, already-authorized file path), and `ena_md5` (32 hex digits). It must match all 24 distinct SRRs in the GEO sample manifest, exactly one R1 and R2 per SRR, with no repeated file paths. Its SHA256 must match the `fastq_manifest_sha256` field in the provenance JSON. The script uses `tools::md5sum` on **all 48 actual local FASTQ files** and stops if any observed byte digest differs from the corresponding manifest MD5. This is performed only after the existing cheap provenance and FASTA/GTF gates and before DESeq2 or output directory creation.

## Execution and scientific limits
- **No FASTQ was downloaded, read or hashed in this cycle.** In particular, the prohibited 149.54 GB bulk acquisition and VPS were not used. This is a **code correction**, not a completed 48-file MD5 validation.
- The new R script has **not been run** with valid 24-library data. The code requires the files to already exist in a separately authorized future environment; otherwise it fails closed.
- A matching local digest does not authenticate the original ENA metadata, sequencing experiment, biological independence, reference/annotation lineage, multimapping policy, or gene-count matrix.
- A separate source-level review must verify the 48 expected MD5s from ENA; a user-edited manifest could still contain fabricated digests of unrelated bytes. Therefore provenance truth is not automatically established by matching local hashes.
- The existing single-library pilot count cannot be represented as a 24-library matrix. No DEG, DESeq2 result or FDR is reported.

## Required remaining evidence
Exact RefSeq v2.0 FASTA/GTF release and checksum, documented licensing and matching gene universe; 24 independent experimental units/chamber allocation; authenticated 48 ENA MD5s and local bytes; justified multimapping and strandedness; all 24 unnormalized integer gene-count columns; verified count provenance and author scientific review.

**Decision:** code is more fail-closed; ZM remains DATA REBUILD / NO SUBMISSION.
