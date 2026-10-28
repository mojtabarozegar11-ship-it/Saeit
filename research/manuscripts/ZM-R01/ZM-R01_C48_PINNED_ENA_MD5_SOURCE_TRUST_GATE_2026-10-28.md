# ZM-R01 C48 — Authenticate submitted 48 FASTQ MD5 entries against pinned repository ENA source

**2026-10-28 | Code-level scientific provenance correction | DATA REBUILD / NO SUBMISSION**

## Defect remaining after C47
The C47 script recomputed MD5 from 48 local FASTQ files and compared each result to an MD5 in a *caller-supplied* 48-row manifest. This can verify byte-to-manifest consistency but is vulnerable to a self-consistent, untrusted manifest containing arbitrary file hashes. The C47 note explicitly identified this unresolved ENA metadata authenticity gap.

## Actual C48 correction
The R script `analysis/full_factorial_integer_counts.R` now locates the repository's existing ENA source table `ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv` relative to its own script path. Before any costly FASTQ byte hashing it:
1. Requires the local source file and limits its expected size.
2. Computes the actual **Git-style SHA1 blob digest** from `"blob " + byte_length + NUL + file_bytes`, and compares it with the source blob SHA **`d9231121dc27bc13999e120349a80af05aad5e15`**, independently obtained from the existing GitHub branch.
3. Parses the pinned 24-row table; checks 24 distinct run accessions and exact equality to the 24 expected SRRs.
4. Expands the source `fastq1_md5` and `fastq2_md5` into 48 unique `SRR:R1` and `SRR:R2` keys, requires 32-hex MD5s, and checks *every* supplied manifest MD5 against the pinned source by key (order-independent).
5. Only after the source-MD5 crosswalk passes does the C47 `tools::md5sum` scan of the 48 locally available FASTQ files begin.

## Evidence and limitations
- The GitHub file content and blob SHA were retrieved directly from the named branch before modification. The source table is a **historical repository snapshot**, not a fresh ENA API response; a matching Git blob does not independently prove current ENA truth or laboratory sample identity.
- This run **did not** download or hash any FASTQ, reference FASTA or GTF; it did not use VPS or incur a paid service. The 149.54 GB bulk acquisition remains forbidden.
- The R script was **not executed** because no R runtime with DESeq2 and the authorized 48 FASTQ files was available in this environment. This is a source-level change with readback, **not** a passed runtime test or validated DEG analysis.
- Original reference release identity, gene-universe compatibility, biological independence, multimapping and strandedness, 24-library integer counts, author decisions and journal submission remain unresolved.
- The pinned SHA1 is a Git content-addressing check, not a claim that SHA1 is a modern collision-resistant scientific checksum. The actual 48 FASTQ contents still require MD5 byte comparison against independently authenticated ENA records; source authentication should be reconfirmed before any future authorized production run.

**Decision:** improved fail-closed source-to-local MD5 linkage, but **DATA REBUILD / NO SUBMISSION**. No FPKM or 1,167 exploratory hypotheses are reported as DEGs or FDR-significant results.
