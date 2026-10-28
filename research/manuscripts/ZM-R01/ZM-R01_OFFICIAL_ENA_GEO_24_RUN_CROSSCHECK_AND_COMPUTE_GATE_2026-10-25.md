# ZM-R01: actual independent ENA-to-GEO sample/run provenance audit

**Verified 25 October 2026.** This is a real metadata audit against a newly fetched official ENA Portal API response, NOT a FASTQ download, mapping/alignment, integer count reconstruction, DESeq2 analysis, or evidence of a novel biological finding.

## Official source and new machine-readable evidence
- [ENA PRJNA1249400 live file report](https://www.ebi.ac.uk/ena/portal/api/filereport?accession=PRJNA1249400&result=read_run&fields=run_accession,sample_accession,fastq_ftp,fastq_bytes,fastq_md5&format=json), response independently retrieved on 2026-10-25.
- [Official 24-run, 48-file URL/size/MD5 snapshot](ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv), newly committed to this research branch.
- [Earlier GEO sample-title and GSM/SRR/BioSample mapping](GSE294406_VERIFIED_24_GSM_SRR_BIOSAMPLE_ENA_FASTQ_MANIFEST_2026-10-25.csv), used as an **independent previously recorded** cross-check.
- [Original GEO study](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406), [Milec et al. 2025](https://doi.org/10.1016/j.stress.2025.101115).

## Actual validation performed
A fresh programmatic 24-to-24 join on **SRR run accession** was completed. For each row, the independently obtained ENA BioSample accession, both paired FASTQ HTTPS URLs, and both FASTQ compressed byte sizes were compared against the earlier GEO-derived manifest.

| Check | Actual result |
|---|---|
| Unique original GEO GSM↔SRR rows | 24 |
| Unique ENA PRJNA1249400 SRR rows | 24 |
| SRR run joins matched | **24/24** |
| BioSample accession mismatches | **0** |
| Paired FASTQ URL mismatches | **0** |
| R1/R2 compressed byte-size mismatches | **0** |
| ENA files with valid-format 32-character MD5 strings | **48/48** |
| Factorial cells D,H,C = 000,001,010,011,100,101,110,111 | **3 distinct GEO biological replicate titles per cell** |
| Total official compressed paired FASTQ size | **149,540,873,452 bytes = 149.540873452 decimal GB ≈ 139.27 GiB** |

**Integrity boundary:** presence of an ENA MD5 string is not the same as locally checking a downloaded file. No files have been downloaded, so **zero downloaded-file MD5 checksums have been verified**. The GEO titles establish factorial labels, not biological independence or sequencing quality.

## Computational feasibility gate
- A single uncompressed pair can require far more scratch space than its compressed ENA size. A full 149.54-GB compressed transfer plus decompression, wheat reference genome/index, alignment intermediates and gene-level count outputs exceeds the available ~35 GB VPS free space reported previously; that prior free-space figure must be remeasured before any actual job.
- Hosted CI runners have finite disk/RAM and are not a substitute for a suitable wheat RNA-seq processing environment. Do not attempt to retrieve all 48 files into a standard CI workspace or live cPanel production. Processing per-run sequentially with bounded scratch space and immediate disposal is a *candidate*, subject to reference-index size, compute memory and resource quota checks; no viability has yet been demonstrated.
- Before heavy compute: verify an authorized zero-cost resource with adequate CPU, memory, reference annotation, storage and transfer quota; fix wheat genome build, gene models and featureCounts/Salmon/STAR/other count strategy; record version and checksums. Download, verify MD5, QC and quantify each library only when those constraints are met.
- If the original author supplies **unnormalized integer gene counts**, verify column-to-GSM mapping, genome/annotation and feature-counting provenance before using the committed `analysis/full_factorial_integer_counts.R`. FPKM, TPM, rounded FPKM and simulated counts are prohibited inputs to DESeq2.

## Scientific novelty and next decision
The source study already analyzes combined drought/heat/CO₂ stress; a three-way coefficient `D:H:C` alone is not proof of a new biological finding. This stage **closes the 24-sample mapping and file-identity provenance gate**, but does **not** close raw-count acquisition, differential expression, FDR, biological validation, novelty or manuscript submission. All remain blocked or pending until authentic raw counts and computation are available.
