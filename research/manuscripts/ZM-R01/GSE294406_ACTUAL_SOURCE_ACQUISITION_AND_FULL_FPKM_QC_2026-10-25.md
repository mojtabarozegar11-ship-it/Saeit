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
