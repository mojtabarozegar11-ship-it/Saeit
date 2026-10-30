# ZM-R01 — Wheat RefSeq release-consistency gate (C118; 2026-10-30)

**Scope:** Independently reusable release-selection acceptance sheet for NCBI IWGSC Chinese Spring RefSeq v2.1 `GCF_018294505.1`. This is an **annotation release audit**, not a wheat sequencing result, differential-expression analysis or validated biomarker.

| QA assertion | Release 100 (2021) | RS_2025_04 update | Test | Status |
|---|---:|---:|---|---|
| Same reference assembly | GCF_018294505.1 | GCF_018294505.1 | exact accession identity | PASS (published reports) |
| Total mRNA features | 142406 | 142414 | 142414 - 142406 = +8 | PASS |
| Known NM_ mRNAs | 0 | 262 | 262 + 142152 = 142414 | PASS |
| Predicted XM_ mRNAs | 142406 | 142152 | 142152 - 142406 = -254 | PASS |
| Coding genes | 103787 | 103793 | 103793 - 103787 = +6 | PASS |
| CDS features | 142442 | 142450 | 142450 - 142442 = +8 | PASS |
| FASTQ reads, sample sheet, QC and replicates | not supplied | not supplied | must verify real BioProject/SRA, library design and FASTQ checksum | **BLOCKED** |

**Release rule:** The 2025 NCBI update reused extant models while adding then-current known transcript placements; the feature deltas are **not** newly sequenced genes, validated variants or new experimental expression evidence. Do not equate CDS feature count with mRNA count. Lock the assembly and the chosen annotation release together; record exact GTF/GFF and FASTA file SHA-256 *after actual download*, never manufacture a checksum. Do not silently mix 2021 and 2025 annotation feature IDs in downstream quantification.

**Source documents:** [NCBI Release 100](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/), [NCBI RS_2025_04](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/), and [C115 source reconciliation](ZM-R01_C115_NCBI_WHEAT_2025_UPDATE_MODEL_REUSE_RECONCILIATION_2026-10-30.md). **Next:** obtain real, consent/provenance-appropriate SRA/FASTQ accession and independent sample sheet; until then ZM empirical manuscript is BLOCKED.
