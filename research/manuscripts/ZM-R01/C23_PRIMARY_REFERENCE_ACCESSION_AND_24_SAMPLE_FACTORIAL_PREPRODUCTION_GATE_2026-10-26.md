# ZM-R01 C23 — primary-source reference accession decision and GEO factorial preflight
**Date:** 26 October 2026. **Scientific release:** BLOCKED. **Costs/VPS:** none.

## Verified reference distinction
The completed pilot's ENA provenance identifies an Ensembl Plants release-61 cDNA file at `/fasta/triticum_aestivum/cdna/Triticum_aestivum.IWGSC.cdna.all.fa.gz`. The compressed FASTA SHA256 is recorded in the original artifact, but a cDNA filename and hash alone do **not** establish assembly identity or equivalence to the paper's genome-based pipeline.

The primary Ensembl genome page identifies the ordinary **Triticum aestivum (IWGSC)** species as **IWGSC RefSeq v1.0, GCA_900519105.1**, while its separate **Triticum_aestivum_refseqv2** genome entry identifies **IWGSC RefSeq v2.1, GCA_018294505.1**. NCBI identifies the v2.1 reference as **GCF_018294505.1**. GCA and GCF prefixes refer to assembly records from different INSDC/RefSeq namespaces; a filename matching “IWGSC” is **not** proof that its sequence is v2.1.

**Primary evidence:**
- Ensembl ordinary wheat IWGSC assembly: https://www.ensembl.org/genome/GCA_900519105.1
- Ensembl RefSeqv2 species: https://jun2026-plants.ensembl.org/Triticum_aestivum_refseqv2/Info/Annotation
- NCBI RefSeq v2.1 annotation: https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/
- IWGSC announcement and official accession repository: https://www.wheatgenome.org/resources/annotations

**Conclusion:** the pilot should be treated as **a potentially v1.0-reference transcriptome analysis**, not silently relabeled as v2.0 or v2.1. Exact release-61 FASTA header/accession, its parent genome assembly and transcript-gene annotation version must be checked against official metadata before claiming a definitive pilot assembly. The original Milec 2025 method's *exact* version must be checked from its primary full methods; v2.0, v2.1 and v1.0 must not be conflated.

## Experiment design independently documented in official GEO
The official GEO series GSE294406 describes 24 wheat cultivar Alana leaf RNA-seq samples: 8 combinations of drought D, elevated temperature H and elevated CO2 C, with 3 biological replicates in each cell. Source: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406

The checked treatment ordering is control; D; H; C; H+D; C+D; C+H; C+H+D. A deterministic preflight in `analysis/official_geo_24_sample_factorial_design_gate.py` generates the 24 GSM labels and the binary design, verifies the 8 distinct factor cells and 3 replicates per cell, and tests the 8-column full model `~ D*H*C` for rank 8 (24 observations, nominal residual df 16). **This is only design-matrix identifiability**, not evidence of power, correct biological replicate identity, successful mapping or differential expression.

**Critical mapping limitation:** the ENA manifest has 24 SRRs and BioSample IDs but no GSM column. Only **GSM8904963 = SRR33083355 = SAMN47891443** has been independently reconciled against the original verified pilot. The remaining **23 GSM-to-SRR joins must be established individually from official GEO/BioSample/ENA records** before production; guessing by accession order is prohibited.

## Mandatory fail-closed gates before 24-library processing
1. Verify original study reference build and gene annotation against its full methods; obtain source URLs, accessions, checksums and gene-ID namespace for one consistent build. Do not equate Ensembl IWGSC v1 with Ensembl refseqv2.
2. Complete the 24 individual GSM–BioSample–SRR joins, verify 48 official ENA FASTQ checksums and paired-end orientation/strandedness.
3. Choose and document a genome-aware aligner and a gene-level counting rule that **explicitly treats multimappers**, mate pairing, duplicate/secondary alignments, overlap, annotation strand and ambiguous assignment. Never equate `MAPQ >= 20` with strict unique concordant alignment.
4. Run one genuinely compatible pilot with original raw reads and publish transparent QC; **only after acceptance** process all 24 libraries under identical assembly and counting rules. A 24-column **raw nonnegative integer gene-count** matrix must use identical gene IDs, with library QC and design metadata matched to source records.
5. Fit `DESeq2 ~ D*H*C` only when the design has full rank and library counts are real, with prespecified contrasts and multiple-testing FDR. Three-way interaction is identifiable in principle but can have low power; no fabricated DEG counts or adjusted p-values.
6. Source code and scientific results stay on the research branch. No paid compute, VPS changes, journal submission, PR #1054 merge or live-site change.

