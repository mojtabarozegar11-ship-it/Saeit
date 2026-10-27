# ZM-R01 C45 — Correction: invalid cross-unit multimapping lower bound

**Date:** 2026-10-28. **Status:** internal critical AI correction; **DATA REBUILD / NO SUBMISSION**.

## Original source evidence retained (not rewritten)
- Source pilot run: 40222743342, SRR33083355 / GSM8904963.
- Original archived JSON: `evidence/SRR33083355_independent_qc.json`, blob `3380733b45461e44865cce72d8d420b38fa029d0`.
- Bowtie2 input paired reads: **43,926,311**.
- Concordantly aligned 0 times: **8,137,578**; exactly once: **3,148,686**; more than once: **32,640,047**; these three categories sum to 43,926,311.
- MAPQ-filtered primary first-mate gene-assignment count: **14,357,584** across **58,039** nonzero gene IDs.
- The old JSON asserted `minimum_counted_fragments_from_multimapping_category = 11,208,898`, obtained by subtracting 3,148,686 from 14,357,584.

## Error and correction
That subtraction compares **different classification units**. The Bowtie2 categories summarize *concordant paired-end alignment multiplicity*, whereas the count script filters *primary first-mate SAM records* with a MAPQ threshold and a proper-pair flag, then maps transcripts to genes. The aggregate Bowtie2 summary is **not a cross-tabulation of those 14,357,584 counted records** by alignment multiplicity. Consequently the difference **11,208,898 is descriptive arithmetic, NOT an identified minimum number of counted multimappers**.

Bowtie2's own manual distinguishes concordant paired alignment, discordant and mixed-mode alignments and primary/secondary reporting: https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml . A MAPQ threshold is also not a mathematical proof of unique concordant mapping.

**Corrected conclusions:**
1. The original Bowtie2 alignment pool contains substantial concordant multimapping (**32,640,047 input pairs classified as >1 concordant alignment**).
2. The count file is a genuine one-sample sparse integer-assignment pilot; its row sum does not by itself establish a publication-grade uniquely assigned fragment matrix.
3. The fraction or minimum number of **counted** multimappers is **not identifiable** from the aggregate summaries alone; record-level pairing/alignment evidence would be required.
4. The old JSON must remain as historical provenance, but its `minimum_counted_fragments_from_multimapping_category` and `unique_mapping_claim=REFUTED_BY_ORIGINAL_BOWTIE2_SUMMARY` are **superseded for count-level inference**. The original pilot is not cleared for differential expression.
5. Updated `analysis/audit_original_pilot_artifact.py` emits `minimum_counted_fragments_from_multimapping_category: null`, `counted_multimapping_lower_bound: NOT_IDENTIFIABLE_FROM_AGGREGATE_SUMMARIES`, and `unique_mapping_claim: NOT_ESTABLISHED_FOR_COUNTED_FRAGMENTS`. It still fails closed on the assembly, counting-policy and incomplete-matrix gates.

## Release and integrity gates
The original pilot reference is Ensembl Plants release 61 wheat **cDNA**, not proven equivalent to the exact Milec RefSeq v2.0 FASTA+annotation. Only **one** sample has this pilot count table; 24 matched biological count columns, true local FASTQ MD5 verification, strand protocol, validated multimapping policy and independence metadata are missing. No DEG, FDR or 1,167-gene significance claim is authorized.

**Do not** download the 149.54 GB collection, use VPS, spend money, infer author approval or submit. Corrective changes are limited to the draft research branch.
