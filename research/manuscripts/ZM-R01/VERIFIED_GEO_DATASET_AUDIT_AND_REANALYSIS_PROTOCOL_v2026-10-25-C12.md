# ZM-R01 — wheat drought transcriptomics: verified accession audit and reproducible analysis protocol
Version 2026-10-25/C12-v1. **Dataset metadata verified; NO raw reads downloaded; NO differential expression analysis executed; NO novel biological results claimed.** This is an executable study-design specification for independent reanalysis, not a completed article.

## Scientific question
Can drought-responsive transcriptional programs in *Triticum aestivum* be separated into genotype-associated, growth-stage-associated and treatment-associated signals without conflating stress exposure, tissue, platform, batch and genetic perturbation? The question must be narrowed after checking raw sample metadata and study permissions. **Originality depends on genuinely new analysis or validation**, not reuse of published authors' results as our own.

## Source verification / accession triage (2026-10-25)
### Candidate A: GSE157033 — **potentially eligible**, with replicate imbalance
- GEO series https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE157033 ; BioProject **PRJNA659916** https://www.ncbi.nlm.nih.gov/bioproject/PRJNA659916 . Both identifiers and the GEO↔BioProject relation independently corroborated by NCBI indexed records. Linked original publication: Chu et al., *RNA-seq analysis reveals different drought tolerance mechanisms in two broadly adapted wheat cultivars ‘TAM 111’ and ‘TAM 112’*, **Scientific Reports** (2021), official full text mirrored by PMC https://pmc.ncbi.nlm.nih.gov/articles/PMC7900135/.
- Organism: bread wheat; platform: Illumina HiSeq 4000; tissue: flag leaves; two cultivars TAM 111/TAM 112; two growth stages (heading/grain filling); irrigation dry/wet; **15 listed GEO samples**, BioProject lists **15 SRA experiments**. A balanced 2×2×2×2 design would require 16; therefore verify exactly which biological replicate is missing before building a design matrix. Do not claim all cells have two biological replicates.
- Original published differential-expression findings are **not our new results**. The original article already compares cultivar, stage and water treatment, so a claim of first discovery would be false. Candidate for reanalysis only if an independently defensible new methodological question or external validation is developed.
- The original publication reports total 2,254 drought-related DEGs and 1,214 shared genes; these are **published third-party numbers** not independently recomputed.

### Candidate B: GSE226842 — **potentially eligible as an external mechanistic validation cohort only**
- GEO https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE226842 ; BioProject **PRJNA941868** https://www.ncbi.nlm.nih.gov/bioproject/PRJNA941868 . NCBI GEO lists **12 samples** and platform Illumina NovaSeq 6000; second leaf, cultivar Atlas66, well-watered vs seven-day drought, with wild-type/virus control and TaZFP13D overexpression/siRNA perturbations. For example GSM7085309 is OEX13D_drought_biol_rep_2 with cultivar Atlas66 and seven-day water withholding after 14 days watering, https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM7085309.
- Publication Bouard et al., *Modulation of the wheat transcriptome by TaZFP13D under well-watered and drought conditions*, Plant Molecular Biology (2024); full text https://pmc.ncbi.nlm.nih.gov/articles/PMC10853348/. NCBI BioProject independently confirms accession cross-reference.
- **Critical comparability warning:** GSE226842 uses gene manipulation, different cultivar, tissue, developmental stage, platform and drought protocol; it is **not a biological replicate** of GSE157033. It must not be naively pooled or interpreted as an independent validation of cultivar×stage effects. Potential validation must use homologous gene identifiers, matched biological question and a prespecified direction-of-effect framework.

### Candidate C: GSE190755 — **exclude from drought-treatment differential-expression analysis**
- GEO https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE190755 ; BioProject **PRJNA788400** https://www.ncbi.nlm.nih.gov/bioproject/PRJNA788400 . NCBI GEO lists six samples from six genotypes, **under normal/well-watered conditions**, not paired drought vs control. Study title relates to RNA editing in wheat and root architecture in drought-tolerant/sensitive genotypes. Although its description mentions drought sensitivity, this does **not** mean drought stress was applied in the transcriptome design. It is unsuitable for a within-genotype drought-treatment contrast. Could be contextual baseline only with an explicit separate rationale.
- This is a concrete prevention of **exposure misclassification**.