**Current outcome:** original one-sample pilot counts exist but strict unique mapping was refuted by C22; no publication-grade 24-sample matrix, differential expression, FDR or biological novelty conclusion exists.


## 26 October 2026 source-mapping resolution (C24 supersedes the mapping gap only)

The earlier 23-unverified-GSM-to-SRR statement above describes the **earlier C23 checkpoint**, not the current state. A subsequent independent run **40260457907** successfully parsed all 24 deposited GEO family SOFT sample BioSample relationships and joined them to the original ENA manifest without accession-order inference. The verified 24-row crosswalk is preserved in `GSE294406_24_GSM_BIOSAMPLE_SRR_VERIFIED_CROSSWALK_2026-10-26.tsv`, with SHA256 source records and the downloadable run artifact documented in `C24_OFFICIAL_GEO_24_BIOSAMPLE_SRR_SOURCE_CROSSWALK_COMPLETED_2026-10-26.md`. **24/24 sample identities are now resolved.** This does not verify the actual bytes of all 48 FASTQ files or remove the unresolved reference, multimapping, 24-count matrix, DESeq2, FDR, or biological-novelty gates.

## 26 October 2026 original-paper Methods recovery — reference version now source-confirmed, accession still unresolved

The **full original 2025 Milec et al. paper** is openly discoverable as the author/institutional repository PDF: https://repository.rothamsted.ac.uk/id/eprint/33667/2/1-s2.0-S2667064X25003823-main.pdf (Milec et al., *Plant Stress* 18, 101115, DOI 10.1016/j.stress.2025.101115). The original Methods passage, indexed from this primary PDF on 26 October 2026, states that wheat leaf RNA was poly-A selected and sequenced as **Illumina NovaSeq 6000 150-bp paired-end**; reads were trimmed with **Trim Galore v0.4.1** and aligned with **HISAT2** to **“wheat reference genome (RefSeq v2.0, EnsemblPlants)”**; differential expression was analyzed using **DESeq2**. Independent GEO sample metadata (e.g. https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM8904976) repeats RefSeq v2.0, HISAT2, Trim Galore, and mentions Cuffdiff/DESeq2 and FPKM.

**Material scientific advance:** the authors' declared **version is v2.0**, not merely an inference from a secondary abstract. **Remaining blocker:** neither the quoted Methods nor the GEO sample field supplies an exact INSDC GCA/GCF accession, annotation-release checksum, gene-ID namespace, or a complete count-assignment/multimapping policy. Do not substitute the separately documented Ensembl v2.1 (GCA_018294505.1) for v2.0 merely because its name contains “refseqv2”; likewise the pilot's generic IWGSC cDNA may reflect v1.0. Original article FPKM supplementary expression is not a raw fragment-count matrix. Obtain exact versioned genome FASTA/GTF and source SHA256 before a single final alignment.

**Methodological discrepancy requiring explicit decision:** the original study describes **genome-aligned HISAT2 paired-end reads**, whereas the prior pilot used **Bowtie2 against transcriptome cDNA**, filtered by MAPQ and was shown to include ambiguous/multi-aligned fragments. These are different estimands and gene namespaces; pilot counts must not be pooled with newly produced genome-based counts. A new 24-sample pipeline must choose one reference, one paired-fragment gene assignment rule and record ambiguous multimapping rather than treating MAPQ≥20 as proof of uniqueness.

**Additional primary consortium crosscheck (26 October 2026):** IWGSC separately announced **RefSeq v2.0** as available through its URGI repository (https://www.wheatgenome.org/resources/sequences/iwgsc-refseq-v2.0-now-available-at-urgi), and subsequently announced **RefSeq v2.1** and annotation v2.1 through URGI and NCBI (https://internet6-national-wheatgenome.custom.hub.inrae.fr/resources/annotations/refseq-v2.1-assembly-and-annotation-now-freely-available-at-urgi-and-ncbi). The official Ensembl `Triticum_aestivum_refseqv2` page currently explicitly names **v2.1** (https://jun2026-plants.ensembl.org/Triticum_aestivum_refseqv2/Info/Annotation). Thus the author's written **v2.0** is a real separately announced reference version, and using current Ensembl v2.1 would be a *documented methodological deviation* requiring explicit justification rather than silent source matching. Exact v2.0 downloadable FASTA/GFF and accession/checksums remain to be obtained.
