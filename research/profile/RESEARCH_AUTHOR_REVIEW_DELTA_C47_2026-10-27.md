# Author review delta — C47, 27 October 2026

**Internal AI critical assessment; no human author, independent reviewer, approval, submission or publication claim.**

## MR-2026-001 — source-specific correction for Cvejić (2020)

New C47 audit re-expresses published Tables A6/A8 as modeled volume-weighted savings: **22.5506% (2017), 28.4722% (2018), 20.5771% (2019), pooled 23.6621%**. The source reports unweighted annual farm-level percentage means **26.29%, 32.96%, 22.16%**. These are different denominators, not contradictory experimental results. Source appendices have 35 listed farm IDs but three wholly missing modeled rows (22, 28, 30), so **32** usable modeled farm rows; do **not** infer that 32 is the survey denominator for 83% IDSS use. Model-based scenarios are not observed savings. Source: https://doi.org/10.3390/agronomy10091238 and full-text copy linked in [C47](../manuscripts/MR-2026-001/MR-2026-001_C47_CVEJIC_MODELED_SAVINGS_FARM_VS_VOLUME_WEIGHTED_DENOMINATORS_2026-10-27.md).

**Adversarial challenge:** The denominator distinction is valid algebraically but depends on appendix aggregate transcription from an open full-text copy. Reconfirm against publisher typeset original; confirm missing-farm reason and telephone survey response count with original authors before making a definitive denominator assertion. C47 neither validates G/D/R/A nor solves Car Table 5, Amini residual values, Lorite/Baroni/Elia full methods or novelty. Status **MAJOR REVISION / NO SUBMISSION**.

## AE-2026-001 — release gates unchanged

C13/C14 availability-mask distinction must remain explicit: 153 2026-only three-endpoint cases, 169 2019/2023 cases, 155 separate historical-vintage fixed-cohort cases. C14 was re-read from the research branch in this cycle; the precise C13 path was not authenticated. No new archived 2024/2025 ILOSTAT source or three-vintage direct countryatlas comparator was verified. Avoid claims of source independence, revision mechanisms or new estimator. Status **MAJOR REVISION / NO SUBMISSION**.

## ZM-R01 — release gates unchanged

No exact validated RefSeq v2.0 FASTA/annotation/checksum pair, raw FASTQ MD5 audit, multimapping policy, independently verified experimental units or integer-count matrix. FPKM and 1,167 exploratory hypotheses are **not** DESeq2 DEG/FDR results. No bulk 149.54 GB download, VPS or cost. Status **DATA REBUILD / NO SUBMISSION**.

## Human owner decision required before any journal action

Verify actual intellectual contribution and author list, final scientific version, identity and affiliation, funding/COI/AI disclosures, permissions and rights, selected journal/APC and cover letter. Do not fabricate a signature, DOI, manuscript ID or endorsement. No submission or payment has been initiated. This packet is internal research staging only; no live site changes or PR #1054 merge.

**New AE C32 method correction (this cycle):** Official countryatlas documentation shows `compare_vintages` compares **single-year indicator levels**, so a genuine 2000–2019 growth-vintage benchmark requires separate 2000/2019 calls, an ISO3+vintage join and matching archive release identities. The prior successful `growth_rate(type='cagr')` calculation does **not** close this gate. The consolidated AE author-review manuscript now states this limitation. See [C32](../manuscripts/AE-2026-001/AE-2026-001_C32_COUNTRYATLAS_COMPARE_VINTAGES_ESTIMAND_AND_RELEASE_IDENTITY_GATE_2026-10-27.md). No actual three-vintage execution is claimed.


**ZM C35 metadata clarification:** The Ensembl Plants archive page with URL slug `Triticum_aestivum_refseqv2` explicitly reports **IWGSC_RefSeq_v2.1** and assembly accession **GCA_018294505.1**, not v2.0. This new source-level observation prevents treating the website slug as proof of the assembly used by Milec. Exact source FASTA/GTF/checksum remain unknown; see [C35](../manuscripts/ZM-R01/C35_ENSEMBL_REFSEQV2_SLUG_V21_ASSEMBLY_IDENTITY_GATE_2026-10-27.md). No RNA reanalysis or inferred DEG.


## 27 October addendum — C48 full-text GesCoN model lineage

The [C48 original-publisher audit](../manuscripts/MR-2026-001/MR-2026-001_C48_GESCON_2015_FULL_METHOD_MODEL_VALIDATION_VS_2022_FIELD_ADOPTION_2026-10-27.md) establishes that the open-access 2015 GesCoN Part I article already describes daily irrigation/nitrogen scheduling, while Part II reports five calibration and 13 validation datasets for **crop-model predictions**, not farmer recommendation-event adherence. The 2022 commercial-farm study is a separate evidence layer; full 2015 methods cannot validate its 2022 field allocation, event implementation or adoption. The MR Perspective now cites the 2015 original-publisher articles as references 23–24 and explicitly rejects novelty claims based on daily scheduling or crop-model validation. This **does not close** the original full-method gate for the 2022 Elia application or Lorite/Baroni, nor demonstrate empirical G/D/R/A validity. Human approval and all release gates remain outstanding; no journal submission or live deployment.
