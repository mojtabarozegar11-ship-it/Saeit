# R01 — Scientific interpretation and submission gate (15 November 2026)

**Status:** Internal author review; not a submitted, accepted, or field-validated article.

## Study unit and estimand

The archived 1,620-row C and 2,160-row R1 datasets encode simulated policy–scenario outputs, with respectively three and four policies on 540 matched keys per family. Each key combines a climate path, seed, climate class, soil-sensor bias, evapotranspiration forecast factor and rainfall-information case. The 540 keys are *not* 540 independently sampled farms. Inferences must respect repeated climate paths and factorial dependence.

For policies A and B on identical scenario keys i, define the paired descriptive difference in gross irrigation water as

\[\Delta_V = N^{-1}\sum_{i=1}^{N}(V_{A,i}-V_{B,i}).\]

Likewise, define \(\Delta_Q\) for the simulated stress-proxy count. The sign convention must be reported with policy names in every table; a negative Q difference cannot be labeled a field-observed crop benefit.

## Table — verified scope versus unresolved validation

| Claim | Existing evidence in PR #1999 | Permitted interpretation | Required next evidence |
| --- | --- | --- | --- |
| C archive size | 1,620 output rows; three policies; 540 keys | Structured synthetic scenarios | Raw generator configuration and replay |
| R1 archive size | 2,160 output rows; four policies; 540 keys | Structured synthetic scenarios | Raw generator configuration and replay |
| Numerical checkpoints | Author-reported postprocessor agreement to six decimals | Internal arithmetic consistency only | Independent rerun on frozen inputs and reviewer-signed table |
| Q100 proxy | Simulated end-storage threshold count | Proxy, not observed yield or stress | Crop-specific validation if agronomic claims are proposed |
| Water outcomes | Simulated gross-water outputs | Model-relative comparisons | Field metering and uncertainty calibration for real-world claims |
| Decision weights | Eight illustrative post hoc weights | Sensitivity illustration, not prices | Pre-specified decision rationale and robustness checks |
| Financial outcomes | None established by this audit | No profit or revenue claim | Costs, price assumptions, uncertainty and external data |

## Statistical reporting restrictions

1. Report paired **descriptive** summaries, not farm-level independent-sample significance tests on the 540 keys.
2. Identify the 12 climate paths as a dependence source. If uncertainty intervals are later reported, specify resampling at the climate-path level and explain the very small number of independent path clusters.
3. Separate pre-specified hypotheses from the eight explored decision weights; avoid treating the best-looking weight as confirmatory.
4. State units, scenario denominators, policy direction, thresholds, and rounding in every manuscript table.
5. Preserve the exact CSV SHA-256 hashes, code revision, Python version, and complete CLI invocation with the author-controlled reproducibility bundle.
6. Distinguish structural model uncertainty from within-grid sensitivity; factorial scenarios do not establish external validity.
7. Do not claim that six-decimal checkpoint agreement verifies the day-level controller or weather generator.
8. Do not convert the proxy loss V + lambda × Q100 to money without justified conversion parameters.

## Minimum author/editorial release checklist

- [ ] Author confirms title, byline, affiliation, contribution statement and permission to use underlying work.
- [ ] Confirm whether the target journal has an AI-assistance disclosure requirement and supply accurate disclosure.
- [ ] Freeze the actual manuscript revision and crosswalk all table values to the exact input snapshot.
- [ ] Obtain source-level weather-generator and controller replay, or state transparently that only outputs are auditable.
- [ ] Verify all literature references against publisher/DOI records; no references are asserted as verified in this note.
- [ ] Obtain journal-specific ethics, data availability, funding, conflicts and supplementary-material statements.
- [ ] Independent methodological review of clustering, uncertainty, units and scenario provenance.
- [ ] Owner approves the final external submission and any release of private supplementary datasets.

**Gate verdict:** Numerical postprocessing is an intermediate reproducibility control; scientific submission readiness is **NOT PROVEN**. No email, journal submission, production deployment or publication is authorized by this document.
