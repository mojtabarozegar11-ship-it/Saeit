# ZM-R01 C24 — All 24 GEO GSM ↔ BioSample ↔ ENA SRR joins resolved from original deposited metadata

**Date:** 26 October 2026. **Status:** primary-source crosswalk **COMPLETED**; expression analysis and journal release **BLOCKED**. No paid compute or VPS involved.

## Completed primary-source reconciliation

A new independent, fail-closed script `analysis/official_geo_biosample_srr_crosswalk.py` downloaded the original NCBI GEO family SOFT for GSE294406 and parsed each individual `^SAMPLE` block and its deposited `!Sample_relation` BioSample (or independently joined SRA experiment if required). It joined the deposited BioSample identifiers to the existing ENA 24-run manifest **by identifier, never by ordering of GSM or SRR accession numbers**. It required a 24-of-24 GEO accession set, identical source sample titles, unique one-to-one joins, and the independently confirmed pilot anchor `GSM8904963 ↔ SAMN47891443 ↔ SRR33083355`.

**Evidence:**
- Source GEO family SOFT: https://ftp.ncbi.nlm.nih.gov/geo/series/GSE294nnn/GSE294406/soft/GSE294406_family.soft.gz
- Original GEO SOFT compressed SHA256: `a31012eccc1f1c128a4b322b7d80981814e7a297726e753148579324276adc58`.
- Original ENA 24-run TSV SHA256: `2fcddb8a8a789ef11048e6d35b8227e63287a92dec176cbb02d0f4d4bcaffe64`.
- GitHub Actions successful run: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40260457907 ; all source-crosswalk steps succeeded.
- Exact source crosswalk artifact: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40260457907/artifacts/12624033508 ; includes 24-row, 48-MD5-field TSV and source-hashed JSON.
- Permanent compact accession crosswalk: `GSE294406_24_GSM_BIOSAMPLE_SRR_VERIFIED_CROSSWALK_2026-10-26.tsv` (24 rows, 24 unique GSM, 24 unique BioSample, 24 unique SRR).
- Original 24-run ENA manifest: `ENA_PRJNA1249400_OFFICIAL_24_RUN_PAIRED_FASTQ_MD5_2026-10-25.tsv`.

**Validated scientific result:** all 24 GEO samples now have independently deposited and one-to-one verified BioSample and SRR identities; the former 23 missing joins are resolved. The 2×2×2 factorial sample labels can now be joined to the original 24-run sequencing manifest without guesswork.

**Critical limits:** the 48 paired FASTQ MD5 strings were validated for **presence and syntax**, not by downloading and hashing all 48 files. No new FASTQ was downloaded; no new alignments, counts, differential expression, FDR, sample-level QC, transcript-to-gene aggregation or reference equivalence were produced. The original one-sample MAPQ>=20 pilot is **not** uniquely mapped gene-count evidence, as established in C22.

## Next required gates, not completed

1. Resolve the exact published Milec 2025 reference build, transcript annotation and gene-ID namespace from primary full methods. Select one compatible genome/annotation build and preserve accession, release and source hashes. Do not conflate Ensembl ordinary IWGSC v1.0 with IWGSC RefSeq v2.0 or v2.1.
2. Establish read-pair/strandedness/multimapper policy (e.g. genome-aware alignment with uniquely assigned fragments explicitly separated from ambiguous multi-locus reads) and ensure gene-level counts are nonnegative **integers** and reproducible. Do not silently count multi-mappers as uniquely assigned.
3. Verify 48 actual FASTQ MD5s as downloaded within available no-cost hosted resources, preferably resumably; check computational feasibility before transferring approximately 150 GB. Never use the VPS without a separate approved resource plan.
4. Build 24-library gene-count matrix under the **same reference and pipeline**, check sample swaps/outliers and exact 24-sample mapping, then fit `DESeq2 ~ D*H*C` with prespecified contrasts and multiplicity-adjusted FDR.
5. Independently compare the new scientific question and resulting evidence against Milec 2025. A repeat analysis without a distinct supported contribution is not an original paper.

**Release gate:** no claim of published DEGs, FDR, biological novelty, human author approval or journal submission. This C24 record supersedes only the *23 unresolved accession joins* reported in C23; all other C23 scientific safeguards remain mandatory.
