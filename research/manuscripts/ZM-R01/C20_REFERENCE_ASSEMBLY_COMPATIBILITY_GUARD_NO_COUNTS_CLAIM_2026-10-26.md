# ZM-R01 — high-priority wheat reference assembly compatibility gate

**26 October 2026. Scientific status: potential reference mismatch; NO approved gene-count result or DESeq2 matrix.**

## What was actually inspected

1. Original Milec (2025) source method audit `C19_MILEC_ORIGINAL_SOURCE_AND_COUNT_RECONSTRUCTION_SCIENTIFIC_GATE_2026-10-25.md` reports **wheat RefSeq v2.0 / EnsemblPlants**, aligned with HISAT2; the source audit was grounded in original method paragraphs, but its exact sequence/annotation accession was not independently retrieved here.
2. Running [pilot workflow 40222743342](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40222743342) uses **`https://ftp.ensemblgenomes.ebi.ac.uk/pub/plants/release-61/fasta/triticum_aestivum/cdna/Triticum_aestivum.IWGSC.cdna.all.fa.gz`** with `bowtie2` transcriptome alignment. Its path explicitly says `triticum_aestivum` / **IWGSC**, not `triticum_aestivum_refseqv2`.
3. The independent [Ensembl Plants release 61 reference record](https://resources.qiagenbioinformatics.com/manuals/rnaanalysisportal/6000/index.php?manual=General_references_annotations.html) identifies `triticum_aestivum` release-61 genome as **IWGSC** and lists `Triticum_aestivum.IWGSC.61.gff3.gz`. The [Ensembl Genomes 63 separate RefSeqv2 annotation record](https://jun2026-plants.ensembl.org/Triticum_aestivum_refseqv2/Info/Annotation) identifies **IWGSC RefSeq v2.1**, accession **GCA_018294505.1**, as a **distinct** assembly/annotation. The [IWGSC official annotation resource](https://www.wheatgenome.org/resources/annotations) likewise lists RefSeq v2.1 separately from v1.0.
4. **Inference, not yet a sequence-header proof:** the pilot is *likely* using a reference distinct from the original publication's RefSeq v2.0. Its `wheat_cdna.fa.gz.sha256` will prove the exact bytes only if the pilot finishes and uploads the artifact. A SHA alone cannot prove assembly compatibility. Exact FASTA header/annotation metadata and gene-ID overlap must be verified before comparing genes or reusing this index for the 24-sample final analysis.

## Immediate scientifically valid decisions

- **Do not cancel or edit the still-running pilot** solely because of this observation; its first-sample output may be useful for feasibility/QC, but cannot be declared matched to Milec's original annotation without verification. A changed workflow in the same GitHub concurrency group could cancel the run and discard already acquired FASTQ; no such change is authorized or executed in this note.
- **Do not mix gene counts from different wheat assemblies or annotations** in one matrix. All 24 libraries must use the **same exact reference** and gene-ID map; if original-study comparability is essential, select the RefSeq v2-compatible assembly/annotation and reprocess every library uniformly.
- Require a machine-readable provenance manifest containing exact assembly accession, annotation version, FASTA URL/SHA256, aligner version/parameters, gene-ID extraction rules, fraction of multimapping/ambiguous pairs, and library QC. The pilot's MAPQ>=20 conservative paired-fragment rule is an operational counting choice, not identical to original HISAT2+DESeq2 workflow.
- **No first-sample counts artifact exists at time of inspection**: the GitHub Actions job's `Transcriptome alignment and genuine conservative integer fragment counts` step was still **in progress**, with artifact list empty. No DEG, FDR, biological conclusion or submission can be claimed.
- A pilot completed against an unverified or mismatched reference must remain **reference-specific technical feasibility evidence**, not a finished sample in a publication-grade uniform 24-library count matrix.

## Exit criteria

1. Pilot job finishes with logs and compact artifact; confirm both original FASTQ MD5, reference hash, alignment rate and integer count provenance.
2. Identify the exact IWGSC reference assembly used, crosswalk to the original study's RefSeq v2.0/2.1 and verify stable gene identifiers; if mismatched, use a consistent publication-grade reference for **all** 24 libraries.
3. Only then continue batch reconstruction, `~D*H*C` DESeq2 and FDR with actual biological replicates. No imputation, no FPKM-to-count rounding, no VPS disk risk, no paid compute.
