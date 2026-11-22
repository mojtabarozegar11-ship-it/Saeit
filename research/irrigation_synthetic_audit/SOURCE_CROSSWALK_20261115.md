# R01 — audited source crosswalk, scientific interpretation and release limits
Internal technical document; inspected 2026-11-15. **Not a field experiment, publication, or submission.**

## Original author-controlled source
Google Sheets workbook: `ZM-IRR-MODEL-2026-01 — Research Data Workbook — 4260 Records`.
Source: https://docs.google.com/spreadsheets/d/1NC1pgdb1Dkhk1HdgdF_sFvnx1i86O88u_fgVdxvvKQA/edit

The workbook's `Overview` tab lists 480 baseline rows, 1,620 Cohort C rows,
2,160 Regime R1 rows, and 480 separate forensic plot-day diagnostic rows.
The baseline and the two policy archives sum to **4,260 rows**. The forensic
trace must **not** be added a second time to that 4,260 denominator.
This table reports the original workbook's own declared counts, checked
against tab dimensions; it is not an independent reproduction of the model.

| Workbook tab | Sheet grid | Observed header | Observed first scenario ID |
| --- | ---: | --- | --- |
| `CohortC1620` | 1,621 rows / 12 columns | 12 expected metric fields | `C-dry-1` |
| `RegimeR2160` | 2,161 rows / 12 columns | 12 expected metric fields | `R-dry-1` |
| `Baseline480` | 481 rows / 16 columns | not ingested by this postprocessor | Not inspected here |
| `ForensicTrace480` | 481 rows / 21 columns | diagnostic unit, not independent trials | Not inspected here |
| `DecisionWeights` | 550 rows / 16 columns | paired sensitivity table | Not observational |

**Critical source-code mismatch fixed:** the Python logical family key is `R1`,
but the REAL workbook cohort strings begin `R-`, not `R1-`.
The synthetic test generator formerly produced `R1-` and therefore hid the
real-input failure. The production-family prefix is now checked against `R-`
and the test fixture reproduces this observed naming convention.

## Source cells transcribed only as audit checkpoints

The worksheet `DecisionWeights!H1:P10` was read directly. These are workbook
outputs, **not independently re-simulated estimates**.

| λ (m³ per simulated Q-day) | C v3 / v2 / tie | C mean ΔL | R v3 / v2 / tie | R mean ΔL |
| ---: | --- | ---: | --- | ---: |
| 0 | 20 / 383 / 137 | 36.068955967 | 13 / 401 / 126 | 30.575281425 |
| 10 | 196 / 255 / 89 | -32.856969959 | 193 / 253 / 94 | -44.128422279 |
| 100 | 222 / 229 / 89 | -653.190303292 | 214 / 232 / 94 | -716.461755612 |

ΔV = V(v3) − V(v2), ΔQ = Q(v3) − Q(v2);
the illustrative loss difference is ΔL = ΔV + λΔQ. These are paired
**descriptive** differences on a structured, factorial synthetic grid. The
choice of λ is illustrative, not a verified farmer willingness-to-pay measure.
Because modeled water is in cubic metres and Q is a count of simulated
threshold plot-days, λ has dimensions cubic metres **per** threshold plot-day,
not currency. Drainage remains a depth in millimetres and cannot be
relabelled as cubic metres without an area conversion.

## 20 independently identified scientific/data gates

The evidence column distinguishes a guard **present in code** from a
validation **executed on the complete author-held archive**. These are NOT
20 proven farm outcomes or a claim that 20 tests already passed.

