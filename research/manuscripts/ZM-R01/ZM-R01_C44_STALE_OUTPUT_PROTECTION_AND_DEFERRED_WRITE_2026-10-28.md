# ZM-R01 C44 — Prevent stale DESeq2 output mixing and defer filesystem writes

**28 October 2026 | Internal code-safety correction | DATA REBUILD / NO SUBMISSION**

## Actual change

The research-branch script `analysis/full_factorial_integer_counts.R` was inspected and amended. Previously it called `dir.create(outdir)` after some provenance gates but **before** validating the factorial labels, count-matrix structure and DESeq2 fit. It could therefore create an output folder even when subsequent input checks or modeling failed. A nonempty pre-existing output folder could also be reused, allowing outputs from different attempted analyses to be mixed.

The new code:
1. **Refuses a nonempty output directory** with an explicit stop, preventing silent overwrites and mixed old/new result files.
2. **Does not create an output directory until after** all current input validation and successful `DESeq()` and `results()` execution.
3. Retains the earlier strict evidence gates for 24 independent treatment-assignment units, integer counts, reference/annotation provenance, FASTQ MD5 evidence and multimapping policy.

This is a correctness and reproducibility safeguard; it does not validate the truth of metadata assertions or experimental-unit independence.

## Verification and limits

The exact updated R file was read back from the target GitHub branch, and source-order checks confirmed that `dir.create(outdir)` occurs after `res <- results(dds, ...)`. **Rscript is not installed in the current analysis environment**, so no executable R/DESeq2 test, package loading or biological analysis is claimed. The guard should be subjected to a controlled negative-path R test on a permitted CI runner with non-biological fixtures before relying on it operationally; no fake biological data or results should be reported as scientific evidence.

Remaining gates: exact RefSeq v2.0 FASTA/GTF pair and hashes; 24 byte-verified FASTQ MD5s; defensible multimapping; independent experimental units; true 24-column integer counts; correctly justified statistical model. The preserved one-sample pilot does not satisfy these.

**Disposition:** code hardened; no new DEG, FDR, biological result, human approval, VPS use or submission. NO SUBMISSION.
