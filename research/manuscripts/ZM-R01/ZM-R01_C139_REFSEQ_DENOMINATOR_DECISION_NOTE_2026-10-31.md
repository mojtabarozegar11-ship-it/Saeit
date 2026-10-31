# ZM-R01 C139 — wheat RefSeq gene/transcript denominator decision note

**2026-10-31 | R-01 | READY_FOR_REVIEW annotation arithmetic; FASTQ biological inference BLOCKED**

Input: [C136 NCBI feature-class contract](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/research/mr-2026-001-novelty-audit/research/manuscripts/ZM-R01/ZM-R01_C136_NCBI_REFSEQ_FEATURE_CLASS_CONTRACT_2026-10-31.csv), referencing [NCBI RefSeq wheat annotation GCF_018294505.1-RS_2025_04](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/). Values are **prior source-report transcriptions**, not a fresh NCBI download in this run.

| Source-defined class | Count | Unit / valid use |
|---|---:|---|
| Protein-coding loci | 103793 | Gene loci |
| Noncoding gene loci | 32609 | Gene loci |
| Non-pseudogene gene loci | 136402 | 103793 + 32609 |
| Pseudogene loci | 19065 | 448 transcribed + 18617 nontranscribed |
| All gene/pseudogene loci | 155467 | 136402 + 19065 |
| Non-pseudogene annotated transcripts | 224459 | 142414 mRNA + 82045 ncRNA; **not** independent gene loci |

**Validated arithmetic:** all four integer identities reconcile exactly against the C136 source transcription. Gene loci, pseudogene loci and transcript isoforms are **not exchangeable denominators**. The pseudogene fraction of the inclusive locus total is 12.263053% (derived description only; not an expression result). Annotations from this assembly/release must not be silently combined with another RefSeq assembly or version.

**Fail-closed FASTQ gate:** the previously specified **24 real FASTQ files**, sample metadata, read-pair checksums, mapping/quantification outputs and quality metrics were not supplied or verified here. Therefore **zero** RNA-seq differential-expression, genotype, pathway or treatment-effect conclusions are authorized. Next action: recover accession-to-sample manifest and SHA-256 of each raw FASTQ, confirm biological replicate identities and assembly compatibility, then perform read QC/quantification on the authorized non-factory environment.