| # | Gate | Evidence / remaining condition |
| --- | --- | --- |
| 01 | Controlled source provenance | Original workbook title, tab names and URL sampled directly |
| 02 | Cohort C denominator | 1,620 full workbook data rows read; independent descriptive postprocessing completed; generator replay pending |
| 03 | Regime R1 denominator | 2,160 full workbook data rows read; independent descriptive postprocessing completed; generator replay pending |
| 04 | Avoid forensic trace double count | 480 diagnostic rows excluded from 4,260 in workbook Overview |
| 05 | Exact source column names | 12 header fields matched by live read |
| 06 | Real R1 cohort prefix | `R-` observed and corrected in code and test fixture |
| 07 | Family policy cardinality | 3 C / 4 R policy names enforced in parser |
| 08 | Repeated-key identity | Cohort, seed, climate, bias, ET and forecast case paired |
| 09 | Duplicate policy-key prevention | Rejects duplicate rows in analyzer |
| 10 | Factorial-grid completeness | 5×3×3 combinations for each path, 4 dry/4 medium/4 wet per family now enforced; full live data passed |
| 11 | CSV header uniqueness | Rejects duplicate source header names |
| 12 | CSV record width | Now rejects overlong records rather than ignoring surplus values |
| 13 | Finite values and ranges | Numerical and water-cap checks in source loader |
| 14 | Unit preservation | Gross-water m³ separate from drainage millimetres |
| 15 | Simulated stress-count bounds | Q and below-98 count relation checked |
| 16 | Matched ΔV and ΔQ sign | Defined as v3 minus v2; paired in code |
| 17 | Full Pareto partition | Reverse tradeoff category now counted; partition checks 540 |
| 18 | Undefined crossing statistic | No crossover produces null, never a fabricated median |
| 19 | Dependence across climate paths | Twelve path-level mean paired effects now emitted separately |
| 20 | Decision-weight sensitivity | Eight weights enumerated; sample λ=0/10/100 crosschecked |
| 21 | Source SHA-256 | Hashing implemented for ingested exact CSV bytes; hashes not recovered from original Sheet here |
| 22 | Manuscript checkpoint comparison | Full-sheet independent JavaScript postprocessing of 3,780 rows agrees with all 64 decision-weight table checkpoints; Python CLI replay pending |
| 23 | Generator replay | Recovered C and R generators exist in **private Karegar**; no fresh complete C/R replay was executed in this PR review |
| 24 | Weather and soil calibration | NOT FIELD VALIDATED |
| 25 | Crop yield / causal benefit | NOT ESTABLISHED |
| 26 | Independent cluster uncertainty | NOT ESTABLISHED; 12 paths, not 540 independent farms |
| 27 | External scientific source | FAO-56 and Cameron–Miller references verified at publisher/author-linked pages |
| 28 | Software regression suite | 40 test methods now authored in PR; execution status requires specific job logs |
| 29 | Manuscript/editorial review | NOT COMPLETED |
| 30 | External publication and licensing | NOT AUTHORIZED; requires owner-specific approval |

## Real scientific references — contextual, not validation of this model
1. Allen RG, Pereira LS, Raes D, Smith M (1998). *Crop
   evapotranspiration—Guidelines for computing crop water requirements*.
   FAO Irrigation and Drainage Paper 56, Rome, FAO.
   Original agency catalog/full text:
   https://www.fao.org/4/X0490E/X0490E00.htm
   This supplies conceptual reference-ET and crop-water methodology;
   it does **not** verify the archived scenario model's weather or sensor inputs.
2. Cameron AC, Miller DL (2015). *A Practitioner's Guide to Cluster-Robust
   Inference*. *Journal of Human Resources* 50(2), 317–372.
   DOI https://doi.org/10.3368/jhr.50.2.317
   This informs the warning about pseudo-replication and few clusters;
   a numerical inference procedure has **not** been specified or run here.

## Gated next verification, no cost or distribution
1. Obtain exact frozen CSV snapshots from author-controlled bundle without publishing them.
2. Run all 40 regression test methods against this PR head and capture command, Python version, stdout and exit code.
3. Retrieve the recovered generator and offline verifier from the **private** Karegar records below; replay the two synthetic families on a controlled computer; compare against frozen CSV/TSV snapshots and all declared checkpoints.
4. Audit path-level deviations/outliers without incorrectly treating factorial keys as independent trials.
5. Verify the weather/controller generator source or explicitly publish the replay limitation (only with final owner approval).
6. Freeze manuscript, source references, disclosures, byline and editor-facing package; **do not submit** without explicit approval.

