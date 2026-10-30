# ZM-R01 | C124 NCBI wheat reference/annotation version lock

**Usable for:** choosing an explicit public *reference* assembly/annotation pair in a future RNA-seq analysis; **not** a replacement for the missing 24 treatment FASTQ libraries.

| Parameter | Verified source record | Scientific rule |
|---|---|---|
| Species | Triticum aestivum, bread wheat | Do not mix cultivar-specific genomes without alignment justification |
| Assembly | IWGSC CS RefSeq v2.1, **GCF_018294505.1** | Reference FASTA and sequence dictionary must match accession exactly |
| NCBI annotation release 100 | Submitted **2021-10-26**, pipeline 9.0 | Historical gene models and evidence, not 2025 annotations |
| NCBI annotation update | **GCF_018294505.1-RS_2025_04**, submitted **2025-04-18**, pipeline 10.3 | Annotation update on the same assembly; previous models not all recalculated |
| Source type | NCBI automated RefSeq annotations | Do not confuse with distinct IWGSC consortium annotation counts |

**Primary sources:** https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/100/ and https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/ .

## Actual workflow lock (before any quantification)
1. Select *one* release and download its FASTA and compatible GFF/GTF from the same provenance; store URLs, exact file sizes, retrieval date and SHA-256. No files downloaded in this checkpoint.
2. Verify chromosome naming, gene IDs, strandedness, transcript biotype and sequence-dictionary consistency before aligning.
3. Require 24 independently authenticated experimental sample IDs, their factorial treatment/replicate assignments, SRA/FASTQ provenance and SHA-256, with explicit access/consent/rights. The public annotation support samples in C120 are **not** those experiment samples.
4. Never generate differential-expression results, p-values or treatment claims from reference annotations alone.

**Status:** reference choice documented; experiment **BLOCKED** on authentic 24-sample FASTQ/metadata and hash-verified reference files. No VPS or factory operations.
