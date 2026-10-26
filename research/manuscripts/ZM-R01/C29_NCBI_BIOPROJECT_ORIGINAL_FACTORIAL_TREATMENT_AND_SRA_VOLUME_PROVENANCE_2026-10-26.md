# ZM-R01 C29 — Original NCBI BioProject treatment and SRA-volume provenance

**26 October 2026 | Primary source:** NCBI BioProject [PRJNA1249400](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1249400), cross-linked to GEO [GSE294406](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406). This is an independent primary-metadata inspection, **not** FASTQ read processing or proof of biological independence.

## Original design attributes independently confirmed

The submitting project, “Integrative morpho-physiological and transcriptomic insights into wheat responses to combined drought, heat, and elevated CO₂ under future climate conditions,” identifies winter bread wheat cultivar **Alana** and **three experimental stress dimensions**:
- D: drought.
- T: elevated temperature, **up to 31 °C**.
- C: elevated CO₂, **700 ppm**.

It explicitly names the seven noncontrol arms **D, T, C, C+T, T+D, C+D, C+T+D**; together with control these are the **eight cells** of a 2×2×2 factorial treatment layout. The BioProject describes sampling **third and fourth leaves of the main tiller at GS61**. These details are important biological covariates and prevent falsely describing this as a generic drought-only leaf experiment.

The project lists **24 SRA experiments and 24 BioSamples**, consistent with the GEO 24-sample list and nominal three replicates per treatment cell. The submitter's “biol_rep” labels and 24 distinct accessions **do not independently prove 24 independently randomized experimental units** or rule out pseudoreplication. The earlier 8/8 design-matrix rank and nominal 16 residual df remain **algebraic only** until plant/pot/chamber assignment is checked.

## Important unit and provenance distinction

The NCBI BioProject project summary separately displays approximately **314 Gbases** and **99,400 Mbytes** for SRA data, while the earlier ENA metadata-derived list summed to **149,540,873,452 compressed FASTQ bytes**. These are **different database accounting/representation measures**, not necessarily the same objects or formats. Their inequality **must not be labeled corruption, loss or an MD5 mismatch**. Resolve only with per-run, per-mate URLs, actual byte lengths, checksum algorithms and archive-format definitions.

## Implications for differential expression

1. Preserve the **eight treatment combinations** and the three-factor interaction terms in the design if independence, replication and dispersion assumptions are confirmed.
2. The experiment has **one named cultivar** and one recorded developmental stage; do not extrapolate to multiple genotypes or stages.
3. Leaf sampling from third/fourth leaves cannot be interpreted as independent leaf replicates without the experimental-unit records.
4. Do not substitute FPKM for integer counts or treat 1,167 exploratory candidate genes as FDR-controlled DEGs.
5. No exact original RefSeq v2.0 FASTA+matching GTF+rights/checksum pair, read-level MD5 validation, count matrix or DESeq2 run was obtained. No bulk FASTQ download, VPS use or expense was incurred.

**Evidence boundary:** This C29 adds original NCBI experimental-factor, tissue-stage and SRA accounting metadata beyond the earlier 24-ID design-rank check. It is not a new empirical expression result, and ZM-R01 remains **DATA REBUILD / NO SUBMISSION**.
