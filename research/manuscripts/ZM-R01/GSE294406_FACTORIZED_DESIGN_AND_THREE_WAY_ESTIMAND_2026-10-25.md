# ZM-R01: full-factorial interaction estimand and 24-run provenance

**Design audit (2026-10-25):** 24 biological libraries, eight D×H×C cells, three independent libraries per cell. The 24×8 binary design matrix [1,D,H,C,D:H,D:C,H:C,D:H:C] has full column rank 8 (verified by Gaussian elimination on the exact GEO sample-title-derived treatment factors), nominal residual df=16. These are design results, not gene-expression results. No raw integer counts were obtained in this step.

**Prespecified third-order interaction on the GLM log-link scale:** beta_DHC = mu111 - mu110 - mu101 - mu011 + mu100 + mu010 + mu001 - mu000. The triple-treated versus untreated comparison alone is NOT a test of this interaction. FPKM is not a count matrix and must not be rounded to obtain one. Model power is limited by n=3 per cell; batch, dispersion and true replicate independence remain unverified.

**Verified original source:** https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE294406 ; original source already analyzed combined stress, non-additivity and WGCNA (Milec 2025 DOI 10.1016/j.stress.2025.101115). This pre-specified contrast is only a candidate for a distinct estimand; no novelty or biological significance has been demonstrated.

| GSM | SRR | GEO sample title | D | H | C | Replicate |
|---|---|---|---:|---:|---:|---:|
| GSM8904963 | SRR33083355 | Alana_control_biol_rep1 | 0 | 0 | 0 | 1 |
| GSM8904964 | SRR33083354 | Alana_control_biol_rep2 | 0 | 0 | 0 | 2 |
| GSM8904965 | SRR33083353 | Alana_control_biol_rep3 | 0 | 0 | 0 | 3 |
| GSM8904966 | SRR33083352 | Alana_drought_biol_rep1 | 1 | 0 | 0 | 1 |
| GSM8904967 | SRR33083346 | Alana_drought_biol_rep2 | 1 | 0 | 0 | 2 |
| GSM8904968 | SRR33083347 | Alana_drought_biol_rep3 | 1 | 0 | 0 | 3 |
| GSM8904969 | SRR33083348 | Alana_elevated-temp_biol_rep1 | 0 | 1 | 0 | 1 |
| GSM8904970 | SRR33083349 | Alana_elevated-temp_biol_rep2 | 0 | 1 | 0 | 2 |
| GSM8904971 | SRR33083350 | Alana_elevated-temp_biol_rep3 | 0 | 1 | 0 | 3 |
| GSM8904972 | SRR33083351 | Alana_elevated-CO2_biol_rep1 | 0 | 0 | 1 | 1 |
| GSM8904973 | SRR33083339 | Alana_elevated-CO2_biol_rep2 | 0 | 0 | 1 | 2 |
| GSM8904974 | SRR33083340 | Alana_elevated-CO2_biol_rep3 | 0 | 0 | 1 | 3 |
| GSM8904975 | SRR33083341 | Alana_elevated-temp+drought_biol_rep1 | 1 | 1 | 0 | 1 |
| GSM8904976 | SRR33083342 | Alana_elevated-temp+drought_biol_rep2 | 1 | 1 | 0 | 2 |
| GSM8904977 | SRR33083343 | Alana_elevated-temp+drought_biol_rep3 | 1 | 1 | 0 | 3 |
| GSM8904978 | SRR33083344 | Alana_elevated-CO2+drought_biol_rep1 | 1 | 0 | 1 | 1 |
| GSM8904979 | SRR33083345 | Alana_elevated-CO2+drought_biol_rep2 | 1 | 0 | 1 | 2 |
| GSM8904980 | SRR33083338 | Alana_elevated-CO2+drought_biol_rep3 | 1 | 0 | 1 | 3 |
| GSM8904981 | SRR33083337 | Alana_elevated-CO2+elevated-temp_biol_rep1 | 0 | 1 | 1 | 1 |
| GSM8904982 | SRR33083336 | Alana_elevated-CO2+elevated-temp_biol_rep2 | 0 | 1 | 1 | 2 |
| GSM8904983 | SRR33083335 | Alana_elevated-CO2+elevated-temp_biol_rep3 | 0 | 1 | 1 | 3 |
| GSM8904984 | SRR33083332 | Alana_elevated-CO2+elevated-temp+drought_biol_rep1 | 1 | 1 | 1 | 1 |
| GSM8904985 | SRR33083334 | Alana_elevated-CO2+elevated-temp+drought_biol_rep2 | 1 | 1 | 1 | 2 |
| GSM8904986 | SRR33083333 | Alana_elevated-CO2+elevated-temp+drought_biol_rep3 | 1 | 1 | 1 | 3 |

**Required exit gate:** unnormalized integer gene-count matrix from a uniform genome/annotation, sample joins, gene-ID validation, library size/mapping QC, fit of full-factorial DESeq2 or edgeR, FDR correction, sensitivity and source-work novelty check. Do not claim any count-based DEGs or publication readiness until these exist.
