# ZM-R01 C39 — Source-locked 24-library sequencing-file-size balance by factorial treatment

**27 October 2026. Newly executed metadata-only arithmetic on the existing source-locked 24-row GEO↔ENA crosswalk and 24-run paired FASTQ metadata. No new biological results, read-count inference, FASTQ download, VPS, payment or data modification.**

## Inputs and executed computation
- [24 GSM–BioSample–SRR–factor crosswalk](GSE294406_24_GSM_BIOSAMPLE_SRR_VERIFIED_CROSSWALK_2026-10-26.tsv), Git blob `6057129e53563bc5c85b9fbe1cf136c67a84e9c0`.
- [ENA 24-run paired FASTQ file manifest](ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv), Git blob `d9231121dc27bc13999e120349a80af05aad5e15`.
- Executed calculation: parse the two TSVs, join `crosswalk.srr = manifest.run_accession` and require `crosswalk.biosample = manifest.sample_accession`; compute each library's **compressed paired-file bytes** as `fastq1_bytes + fastq2_bytes`; group by the nominal D/H/C treatment bits. Source manifests were fetched directly from the specified research branch. This calculation was run in the research session; no GitHub Actions execution is asserted.
- Checks observed: **24/24 matched**, 24 distinct GSM, BioSample and SRR IDs, **8 cells × 3 libraries**, **48/48 provider-listed MD5 fields syntactically well formed**. Provider MD5 syntax is NOT actual local FASTQ verification.

## New group-level descriptive file-size audit

| D H C | Libraries | Total compressed paired bytes | Mean paired GB/library | Within-cell min–max GB/library |
|---|---:|---:|---:|---:|
| 000 | 3 | 18,134,158,001 | 6.044719 | 5.886297–6.193355 |
| 001 | 3 | 18,723,446,831 | 6.241149 | 5.907094–6.409793 |
| 010 | 3 | 18,391,532,075 | 6.130511 | 5.891357–6.266401 |
| 011 | 3 | 17,918,706,656 | 5.972902 | 5.706071–6.363493 |
| 100 | 3 | 19,069,788,970 | 6.356596 | 5.968920–6.760858 |
| 101 | 3 | 20,048,017,479 | 6.682672 | 6.316945–7.232544 |
| 110 | 3 | 18,704,958,084 | 6.234986 | 6.176118–6.328225 |
| 111 | 3 | 18,550,265,356 | 6.183422 | 5.937540–6.423689 |
| **All** | **24** | **149,540,873,452** | **6.230870** | **5.706071–7.232544** |

**Min:** GSM8904982 / SRR33083336 / DHC=011, 5,706,070,596 bytes. **Max:** GSM8904978 / SRR33083344 / DHC=101, 7,232,544,296 bytes. Maximum/minimum paired compressed bytes ratio **1.2675**. These are **compressed transfer sizes**, NOT read-pair counts, library complexity, mapping rate, expression abundance, treatment effects or evidence of sequencing failure. Differences in compression may reflect read composition or quality and must not be interpreted as biological effects.

## Scientific and operational decision
1. The nominal factorial *metadata* are complete, and all eight D×H×C cells have three labelled RNA libraries. This **does not prove** independent treatment-assignment units or establish a statistically valid 16 residual degrees of freedom; chamber/pot/block allocation remains unknown (see C31/C33).
2. An economical read-depth QC step would require original sequence QC Table S2 or deposited run-level read counts, NOT extrapolation from compressed file sizes. A comparison of raw counts is still blocked by exact RefSeq v2.0 FASTA/annotation/checksum, strandedness, multimapping, library independence and a common pipeline.
3. The complete 24-run crosswalk was **already established in C24 on 26 October**; this cycle did **not** newly resolve those 24 joins. C38's two GSM examples are examples, not evidence that the complete crosswalk regressed or disappeared. Only the **new treatment-stratified file-size calculation and its source-locked audit** count as new work.
4. The **149.540873452 GB** transfer total is confirmed by summing the previously deposited ENA provider byte fields; **not** by downloading 149.54 GB. All 48 true FASTQ file MD5 checks remain unverified locally, apart from the historical single-sample pilot explicitly evidenced in C21. No new MD5 matches claimed.

**Decision: DATA REBUILD / NO SUBMISSION.** No new integer count matrix, DEG/FDR, biological discovery, author approval or journal submission.
