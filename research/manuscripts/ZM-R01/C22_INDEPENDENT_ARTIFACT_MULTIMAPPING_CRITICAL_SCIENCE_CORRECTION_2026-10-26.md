# ZM-R01 C22 — critical independent QC: original pilot is NOT uniquely mapped

**Independent direct examination of the actual downloaded ZIP** [artifact 12618285422](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40222743342/artifacts/12618285422), performed **26 October 2026**. The ZIP contained all five advertised files, including original Bowtie2 `alignment_summary.txt`, `provenance.json`, the integer TSV and original ENA source hashes. This supersedes any description of all 14.36 million counted fragments as **uniquely mapped**.

## Original Bowtie2 paired-read categories (not inferred)

| Original output | Read pairs | Percent of input |
|---|---:|---:|
| Input pairs | **43,926,311** | 100% |
| Concordantly aligned 0 times | **8,137,578** | 18.53% |
| Concordantly aligned exactly once | **3,148,686** | 7.17% |
| Concordantly aligned >1 times | **32,640,047** | 74.31% |
| Overall alignment rate | — | **81.47%** |

These four counts are read directly from the original `alignment_summary.txt`. The three alignment categories sum exactly to the original input count: 8,137,578 + 3,148,686 + 32,640,047 = 43,926,311.

## Independent integer-table examination

The original sparse TSV has **58,039 unique gene IDs** with positive integer values, **no duplicate IDs**, **no zero/negative entries**; the sum of counts is **14,357,584**, identical to the original `provenance.json` value for `gene_assigned_fragments`. The largest single gene count is **119,105**, median nonzero count **49**, and **3,265** gene rows have a count of one. This establishes internal arithmetic integrity of the table, not unique-mapping biological validity.

**Critical mathematical inconsistency:** the table assigns **14,357,584** fragments, whereas only **3,148,686** read pairs were aligned concordantly exactly once. Therefore, **at least 11,208,898 counted fragments** must have originated from the original Bowtie2 category of pairs with multiple concordant alignments, if one counted fragment corresponds to one original read pair as the pipeline asserts. The output's `counts_type` label `integer conservative uniquely mapped proper paired fragments` is **not defensible as an assertion of strict unique concordant mapping**.

Bowtie2's [official manual](https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml) explains that MAPQ is an estimated mapping-confidence score; a MAPQ threshold of 20 is **not identical** to a declaration that only one concordant placement exists. Bowtie2 normally reports a preferred alignment even when multiple placements were found. Filtering `samtools view -q 20` therefore cannot by itself justify the original unique-mapping label. This is especially consequential for a polyploid wheat transcriptome with homologous transcripts.

## Release decision and corrective implementation

- **PASS:** original ENA paired FASTQs passed MD5 in original run; genuine integer values were computed from real alignments; TSV sums and gene IDs pass direct arithmetic checks; first-sample computational feasibility established.
- **FAIL:** strict unique-concordant-pair claim. The sample cannot be called a uniquely mapped gene-count matrix. It also has no verified RefSeq v2.0/2.1 assembly equivalence, no 24-sample cohort and no valid differential expression.
- The [independent auditor](analysis/audit_original_pilot_artifact.py) now parses all four Bowtie2 categories and writes `unique_mapping_claim = REFUTED_BY_ORIGINAL_BOWTIE2_SUMMARY`, `minimum_counted_fragments_from_multimapping_category = 11208898` and `scientific_release_gate = BLOCKED_MULTIMAPPING_AND_ASSEMBLY`. Structural QC may succeed, but the publication release gate remains **closed**.
- **Corrective pipeline before 24-library production:** establish the exact original-study-compatible assembly and GTF/GFF gene IDs, define a consistent gene-level multimapping rule and use a suitable paired-end genome aligner with a documented unique-assignment criterion (or a justified transcript quantification model with correctly labeled estimated counts). Reprocess **all 24** original libraries under that same method. Do not relabel MAPQ-filtered transcriptome assignments as strict unique reads. Predefine gene count and library QC, biological replicate metadata, factorial DESeq2 design `~ D*H*C` and FDR procedure.
- **No paid compute, VPS, original-run cancellation or journal submission** is authorized by this scientific correction.

**Result:** one authentic technical milestone (one-sample counts) **and one independently demonstrated methodological failure**. The failure is a real result of the audit, **not a successful completion of publication-grade counts**.