## Private generator recovery discovered during this review

The user's **private** `Karegar` repository already stores the recovered original-model
implementations and an offline archival comparator:

- `research/irrigation/B29_recovered_C_original_generator_2026-11-14.mjs`
- `research/irrigation/B29_recovered_R1_original_generator_2026-11-14.mjs`
- `research/irrigation/B29_archive_reproduction_verifier.mjs`
- `research/irrigation/B25_generator_reproduction_2026-11-14.md`

These are *not* published here. Their private source comments explicitly say
that modeled rain and ET are synthetic. The B25 report documents earlier
successful baseline comparison (480 rows, 6,240 field checks), **not** a
verified execution of the full C/R experiment in this review. The B29
offline comparator requires authenticated original TSV export files and
Node.js. Possession of a verifier is not a record of its successful execution.

**Critical fairness limitation:** the recovered C/R forecast construction
uses realized `w.rain` for the `perfect` and `falsePositive`
information cases at the decision step. Without historical forecast
issue-time records, that is a modeled perfect-information comparator,
not proof that a real farm would know rainfall in advance. This must be
made explicit in manuscript methods and commercial claims, even if every
synthetic archive check passes. Independent field and economic evidence
remain absent.

## Full live-source arithmetic audit completed this review (not model replay)

A separate read-only JavaScript analysis over bounded native Sheets ranges
`CohortC1620!A1:L1621` and `RegimeR2160!A1:L2161`
processed **all 3,780 synthetic outcome rows** in the original workbook
directly through the connected Google Sheets interface (unformatted numeric
cells). It did not rely on the archived static `EXPECTED` constants, and did
not run or modify the weather/controller model.

| Source-derived result | C | Regime R1 |
| --- | ---: | ---: |
| Rows read | 1,620 | 2,160 |
| Unique matched 3/4-policy keys | 540 | 540 |
| Climate paths | 12 | 12 |
| Factorial settings per climate path | 45 | 45 |
| Paths by class dry/medium/wet | 4/4/4 | 4/4/4 |
| Duplicate/invalid records in the implemented structural scan | 0 | 0 |
| Mean paired Δwater (m³), v3−v2 | 36.068955967 | 30.575281425 |
| Mean paired ΔQ, v3−v2 | -6.892592593 | -7.470370370 |
| Pareto categories summed | 540 | 540 |
| Median finite crossover λ (m³/Q-day) | 2.841907237 | 1.372369279 |

The independent scan checked allowed climate, bias, ET and forecast categories;
finite quantitative values and threshold bounds; unique paired keys; complete
policy families; complete per-path factorials; all paired differences and all
five disjoint Pareto categories. Zero structural anomalies were observed
**under these specific checks**. This does not exclude untested model-design
problems or validate source archive generation.

The `DecisionWeights!H1:P9` cells were independently read and compared for
all eight λ values in each of two families: **64 scalar comparisons** (v3
preferred count, v2 preferred count, tie count, mean ΔL), **zero mismatches**
at 10⁻⁶ precision; maximum absolute difference in mean ΔL was
9.095×10⁻¹³ (R) and 5.684×10⁻¹³ (C) from floating-point arithmetic.
These are self-consistency calculations on the native workbook, **not**
independent field measurements, causal estimates, or a controller replay.

**Additional structural correction after full-sheet inspection:** enforce
the observed 4/4/4 dry/medium/wet balance per family. Earlier code only
required twelve paths and could have accepted an inadmissible 5/4/3 split.
A regression method was added.

No raw workbook values or export bytes were posted in this document. The
source remains author-controlled and the entire numeric comparison is
restricted to descriptive synthetic outcomes.
