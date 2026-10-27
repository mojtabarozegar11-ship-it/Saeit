# ZM-R01 C45 — Qualification of an unverified cross-unit multimapping lower bound

**Date:** 2026-10-28. **Status:** internal critical AI correction; **DATA REBUILD / NO SUBMISSION**.

## Original source evidence retained (not rewritten)
- Source pilot run: 40222743342, SRR33083355 / GSM8904963.
- Original archived JSON: `evidence/SRR33083355_independent_qc.json`, blob `3380733b45461e44865cce72d8d420b38fa029d0`.
- Bowtie2 input paired reads: **43,926,311**.
- Concordantly aligned 0 times: **8,137,578**; exactly once: **3,148,686**; more than once: **32,640,047**; these three categories sum to 43,926,311.
- MAPQ-filtered primary first-mate gene-assignment count: **14,357,584** across **58,039** nonzero gene IDs.
- The old JSON asserted `minimum_counted_fragments_from_multimapping_category = 11,208,898`, obtained by subtracting 3,148,686 from 14,357,584.

## Error and correction
The subtraction compares two classification summaries. **It can support a conditional pigeonhole lower bound** if (i) every counted primary, proper first-mate record represents one distinct original input pair from this exact Bowtie2 run, and (ii) the aligner's proper-pair flag corresponds to the reported concordant categories. The count script filters primary proper first mates and therefore supports these assumptions operationally; however, the archived aggregate report does **not independently cross-tabulate counted read IDs with the concordant-once/multiple categories**, and duplicate/flag consistency has not been independently verified at read-ID level. Consequently **11,208,898 is a conditional lower bound, not an independently observed or unconditional counted-multimapper count**.

Bowtie2's manual distinguishes concordant alignment, proper paired SAM flags, and primary/secondary reporting: https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml . MAPQ ≥20 alone does not prove unique placement.

**Corrected conclusions:**
1. The original Bowtie2 alignment pool contains substantial concordant multimapping (**32,640,047 input pairs classified as >1 concordant alignment**).
2. The count file is a genuine one-sample sparse integer-assignment pilot; its row sum does not by itself establish a publication-grade uniquely assigned fragment matrix.
3. A conditional minimum of **11,208,898** counted alignments from the concordant-multiple category follows under the explicit one-primary-first-mate-per-input-pair and same-run concordance assumptions; **the unconditional count-level minimum is not independently verified**. Read-ID/flag cross-tabulation would resolve the evidentiary gap.
4. The old JSON remains historical provenance; its unconditional `minimum_counted_fragments_from_multimapping_category` and categorical `unique_mapping_claim=REFUTED_BY_ORIGINAL_BOWTIE2_SUMMARY` are **qualified**, not erased. Conditional logic is retained separately. The original pilot is not cleared for differential expression.
5. Updated `analysis/audit_original_pilot_artifact.py` emits `minimum_counted_fragments_from_multimapping_category: null` for an unconditional bound, while preserving `conditional_lower_bound_if_one_primary_first_mate_per_concordant_pair: 11208898` and an explicit crosswalk gate. It still fails closed on the assembly, counting-policy and incomplete-matrix gates.

## Release and integrity gates
The original pilot reference is Ensembl Plants release 61 wheat **cDNA**, not proven equivalent to the exact Milec RefSeq v2.0 FASTA+annotation. Only **one** sample has this pilot count table; 24 matched biological count columns, true local FASTQ MD5 verification, strand protocol, validated multimapping policy and independence metadata are missing. No DEG, FDR or 1,167-gene significance claim is authorized.

**Do not** download the 149.54 GB collection, use VPS, spend money, infer author approval or submit. Corrective changes are limited to the draft research branch.
