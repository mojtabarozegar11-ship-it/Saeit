# ZM-R01 C38 — Two GEO sample-level provenance checks for Milec study GSE294406

**2026-10-27.** Metadata-only audit; no FASTQ, SRA, genome, annotation, or bulk data downloaded. This is not an RNA-seq differential-expression result.

## Source identification and cross-check
- The 2025 Milec et al. article is *Integrative morpho-physiological and transcriptomic insights into wheat responses to combined drought, heat, and elevated CO₂ under future climate conditions*, **Plant Stress**, DOI https://doi.org/10.1016/j.stress.2025.101115. Indexed bibliographic source: https://ouci.dntb.gov.ua/en/works/lDdJdABg/ .
- NCBI GEO series identifier: **GSE294406**, confirmed in indexed original GEO sample records. The following are **two examples, not a complete run manifest**:
  - **GSM8904977**, BioSample **SAMN47891429**, SRA experiment **SRX28347593**: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM8904977
  - **GSM8904978**, BioSample **SAMN47891428**, SRA experiment **SRX28347592**: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM8904978
- GEO sample descriptions explicitly mention **HISAT2**, **RefSeq v2.0, EnsemblPlants**, and differential-expression software **Cuffdiff and DESeq2**, but also describe the supplied expression data as **FPKM** and a table for **three biological replicates per growth regime**. These are **submitter metadata claims**, not independent confirmation of alignment settings, sample independence, raw integer counts, statistical design, or published FDR values.
- The two sample pages say **no supplementary files provided** at the individual GSM level, and raw reads are linked via SRA. This does not prove no processed data exist elsewhere at GSE or publisher level.
- The live GEO HTML currently challenges automated access (CAPTCHA). Indexed source snippets were available; full current page and all sample records were **not** exhaustively inspected.

## Precise verification gap and economical next method
1. Obtain a metadata-only complete GSE294406-to-SRX/SRR run table from official GEO/SRA or ENA, recording GSM, BioSample, SRX, SRR, condition, replicate, layout, fastq_md5, fastq_bytes, and retrieval date. **Do not download any FASTQ** to prepare this manifest.
2. ENA's official filereport API supports result=read_run and fields run_accession,fastq_ftp,fastq_md5,fastq_bytes, per https://github.com/enasequence/read_docs/blob/master/retrieval/programmatic-access/file-reports.rst . API documentation establishes a **possible metadata route**, not successful retrieval of this study's run hashes. Direct metadata API access did not succeed in this run.
3. Keep three checksum states distinct: **(a)** remote provider-listed MD5 (unverified), **(b)** downloaded file's locally computed MD5 (not available), **(c)** matched byte-level MD5 (not available). No claim of true FASTQ MD5 verification is justified by an API listing.
4. Obtain original v2.0 assembly **and matching annotation identity** including exact filename, gene ID mapping, source release and checksum. RefSeq v2.1/IWGSC and NCBI 2025 annotation releases cannot silently replace it.
5. Seek an original integer-count matrix or a small authorized processed-count deposit; FPKM cannot be rounded or converted back into raw count observations. If absent, DESeq2 cannot be independently rerun without reads/alignments and a verified design. **1,167 candidate hypotheses are not 1,167 independently established DEG/FDR findings**.

## Decision
**DATA REBUILD / NO SUBMISSION.** Sample-level accession provenance is more explicit, but complete run metadata, original FASTA/GTF/checksum, library strandedness, multimapping policy, actual FASTQ MD5 and integer counts are still unresolved. No 149.54GB bulk download, VPS, payment, fabricated result or author approval.
