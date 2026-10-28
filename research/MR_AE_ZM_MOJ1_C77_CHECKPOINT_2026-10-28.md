# R-01 / C77 — ZM parser hardening with executed CI evidence

**Run ID:** R-01-20261028-C77-ZM19  
**Date:** 2026-10-28 (Asia/Tehran)  
**Source of carryover:** [Issue #1514](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514) and [C76 checkpoint](MR_AE_ZM_MOJ1_C76_CHECKPOINT_2026-10-28.md).  
**WIP:** MR author-review pack and ZM-R01 metadata/count-integrity gate; no third work product started.

## Material delivery — ZM-R01 parser, READY_FOR_REVIEW

**Before:** C76 code blob `d495d498b9840f7c46dd8e987ebf62fc34013b16` had 11 unexecuted regression tests; raw integer counts accepted unbounded decimal strings, count matrix gene identifiers could contain whitespace, malformed manifest shapes raised incidental Python exceptions, and GenBank GCA was accepted as a substitute for RefSeq GCF. No CI job executed the newly added tests.

**After:** [preflight source](quality_gates/zm_r01_preflight.py) blob `56ba099f591944a50919c68659eff635e6a8788d`; [19 regression tests](quality_gates/test_zm_r01_reference_preflight.py) blob `29cb4d3bd395341d47229b3f8f70228951063535`; [automatic read-only CI workflow](../.github/workflows/zm-r01-reference-preflight-regressions.yml) blob `80063ae57ee8b8d84e78acec09e55c42569e3f19`.

Five distinct implementation improvements, not five separate final scientific products:

1. Added a branch-scoped automatic Python 3.11 regression workflow for source and test changes; [workflow commit 23df2b6](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/23df2b66637a11991d9de5275d1150b6b06de8dd).
2. Reject raw count values exceeding signed R 32-bit integer range without unsafe conversion of arbitrarily long decimal strings; [code commit 1a0eb2e](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/1a0eb2e90b27cb00b8fc6892a2b0b121239efbfa).
3. Enforce one-to-one count-matrix library columns and nonblank, whitespace-free, unique gene identifiers; same code commit.
4. Reject malformed manifest root/reference/library/count-matrix metadata shapes explicitly and fail closed; same code commit.
5. Require a versioned RefSeq `GCF_` assembly accession rather than silently accepting a GenBank `GCA_` accession; [code commit c94cb06](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/c94cb0600f47bd43b8a8468b5dddcc894ade69ff). This checks accession syntax only, not source identity or assembly version provenance.

**Test and correction chain:** First added six new count tests; [run 40690493178](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40690493178) failed 3/17 because test fixtures mistakenly contained literal backslash-t/newline sequences. Corrected the fixture escapes in [commit 55cbf5b](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/55cbf5b8b193351ca61114cbf867dd5fad065a02); [run 40690583307](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40690583307) passed 17/17. Added two RefSeq accession tests in [commit 9b7eec3](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/9b7eec3abf65010e2d54775e2a5e622d212f9c0c); [final run 40690693179](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40690693179) **SUCCESS: 19 tests, OK**. Python syntax check passed. Final three source/test/workflow blobs were re-read through GitHub.

**Reproduce:** `python -m unittest discover -s research/quality_gates -p 'test_zm_r01_reference_preflight.py' -v`. Synthetic fixtures only test parser rejection; no real FASTQ, reference, count matrix, biological sample or DESeq2 was processed. No 149.54GB download or VPS operation. **Code/CI READY_FOR_REVIEW, scientific ZM analysis BLOCKED.**

## Other carryover — no new scientific acceptance

- **MR:** C76 remains latest reviewed manuscript; publisher-original Car tables and erratum, Amini F7, Cvejić item-level denominator, Lorite/Baroni/Elia full methods, and independent G/D/R/A validation remain open. No new MR article or author signoff.
- **AE:** official WDI 2024/2025/2026 archive URLs are identified in [provenance gate](manuscripts/AE-2026-001/AE-2026-001_WDI_OFFICIAL_ARCHIVES_PROVENANCE_GATE_2026-10-28.md); no historical ZIP bytes/SHA, historic ILOSTAT or countryatlas direct benchmark verified. C13/C14 remain prior work, not new successes.
- **ZM:** exact RefSeq v2.0 FASTA/GTF/checksums, actual FASTQ MD5, independent biological provenance, multimapping, strandedness and raw integer count matrix remain unverified. FPKM and 1,167 hypotheses are NOT DEG/FDR.
- **CV/site:** prior FA/EN CV v2 remains review-only; no new verified credential or staging/live publication.
- **MOJ1:** Gmail search through 2026-10-28 found no new confirmed audit sponsor or independent audit. Private audit artifact 12406875421 is prior completed work, not a new task. No transfer, payment, mainnet deployment or external commitment.

**Final scientific outputs DELIVERED:** 0. **New engineering work product READY_FOR_REVIEW:** 1. **Paper stage transfers:** 0. **New journal submissions:** 0.

**First exact next atomic action:** inspect the latest CI job's tested commit and compare manifest accession and raw-count rules with actual *non-sensitive* source-metadata documentation; obtain original RefSeq v2.0 assembly accession/FASTA/GTF/checksums from official release before accepting a real ZM manifest. In parallel, resume MR Car publisher-original Table 5/6 provenance; never infer a repaired table from the transcription.
