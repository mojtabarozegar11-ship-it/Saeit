# ZM-R01: first real FASTQ pair → conservative integer gene counts — experimental execution gate

**Date:** 2026-10-25. **Status:** actual read-only job specification and source-attributed integer-count algorithm committed to research branch; **successful FASTQ transfer, MD5 verification, alignment and integer-count artifact are NOT yet independently verified**. No journal-ready data matrix, FDR, differential-expression result or novel gene finding exists.

## Why the previous blocker needed a different solution
The original GEO record [GSE294406](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406) publishes FPKM and points to raw SRA runs for 24 biological libraries. FPKM **must not** be rounded into counts for DESeq2. The ENA source-verified paired FASTQ manifest `ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv` contains per-mate bytes and MD5 for all runs. The 149,540,873,452-byte complete 24-run FASTQ set is too large for the last verified free VPS snapshot.

The existing publicly visible repository is on GitHub's **free standard hosted-runner** eligibility (verify repository visibility and [billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions) before extending to many runs). Large paid runners are **not authorized**, nor is changing the VPS or live sites.

## Actual new implementation on the research branch
- Count generator: `analysis/unique_fragment_transcriptome_gene_counts.py` reads primary mapped proper paired-fragment alignments, retains first-in-pair once at MAPQ >= 20, matches transcript ID to gene ID using `gene:` metadata in the downloaded reference FASTA, and writes genuine *nonnegative integer* per-gene fragment counts plus JSON QC. It **rejects** missing reference mappings or zero assigned fragments. It does not parse FPKM and cannot invent a gene count.
- CI execution definition: `.github/workflows/zm-r01-single-srr-conservative-integer-count-pilot.yml`; designed for **one real control replicate**, SRR33083355/GSM8904963, rather than an unbounded mass transfer. It checks ENA-reported file sizes and MD5 of both downloaded mates before alignment, checks free ephemeral disk space, fetches public IWGSC wheat cDNA reference from an explicit Ensembl Plants release, builds a Bowtie2 index, conservatively counts paired alignments, and retains only compact QC/count artifacts on a seven-day expiry. It uses the standard public `ubuntu-22.04` runner, no paid resources, no site deployment, no Github branch merge or shared VPS storage.
- **Reference mismatch limitation:** prior original study used a genome-based HISAT2/DESeq2 pipeline and RefSeq v2.0; this pilot uses Ensembl Plants transcriptome reference and uniquely mapped proper fragments. Even if successful, **the counts are not necessarily the original authors' counts**. A reference-version/gene-ID harmonization audit, alignment-rate review, a validated all-24-library workflow and full factorial DESeq2 sensitivity are essential. Fragment counts from unique transcriptome alignment may undercount isoform-ambiguous and wheat homoeologous reads.

## Mandatory evidence gates
1. Show a **completed** GitHub Actions run, console log and artifact, not just code or an attempted job.
2. Verify two downloaded paired FASTQ MD5 values against ENA official accession metadata, observed file sizes and map quality, and record exact Ensembl reference SHA256.
3. Obtain actual `GSM8904963` gene counts and independent replay using the identical reference.
4. If pilot fails because of network, cDNA mapping, RAM or disk limits, preserve the precise error and redesign without spending money or loading production VPS; do not misrepresent a failed data fetch as counts generated.
5. Only after a scientifically acceptable integer-count pipeline is established **for all 24 biological samples**, use matching gene annotations, enforce identical count units, control reference consistency, run DESeq2 factorial `~ D*H*C` with interaction coefficient/FDR and source-grounded novelty audit. No fabricated hypothesis testing, FDR or biological conclusion.

**Scientific interpretation at this stage:** new computational execution route prepared and constrained; **raw integer-count availability remains unconfirmed** until real job evidence is returned. A first-sample pilot is *not* a publication-ready dataset.
