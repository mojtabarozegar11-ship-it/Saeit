# ZM-R01 | C134 NCBI wheat reference feature-denominator adjudication

**Date/source checked:** 2026-10-31; original [NCBI Triticum aestivum Annotation Report GCF_018294505.1-RS_2025_04](https://www.ncbi.nlm.nih.gov/refseq/annotation_euk/Triticum_aestivum/GCF_018294505.1-RS_2025_04/). **State: verified reference metadata; no FASTQ data or expression results.**

## Reconciled source categories

| NCBI annotation category | Source count | Valid interpretation |
|---|---:|---|
| Protein-coding genes | 103,793 | Gene loci annotated as protein-coding; not independent biological samples |
| Non-coding genes | 32,609 | Non-coding gene loci |
| **Genes excluding pseudogenes** | **136,402** | 103,793 + 32,609; NCBI detailed feature-length table's Genes count |
| Transcribed pseudogenes | 448 | Pseudogene class, not additional coding genes |
| Non-transcribed pseudogenes | 18,617 | Pseudogene class |
| **Pseudogenes total** | **19,065** | 448 + 18,617 |
| **Genes and pseudogenes** | **155,467** | 136,402 + 19,065; broad annotation feature count, **not** protein-coding genes |
| mRNAs | 142,414 | Transcripts, can exceed protein-coding gene count |
| Non-coding RNAs | 82,045 | RNA features, not automatically independent gene loci |
| All transcripts in detailed table | 224,459 | 142,414 + 82,045; excludes separate pseudo transcripts from this specific detailed-table definition |
| Pseudo transcripts | 448 | Separate pseudogene-derived transcript count |

**Primary-source consistency checks:** 103793+32609=136402; 448+18617=19065; 136402+19065=155467; 142414+82045=224459. This reconciles the apparent 136,402-versus-155,467 discrepancy as **different feature inclusion rules**, not evidence of an annotation defect. Gene-locus, transcript and pseudogene denominators must not be mixed in downstream expression analysis.

## Implementation gate for ZM-R01

Reference assembly: IWGSC CS RefSeq v2.1 / GCF_018294505.1, with 22 assembled chromosomes **plus unplaced scaffolds**. Annotation update GCF_018294505.1-RS_2025_04; pipeline 10.3; previously current model transcripts were retained, not recalculated. For differential-expression testing, define the count unit (gene locus or transcript), the transcript-to-gene aggregation mapping and the explicit exclusion/inclusion of pseudogenes and noncoding features **before** running the analysis. Freeze FASTA, GFF/GTF, transcript-to-gene mapping, annotation release, SHA-256 and exact provenance. Check identifiers and coordinate conventions.

The planned 24-library experiment is **BLOCKED**: no authenticated FASTQ, sample-level biological metadata, library layout, replicates, or matching reference FASTA/GFF bytes have been supplied. These source statistics do not establish RNA-seq quality, treatment response, significance or gene expression. No synthetic reads or invented results have been generated.

**Next:** receive legitimate sample manifest and 24-library FASTQ hashes; download matched reference and validate source/feature IDs offline; pre-register sample-level design and independent biological replicate structure. Owner R-01 retains scientific review; no publication without author approval.
