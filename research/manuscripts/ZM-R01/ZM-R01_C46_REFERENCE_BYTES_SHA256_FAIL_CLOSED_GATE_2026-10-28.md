# ZM-R01 C46 — Reference FASTA/GTF byte-integrity gate (implementation correction)

**28 October 2026 | Internal computational-method correction | DATA REBUILD / NO SUBMISSION**

## Confirmed gap in the previous code
The previous `analysis/full_factorial_integer_counts.R` verified SHA256 of the counts TSV and independent-unit CSV against declared provenance values, but accepted `reference_fasta_sha256` and `annotation_gtf_sha256` as **syntactically valid declarations without hashing actual reference/annotation file bytes**. This is insufficient to claim independently verified reference integrity.

## Implemented correction
The R entrypoint now requires **seven positional arguments**:
`counts.tsv manifest.csv independent_units.csv provenance.json output_dir refseq_v2.fasta matching_annotation.gtf`.
The reference FASTA and annotation GTF must both exist locally. Before DESeq2 fitting or output creation, their actual file bytes are hashed using `digest::digest(..., algo="sha256", file=TRUE, serialize=FALSE)` and compared to the corresponding provenance values. A missing file or digest mismatch stops the pipeline with `NO DESeq2`. The output provenance label has been changed from "declared" to "local bytes verified", but **only for a future run that passes the new gate**.

## Scientific and operational limits
- No FASTA or GTF was downloaded or read during this cycle, no 149.54 GB FASTQ download occurred, and no VPS or paid compute was used.
- No R/DESeq2 execution with valid primary inputs was performed. This is a **code-path correction**, not a validated successful model run.
- Byte-hash equality alone does not establish the correct RefSeq v2.0 assembly accession, GTF/FASTA semantic compatibility, gene-ID universe, licensing, read strandedness or multimapping policy. Those remain separate scientific gates.
- The JSON provenance flags are **self-reported** unless corroborated by independent primary evidence; FASTQ MD5 values for all 24 libraries are not verified from local FASTQ bytes. No full 24-sample integer-count matrix exists.
- The single-sample pilot evidence is not a factorial experiment. FPKM and 1,167 hypotheses are not DEG/FDR results.
- The full experimental-unit/chamber independence and any clustering must be resolved before inferential analysis; a successful SHA check cannot authorize publication.

**Decision:** retain DATA REBUILD / NO SUBMISSION. Author approval, human scientific scrutiny, original data and version rights remain mandatory.
