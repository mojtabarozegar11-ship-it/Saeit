# ZM-R01 C25 — source-joined 24-library capacity decision, 26 October 2026

**Scope:** independent new read-only reconciliation of the already source-verified GEO/ENA metadata with official GitHub standard-runner limits. This is a capacity decision, **not** RNA-seq processing, reference validation, DESeq2, FDR, or a publication claim.

## Verified inputs

- ENA source manifest: `ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv` (Git blob `d9231121dc27bc13999e120349a80af05aad5e15`).
- Independently verified GEO ↔ BioSample ↔ SRR crosswalk: `GSE294406_24_GSM_BIOSAMPLE_SRR_VERIFIED_CROSSWALK_2026-10-26.tsv` (Git blob `6057129e53563bc5c85b9fbe1cf136c67a84e9c0`).
- Joined **24/24** runs by SRR and verified the BioSample matches for each. Each of the eight 2×2×2 conditions has **3** biological libraries.
- **Total compressed paired FASTQ bytes:** `149540873452` = **149.540873452 decimal GB** = **139.270791 GiB**, 48 files. This reconciles exactly with C19.
- **Largest compressed pair:** GSM8904978 / SRR33083344 / D=1 H=0 C=1, **7,232,544,296 bytes** = **6.735832 GiB**.
- **Next largest:** GSM8904966 / SRR33083352 / D=1 H=0 C=0, **6,760,858,399 bytes**.
- **Smallest compressed pair:** **5,706,070,596 bytes**.
- Total compressed bytes by factorial condition: 000=18,134,158,001; 001=18,723,446,831; 010=18,391,532,075; 011=17,918,706,656; 100=19,069,788,970; 101=20,048,017,479; 110=18,704,958,084; 111=18,550,265,356.

## Source-backed capacity constraint

Official GitHub documentation, checked 26 October 2026:
- Standard `ubuntu-latest` runner for **public** repositories: **4 vCPU, 16 GB RAM, 14 GB SSD**. Source: https://docs.github.com/en/actions/reference/runners/github-hosted-runners .
- Standard GitHub-hosted runners are free for public repositories, subject to platform limits and acceptable-use requirements; larger runners are not automatically free. Source: https://docs.github.com/en/actions/concepts/billing-and-usage .
- The Saeit repository was confirmed **public** via the connected GitHub repository API. This does not guarantee available runner concurrency, throughput, or successful large-data execution.

**Go/no-go decision:** **NO-GO for downloading all 48 FASTQ files onto one standard runner or the nearly full VPS.** Even the largest *compressed* single pair consumes about half of the runner's nominal disk before reference index, temporary extraction, alignments, BAM, sort buffers and operating-system use. Thus a simple per-sample `download -> decompress -> align -> BAM` pipeline cannot be declared feasible on 14 GB without a measured preflight and streaming design. There is no scientific justification for a paid runner or a VPS transfer at this stage.

## Required non-destructive next execution

1. **Reference first:** verify from Milec original Methods and primary FASTA/annotation records whether its `RefSeq v2.0 (EnsemblPlants)` means exactly the same assembly/transcript/GTF release as the selected download. Record FASTA/GTF source SHA256 and gene-ID namespace. **Do not equate v1.0, v2.0 and v2.1.**
2. **Paired-read policy:** decide gene-level counting from paired-end fragments, treatment of multi-locus and multi-gene ambiguity, strandedness, secondary/supplementary alignments, and quality gates. The original MAPQ>=20 pilot cannot be labeled strict unique.
3. **Runner preflight:** on an actual standard runner, record `df -B1`, `free -b`, CPU, temporary-path capacity, index size and the worst-case per-sample streaming/temporary disk requirement. Require a **>=2 GiB reserve** and fail closed if projected peak exceeds actual free bytes; 14 GB is nominal, not available scratch.
4. **Single valid source-matched library:** stream each mate with incremental MD5 validation, do not store all reads simultaneously, and preserve only small QC and integer gene-count outputs. A checksum must be computed over **actual downloaded bytes**, not inferred from the ENA metadata string. Only accept counts after a method-specific independent multimapping audit.
5. **24 samples after gate:** use bounded concurrency and ephemeral per-run storage; never upload raw FASTQ/BAM as artifacts. For each library, record reference/index checksum, FASTQ MD5, read pairs, mapped/ambiguous/unassigned fragment categories, gene-count sum and source identity. A 24-column same-gene-ID nonnegative integer matrix is required before `DESeq2 ~ D*H*C` and adjusted FDR.
6. **Science gate:** an estimable 3-way coefficient is not evidence of a novel biological mechanism; compare the final estimand and findings with Milec 2025 and other primary studies.

**Verified this cycle:** manifest-derived capacity limits and no-cost architecture constraints. **Not done:** reference accession reconciliation, 48 FASTQ bytewise MD5 checks, 24-library counts, differential expression, publication or site changes.
