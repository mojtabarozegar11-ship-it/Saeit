# ZM-R01 — actual GEO source acquired; full FPKM matrix QC executed and independently repeated in GitHub Actions
**Date:** 2026-10-25. **Scope:** GSE294406, original submitter-supplied FPKM workbook. **Status:** source acquired, QC complete; raw count analysis, differential expression, novel gene mechanism and manuscript submission **NOT DONE**.

## Independently verifiable primary evidence
- NCBI original: https://ftp.ncbi.nlm.nih.gov/geo/series/GSE294nnn/GSE294406/suppl/GSE294406_FPKM_all_treatments.xlsx
- Source GEO series: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406
- Successful initial read-only acquisition run: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40170531549 ; artifact ID 12590350040.
- Successful **full 2,524,800-cell numerical QC run**: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40170671082 ; artifact ID **12589433491**; all job steps successful. Full source XLSX, initial audit JSON and complete numerical QC JSON stored in artifact with 14-day retention. No VPS/cPanel/site deployment.
- Committed reproducible QC code: https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/ZM-R01/analysis/audit_fpkm_matrix.py
- Acquisition code: https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/ZM-R01/analysis/fetch_and_audit_gse294406.py
- PR: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1054 (Draft; NOT merged).

## Verified original source and matrix properties
| Metric | Observed from downloaded bytes |
|---|---|
| Original XLSX bytes | **26,596,634** |
| Original XLSX SHA256 | `751c80defdc09b180f6174d6bbb3c7234570e8f15725f4c47cfcc9565b2f7e7b` |
| Worksheet | `List1`, 105,201 rows including header, 25 columns including gene ID |
| Gene rows | **105,200** |
| Unique gene identifiers | **105,200**; duplicate IDs **0** |
| FPKM sample columns | **24**, grouped 8 conditions × 3 biological replicates in manifest |
| Numerical FPKM cells audited | **2,524,800** |
| Missing / non-finite / negative | **0 / 0 / 0** |
| Exact zeros | **1,006,967 (39.883%)** |
| Within-condition minimum Pearson correlation on log2(FPKM+1) | **0.971812** (CTD condition) |
| Original source integrity | Checksum verified in BOTH local processing and GitHub Actions; both obtained identical QC aggregate totals |

### Within-condition replicate similarity — descriptive only
Pearson correlation across all 105,200 genes, transformed as log2(FPKM+1), for each of three within-condition pairs. Values are descriptive and **not** a biological independence test, proof of sample identity, or statistical differential expression.

| Group | Min pairwise r | Mean of three pairwise r |
|---|---:|---:|
| CTR | 0.993744 | 0.994813 |
| eT | 0.985591 | 0.990564 |
| eC | 0.995582 | 0.996166 |
| D | 0.991641 | 0.993812 |
| CT | 0.993152 | 0.994772 |
| CD | 0.983715 | 0.990364 |
| TD | 0.975438 | 0.985573 |
| CTD | 0.971812 | 0.983563 |

The **CTD** (triple-combination) and **TD** (heat+drought) groups show the lowest within-group minima (0.9718 and 0.9754); these remain high absolute correlations, but sample-level batch/read QC is necessary before claiming any specific replicate is an outlier or drawing mechanistic conclusions.

## What this accomplishment DOES NOT establish
1. These numbers describe **normalized FPKM** values. They are **NOT integer raw read counts** and **MUST NOT be fed to DESeq2 or edgeR count-based likelihood models**. No DEGs, FDR, log-fold-change tests, enrichment, causal mechanism or gene discoveries have been computed or validated.
2. Workbook column names (e.g., `CTR_R1_FL`, `eT_R1_FL`, `CD1_FL`, `CTD_R3_FL`) correspond to treatment/replicate labels, but exact column↔GSM accession pairing should still be checked against original authors' supplementary metadata before any sample-specific scientific inference.
3. High global correlations can be influenced by many shared zero/low-expression genes. This preliminary metric is not a substitute for expression-filtered PCA, sequencing QC, mapping/annotation checks, or biological-batch evaluation.
4. All 24 libraries belong to **Alana** wheat leaf tissue at **GS61**. No genotype, tissue or stage comparison is estimable *within this dataset*.
5. Milec et al. 2025 DOI **10.1016/j.stress.2025.101115** already analyzed combined stress and transcription-factor networks; Yoldi-Achalandabaso et al. 2025 DOI **10.1111/ppl.70125** already synthesized triple-stress agronomic effects. The present source-QC work is not a novel biology paper.

## Immediate next scientific gate
Secure verified **raw gene counts** from original authors or reconstruct counts from public SRA reads with an explicit ~99.4 GB download/storage/compute plan. Establish source/reference build, library strandedness, per-sample QC, sample identity, batch structure, prespecified novel question and a source-by-source originality comparison. Then perform valid factorial inference on real counts, report effect sizes and FDR with complete reproducibility. The source data have now actually been obtained; **the remaining blocker is count-level inferential analysis and independent biological novelty**, not the public FPKM workbook download.

**Sole intended human author:** Mojtaba Roozegar; AI-assisted source/QC preparation requires actual author scientific interpretation and publisher-specific disclosure. No submission, manuscript ID, acceptance or publication.


## C17 independent filtered-expression QC (2026-10-25) — NEW descriptive analysis, NOT inferential RNA-seq