## Analysis plan: steps that are not yet executed
1. Download the GEO series/sample metadata and SRA run manifest for candidates A and B. Record sample accession, run accession, sample attributes, stage, tissue, cultivar, treatment, replicate, read layout, platform, publication DOI, file size and checksums. **No downloads have occurred in this cycle.**
2. Confirm per-cell replication and whether the original paper's 15 runs map to 15 independent biological samples; exclude technical duplication from biological replicate counts. Identify missing design cell and whether interaction models are estimable.
3. Select an explicit wheat reference assembly and matching annotation (record assembly accession/version, annotation release, index checksums); choose quantification workflow, library strandedness, quality trimming and gene-counting policy after inspecting read metadata. No mapping rate or QC pass claimed yet.
4. Conduct FastQC/MultiQC or equivalent on raw reads, check per-sample read counts, adapters, duplication, GC, strandedness, outliers and sample identity. Reject/flag failed samples before any model fit, with reasons and retained read counts.
5. Construct a count matrix and model with factors genotype, drought, growth stage and **only estimable interactions** for GSE157033. Do not assume a balanced factorial design; assess rank and confounding before interpreting effects. Control multiple testing (Benjamini–Hochberg FDR, prespecified cutoff) and log fold-change shrinkage where appropriate. Document the exact tool/version/parameters and contrast definitions.
6. Analyze GSE226842 separately: perturbation genotype, drought, and interactions if design allows. **Never combine counts across these studies as if same experimental conditions**; any comparison uses clearly specified orthology and cross-study limitations.
7. Validate a short prespecified candidate set with independent external data and/or laboratory qPCR **only if actual data/experiment and permissions exist**. Do not claim a validation experiment or new marker without results.
8. Compare discoveries against Chu et al. (2021), Bouard et al. (2024), and Nouraei et al. (2022; DOI 10.3389/fpls.2022.857829, https://pmc.ncbi.nlm.nih.gov/articles/PMC9005202/) to avoid rediscovery-as-novelty.
9. Package accession-to-sample manifest, raw data hashes, QC reports, analysis scripts, session info, contrast table, FDR and effect sizes, provenance, plots and negative findings before manuscript Results is drafted.

## Original English Methods text (conditional, not a claim of conduct)
> Publicly archived wheat transcriptomic datasets will be evaluated for biological comparability before any joint interpretation. Series will be screened against an explicit genotype–treatment–developmental-stage schema. Drought exposure must be evidenced by sample-level treatment metadata rather than inferred from cultivar labels or stress-tolerance phenotypes. Raw sequencing files and corresponding manifests will be acquired only after confirming availability, sample provenance and reuse conditions. Read-level quality metrics and library properties will determine the downstream preprocessing strategy. Differential-expression contrasts will be specified against the actual observed design matrix, and the estimability of interaction effects will be checked before model fitting. We will control the false-discovery rate across tested genes and separate exploratory findings from externally validated responses. Datasets differing in cultivar, tissue, developmental stage, genetic perturbation or platform will not be treated as biological replicates. Any cross-study validation will be explicitly limited to comparable gene-level directional patterns, with reference annotation and gene-ID mappings recorded.

## Scientific integrity and next action
The existence of accession metadata is **not** proof of completed reanalysis, differential expression, laboratory experiment, novel marker or journal submission. Next necessary step: fetch real sample-level GEO/SRA manifests for A and B, record missing replicate(s), inspect licenses and plan a computational run with known resources. Candidate journal **Frontiers in Plant Science** is not selected or approved for submission. No new article has been submitted.


## C13 sample-level verification — actual 27 GEO Sample records fetched 2026-10-25
**Evidence:** [27-row machine-readable manifest](GEO_VERIFIED_SAMPLE_MANIFEST_27_SAMPLES_2026-10-25.csv), reconstructed directly from NCBI GEO full sample records (`GSE157033&targ=gsm&view=full&form=text` and `GSE226842&targ=gsm&view=full&form=text`). Each row preserves GSM accession, title, cultivar, stage, water treatment, genotype, tissue, BioSample/SRA experiment links and direct GEO URL. Source records, not new expression data.

### A. GSE157033 — exact missing replicate identified
| Cultivar | Stage | Dry | Wet |
|---|---|---:|---:|
| TAM111 | GrainFilling | 2 | 2 |
| TAM111 | Heading | 2 | **1** |
| TAM112 | GrainFilling | 2 | 2 |
| TAM112 | Heading | 2 | 2 |

Total = **15 biological pooled-leaf RNA-seq samples**. The missing cell is **TAM111 / Heading / Wet / replicate 2**; only `GSM4751175` (TAM111_Heading_Wet_rep1) is present in the source records. Do **not** invent an extra sample or pretend this is a balanced 2×2×2×2 design. Pooled leaves from four plants per library are **one RNA-seq biological library** for inferential sample size, not four independent sequencing replicates. A full factorial design with all interactions may have estimability/power limitations. Inspect rank of model matrix and residual degrees of freedom before specifying contrasts, avoid per-cell variance estimation from the singleton cell and do not overclaim three-way interactions.

### B. GSE226842 — unequal treatment/genotype replication, distinct biological context
| Genotype / virus treatment | Well-watered | 7-day drought |
|---|---:|---:|
| WT (no BSMV) | **1** | **1** |
| BSMV empty-vector control | **1** | **1** |
| TaZFP13D overexpression | 2 | 2 |
| TaZFP13D underexpression (siRNA) | 2 | 2 |

Total **12 libraries**. WT and empty-vector BSMV arms have one library per treatment; they **cannot** independently estimate within-arm dispersion. Avoid unsupported differential-expression claims from singleton WT/BSMV comparisons. Tissue = second leaf, cultivar = Atlas66, time = 21 days after germination, drought = seven days withholding water. Contrasts to GSE157033 (flag leaf, two cultivars, two stages, different drought exposure) cannot be treated as equivalent biological replicates. Gene-level external validation must account for gene identifiers, orthology, directionality, independent biological contexts and the original authors' findings.

### Journal scope risk discovered from official publisher (not just a fee check)
Frontiers in Plant Science / Plant Abiotic Stress scope: https://www.frontiersin.org/journals/plant-science/sections/plant-abiotic-stress/about . The section says **descriptive collections of transcripts/proteins/metabolites and basic gene-family description without new biological mechanism are generally not considered** unless extended to reveal biological insight. A routine re-run of DEG counts is therefore not an adequate ZM-R01 paper for this section. The current study must demonstrate a credible novel biological/methodological inference with independent validation or choose a more appropriate journal; **do not invent wet-lab validation**. Official article types https://www.frontiersin.org/journals/plant-science/sections/plant-abiotic-stress/for-authors/article-types : Original Research is a valid type for *actual unpublished primary findings*, not for an unexecuted analysis. Official APC as checked 2026-10-25: CHF **3,150** A-type, only if accepted; https://www.frontiersin.org/journals/plant-science/sections/plant-abiotic-stress/for-authors/publishing-fees . Fee waiver/support eligibility unverified; no expenditure approved.

**Next computational gate:** download actual public expression counts or raw SRA files using the recorded SRX identifiers, verify per-library library-size/QC and wheat reference version, construct design matrix with explicit singleton and batch restrictions, run genuine reproducible analysis, then verify novelty against Chu et al. 2021 and Bouard et al. 2024. No raw read downloads or new DE results have been performed in this cycle.

### C13 source-level data access inspection
The live GEO Series records explicitly advertise downloadable supplements:
- GSE157033: `GSE157033_RAW.tar` and `GSE157033_merged.gtf.gz` under https://ftp.ncbi.nlm.nih.gov/geo/series/GSE157nnn/GSE157033/suppl/ ; associated SRA study **SRP279172**. **RAW.tar is not equivalent to SRA FASTQ**, and contents/size have not yet been downloaded or inspected.
- GSE226842: `GSE226842_TaZFP13D_processed_data.xlsx` under https://ftp.ncbi.nlm.nih.gov/geo/series/GSE226nnn/GSE226842/suppl/ . **This is an available publisher-supplied processed-data workbook, not an independent result from this project**. Attempted direct retrieval through available public-file route was blocked; no workbook analysis performed.
The concrete next data task is obtaining and integrity-checking the public supplements and/or raw SRA FASTQ with exact accession mapping, then deciding a new statistical analysis appropriate for imbalanced replication. No numerical expression estimates are claimed.
