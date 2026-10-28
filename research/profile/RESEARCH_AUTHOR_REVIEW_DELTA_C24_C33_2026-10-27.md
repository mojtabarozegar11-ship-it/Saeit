# Author-review delta — AE C24 direct R package and ZM C33 published Methods (27 October 2026)

**Review-only; no approval, submission, identity assertion or website deployment.** Prepared by AI as internal research administration; human scientific authorship, declarations and approval remain reserved to the actual author.

## AE-2026-001: actual countryatlas R execution

- Source manuscript now includes **Methods 2.15 / Results 3.25** for [C24](../manuscripts/AE-2026-001/AE-2026-001_C24_ACTUAL_COUNTRYATLAS_R300_DIRECT_PACKAGE_BENCHMARK_2026-10-27.md).
- Unlike C22's mathematical emulation, actual **countryatlas 3.0.0** `growth_rate(type="cagr")` was run in R 4.6.1, [run 40407883759](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40407883759) **SUCCESS**, [artifact 12692315824](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40407883759/artifacts/12692315824) (two country-level CSVs and one summary).
- Source-locked **157/169** positive-endpoint economies, maximum numerical package/formula discrepancy **2.22e-16**, median log/CAGR values 2.3555753/2.3835381 and 0.9751105/0.9798802 respectively.
- **Still OPEN:** direct `compare_vintages` execution on three real WDI vintages, 2024/2025 ILOSTAT archives, source-lineage/ISIC sensitivity, novelty, author declarations. **MAJOR REVISION / NO SUBMISSION**.

## ZM-R01: published full Methods newly available

- [C33](../manuscripts/ZM-R01/C33_PUBLISHED_2025_FULL_TEXT_METHODS_EXTRACTED_REPLICATION_REFERENCE_AND_DEG_GATE_2026-10-27.md) records **successful full-text extraction** from the [published CC BY 2025 paper](https://repository.rothamsted.ac.uk/id/eprint/33667/2/1-s2.0-S2667064X25003823-main.pdf), superseding C32's prior *text inaccessible* status. PDF **bytes and checksum still not saved**.
- Published RNA methods: **three biological replicates per treatment at GS61**, **150-bp paired-end NovaSeq**, Trim Galore v0.4.1, HISAT2, stated “RefSeq v2.0, EnsemblPlants,” and authors' DESeq2. Phenotypic replicates: three per treatment, each containing six plants.
- Published statistical thresholds must remain distinct: DESeq2 differential-expression **FDR-adjusted p<0.05** versus GO/KEGG gene input **adjusted p<0.01 plus |log2FC|≥1**, with pathway FDR<0.05.
- **Still OPEN:** number and independent assignment of stress-treatment chambers/pots/blocks, exact reference FASTA/GTF accession and checksum, unique/multimapping rules, actual raw integer counts, independent DEG/FDR replication. Initial growth in one named chamber does **not** establish stress-treatment chamber allocation. **DATA REBUILD / NO SUBMISSION**.

## MR-2026-001: unchanged science gates

C44's seasonal-volume/event-level counterexample is synthetic; Car Table 5, Amini F7, Cvejić denominator, full comparator Methods and G/D/R/A empirical validation remain unresolved. The verified MR Word predates C44. **MAJOR REVISION / NO SUBMISSION**.

## Human approval and deployment boundaries

No article is approved for submission; no manuscript ID, editorial acceptance, independent human peer review, funding/COI/AI disclosure confirmation, or verified identity/affiliation is claimed. Site profile is **GitHub staging only**, not live. Do not merge PR #1054, publish a live CV, or interact with restricted social accounts without the separately required authorization and backups/rollback.
