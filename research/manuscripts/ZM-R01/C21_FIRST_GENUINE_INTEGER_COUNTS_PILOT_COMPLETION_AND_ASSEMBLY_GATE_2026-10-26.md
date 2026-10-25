# ZM-R01 C21 — first genuine paired-read count pilot completed; reference gate remains CLOSED

**Observed and independently queried:** 2026-10-26. **Data stage advanced:** source download and single-sample counting completed; **24-library matrix NOT completed**.

## Verified run and original artifact

- Original GitHub Actions [run 40222743342](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40222743342) / job **121257644350** has **completed/success** status for all substantive steps, including the previously in-progress transcriptome alignment.
- Original [artifact 12618285422](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40222743342/artifacts/12618285422), named `ZM-R01-SRR33083355-genuine-integer-gene-count-pilot`, was actually uploaded **2026-10-25 23:10:32 UTC**, size **252,151 bytes**, GitHub artifact digest **SHA256 0d2beb292eb5ffbed24e30237483513c3ac3cd1e188d2248098df0a5341f30a8**, expiry **2026-11-01 23:10 UTC** unless preserved elsewhere.
- Original source: **SRR33083355 / GSM8904963**, BioProject PRJNA1249400. Official ENA mate 1 **3,059,504,327 bytes**, MD5 **9a6776857b7e34e1b80d5e073c555198**; mate 2 **3,133,850,963 bytes**, MD5 **082dcd1fb7dc08d78e57599aaf77efb5**. **Both matched official ENA MD5** in the actual job log, not inferred from file sizes.
- Reference cDNA source: Ensembl Plants release 61 `Triticum_aestivum.IWGSC.cdna.all.fa.gz`; **133,744 gene-annotated transcript FASTA headers** were checked before transfer. Original reference SHA256 file is inside the artifact; assembly accession equivalence to RefSeq v2.0 is **not** independently proven.
- Original pipeline: Bowtie2 `--very-sensitive --no-unal --no-mixed --no-discordant`, `samtools view -h -f 66 -F 2304 -q 20`, one counted first mate per primary proper pair, mapping transcript headers to gene IDs.
- Original job log prints **58,039 genes with nonzero conservative integer counts**, **14,357,584** `gene_assigned_fragments` and `passing_mapping_quality` records after filtering. These are **post-filter counts** and are **not** the total original read-pair denominator or Bowtie2 overall alignment rate. No alignment-rate claim is made without reading the uploaded `alignment_summary.txt`.
- Original upload contains **five** compact files: `conservative_one_sample_integer_counts.tsv`, `provenance.json`, `alignment_summary.txt`, `verified_ena_download_provenance.json`, `wheat_cdna.fa.gz.sha256`.

## New independent QC path

A separate fail-closed [audit script](analysis/audit_original_pilot_artifact.py) and [CI workflow](../../../.github/workflows/zm-r01-original-pilot-independent-qc.yml) were added after the original job completed. They download the **existing compact artifact**, not the 6.19 GB FASTQ, and independently cross-check 24-run manifest uniqueness, source MD5/bytes, sample accession, reference SHA, integer count table and its sum, and original Bowtie2 alignment-rate text. The workflow is configured to retain original compact derived evidence plus audit JSON for 30 days. **This is an implemented QC pathway, not a claim that its first execution passed.** Check its actual run and artifact before marking independent QC successful.

## Scientific non-equivalence and next release gates

1. **Pilot feasibility succeeded.** Real original paired FASTQs were downloaded and source-verified; integer counts were computed from alignments for one sample.
2. **Assembly comparability is NOT established.** The pilot reference `triticum_aestivum.IWGSC` is not automatically equivalent to the source paper's RefSeq v2.0/2.1 assembly. Before using pilot counts for final 24-sample DESeq2, verify exact FASTA assembly, annotation gene-ID space and overlap; choose one consistent reference for all 24 libraries.
3. **Statistical matrix remains missing.** This is one of 24 samples, not a 24-column count matrix. No FPKM/TPM conversion, invented missing samples, DESeq2 `~D*H*C`, FDR or biological discovery is claimed.
4. **Cost/safety:** The original job used a standard ephemeral GitHub-hosted runner; neither VPS nor a paid compute resource was used. Do not rerun the 6.19 GB pilot unnecessarily or launch an unbounded 24-job batch before QC/reference compatibility and resource limits are resolved.

**Evidence correction:** Earlier C20 correctly said that no artifact existed *at its inspection time*. C21 supersedes that time-sensitive observation: the original run **is now completed and the single-sample artifact exists**. It does **not** supersede C20's assembly warning.