The same **original 26,596,634-byte GEO XLSX** was independently reopened from the previously verified artifact/ZIP and matched to SHA256 `751c80defdc09b180f6174d6bbb3c7234570e8f15725f4c47cfcc9565b2f7e7b`. Unlike the earlier all-gene correlation, this run filtered genes **FPKM ≥ 1 in at least three of 24 samples**, then used `log2(FPKM+1)` for descriptive sample-level analysis. The source file was not modified.

| Recomputed descriptive metric | Actual result |
|---|---:|
| Original genes | 105,200 |
| Genes retained under stated expression filter | **45,359** |
| Genes excluded | **59,841** |
| Samples | **24** |
| PC1 / PC2 / PC3 fraction of filtered sample variance | **32.0394% / 15.8649% / 15.3513%** |
| Minimum within-condition pairwise Pearson correlation, filtered log-FPKM | **0.929810** |
| Median within-condition correlation | **0.986279** |
| Median between-condition correlation | **0.926025** |
| Maximum between-condition correlation | **0.981400** |
| Nearest-correlated sample in same annotated treatment group | **24/24** |

**Interpretation:** The earlier all-gene minimum within-group correlation of 0.971812 **must not be presented as a robust universal QC metric**: after filtering low-abundance genes, the minimum is lower (0.929810). This is not evidence of sample failure, but demonstrates dependence on expression filtering. All 24 samples have their strongest pairwise Pearson correlation with another member of their annotated condition; this is an internal-label consistency check, **not** proof of biological independence, true GSM identity, absence of batch effects or mechanism. PCA is exploratory and descriptive only. All group names here are parsed from the **workbook column headers**; full 24-column ↔ GSM mapping remains pending.

**Reproducibility:** `research/manuscripts/ZM-R01/analysis/exploratory_filtered_fpkm_qc.py` requires the original NCBI workbook and `numpy`, uses the existing local `audit_fpkm_matrix.py` parser, verifies the same SHA256 and writes JSON with sample-level PC scores and nearest-neighbor labels. This analysis was **executed in the isolated research workspace**; a new independent GitHub Actions run for the C17 script **has now completed successfully** at https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40174446670 with all job steps green; artifact **12591497313** contains the original source XLSX, earlier QC JSON and the new filtered exploratory QC JSON (expires 2026-11-08). The local run and CI run are separate executions. Do not conflate a committed script with a CI run.

**Primary-source novelty blocker strengthened:** The original published study is Milec et al., *Plant Stress* 18 (2025) 101115, DOI https://doi.org/10.1016/j.stress.2025.101115. A **legal, author-deposited preprint** was newly located at https://zenodo.org/records/16229021 (DOI 10.5281/zenodo.16229021; original DOCX downloadable) and the Czech Academy institutional record links an open-access author version: https://asep.lib.cas.cz/arl-cav/cs/detail-cav_un_epca-0641134-Integrative-morphophysiological-and-transcriptomic-insights-into-wheat-responses-to-combined-drough/ . **The full original manuscript was located but not yet completely extracted/read in this C17 run**, so do not claim a complete novelty exclusion audit. The original NCBI BioProject confirms 24 SRA experiments, Alana genotype, GS61 leaves and approximately 99.4 GB of sequence archives: https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1249400 .

**Scientific gate:** no raw count matrix has been acquired; no DESeq2/edgeR, gene-level FDR, independent gene mechanism or article-ready result exists. Before any journal submission, check the original preprint's full analyses and supplementary data, secure raw gene counts or plan SRA processing, reconcile sample ↔ GSM, and specify a distinct mechanistic hypothesis requiring genuine author-led interpretation.


### C17 source-column ↔ GSM concordance audit — complete metadata mapping, verified in independent CI

The source FPKM workbook orders conditions **CTR, eT, eC, D, CT, CD, TD, CTD**, whereas the original GEO manifest orders **control, drought, elevated temperature, elevated CO₂, heat+drought, CO₂+drought, CO₂+heat, triple**. Consequently, **positional joining is scientifically unsafe**. A new parser maps each workbook header's **condition + biological replicate number** to the manifest's independently recorded **drought/heat/CO₂ factor vector + replicate**, without relying on row order. This successfully resolves **24/24 workbook columns to 24 unique GSM accessions**, with no duplicates or unmatched headers.

Concrete checks: `CTR_R1_FL → GSM8904963`, `eT_R1_FL → GSM8904969`, `CT_R1_FL → GSM8904981`, `CD1_FL → GSM8904978`, `TD1_FL → GSM8904975`, `CTD_R3_FL → GSM8904986`. NCBI BioSample independently corroborates examples GSM8904963 (control), GSM8904981 (CO₂+temperature) and GSM8904985 (triple): https://www.ncbi.nlm.nih.gov/biosample/SAMN47891443 ; https://www.ncbi.nlm.nih.gov/biosample/SAMN47891425 ; https://www.ncbi.nlm.nih.gov/biosample/SAMN47891421 .

**Independent execution verified:** GitHub Actions run https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40174630549 completed **successfully**; job logs explicitly print `mapped_columns: 24` and `unique_GSM: 24`. Artifact **12591802041** includes original source XLSX, original full QC, filtered PCA QC and the new 24-column mapping JSON (expires **2026-11-08**). Reusable code: `research/manuscripts/ZM-R01/analysis/map_fpkm_columns_to_gsm.py`.

**Important boundary:** This proves **metadata label concordance** between the submitter workbook and GEO sample titles, **not** a read-level forensic identity check; definitive identity/batch verification still requires raw sequencing metadata and count-level QC. No gene-level inference or novel biological result has been generated.
