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
