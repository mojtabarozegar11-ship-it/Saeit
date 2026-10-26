# ZM-R01 C31 — Experimental-unit clustering sensitivity: 24 libraries do not guarantee 16 independent residual degrees of freedom

**26 October 2026 | Conditional algebraic design sensitivity; not observed chamber assignment | DATA REBUILD / NO SUBMISSION**

## Primary records and observed facts

The source GEO series https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406 identifies **24 RNA-seq libraries**, eight nominal D×H×C treatment cells and three entries labelled `biol_rep1`–`biol_rep3` per cell. NCBI BioProject https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1249400 describes wheat cultivar Alana and stress regimes. The previously executed 24-row factorial design-matrix audit (C26) found a **full rank 8** and **nominal residual df = 24 − 8 = 16**. These facts alone do **not** identify the number of independently assigned plant/pot/chamber units.

GEO sample GSM8904986 https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM8904986 specifies poly(A) RNA, paired-end Illumina NovaSeq 6000 150 bp sequencing and drought as soil water content 25 ± 5% for its triple-stress treatment. This is a source-level library/treatment description, not evidence of independent chamber replication.

## New conditional experimental-unit sensitivity

Assume a saturated 2×2×2 factorial model with **p = 8** cell-mean coefficients. If independent *treatment-assignment units* are chambers or pots rather than library preparations, the maximum residual df for a unit-level saturated analysis is `N_independent_units − 8`, provided every cell has independent unit coverage and the design remains full rank. For balanced numbers `k` of independently assigned units per treatment cell:

| Hypothetical independent treatment-assignment units per cell (k) | Total independent units (8k) | Saturated 8-cell model rank | Maximum independent-unit residual df | Interpretation |
|---|---:|---:|---:|---|
| 1 | 8 | 8 | **0** | No within-cell unit-level residual variance; chamber identity and treatment can be completely confounded |
| 2 | 16 | 8 | **8** | Residual information possible if assignment and independence are real |
| 3 | 24 | 8 | **16** | Original nominal df justified *only if* all 24 units are independently assigned |

**This table is algebra, not measured evidence about Milec et al.'s actual growth chambers.** If plants share a chamber and treatment is fixed by chamber, library-level independence is violated for treatment-effect inference; simply including a random intercept cannot recover a treatment effect confounded with one chamber per treatment. Technical or leaf-level replicates cannot be re-labelled independent biological treatment-assignment replicates.

## Required metadata and analysis gate

1. Obtain original Methods/preprint and/or author deposition identifying each sample's **plant ID, pot ID, chamber ID, chamber reassignment/block, treatment-assignment unit, sampling day and library preparation batch**. A label `biol_rep3` is not a substitute.
2. If at least two independent units per treatment cell are demonstrated, prespecify an appropriate chamber/block-aware count-based model and distinguish treatment contrasts from within-chamber technical variation. A fixed-effects `~ D*H*C` DESeq2 design at library level may still be inappropriate for a clustered design.
3. If only one chamber per cell or no independently replicated chamber-level treatment assignment is documented, classify treatment inference as **not identifiable from independently replicated units**. Descriptive FPKM contrasts remain exploratory only.
4. No count matrix or FDR is available; no p-value, biological effect size, independent chamber count or gene claim is inferred from this sensitivity.

**Decision:** a new, explicit **experimental-unit identifiability gate** beyond the prior sample-row rank audit. The 24-library rank-8/16-df result remains a conditional mathematical property; the scientifically relevant independent-unit residual df is **unknown** until treatment allocation records are verified.
