# R01 — scientific inference and disclosure gates (2026-11-15)

**Status:** methodological review material, not a field experiment, manuscript submission, or evidence of agronomic efficacy. The PR's reported 3,780 modeled policy records consist of two families with 540 matched scenario keys each and 3 or 4 policy alternatives respectively. Twelve modeled climate paths per family are not 1,080 independent farms. Counts below are inherited from the PR description and require re-verification against frozen original archives before publication.

## Twenty independent scientific gates

| ID | Required verification | Acceptance evidence | Current assessment |
|---|---|---|---|
| 01 | Identify observational unit | Explicit matched scenario key and path identifier | Described; original archive audit pending |
| 02 | Identify experimental unit | No simulated row called a field replicate | Methodological restriction |
| 03 | Specify target population | State simulated weather/soil/management domain | Not established |
| 04 | Provenance of inputs | Hashes, licenses and dated source manifests | Pending |
| 05 | Generator provenance | Versioned generator and deterministic configuration | Pending |
| 06 | Scenario completeness | Each family has 540 complete matched keys | Reported in PR; rerun pending |
| 07 | Policy balance | C: 3 and R1: 4 policies per key | Reported; rerun pending |
| 08 | Climate-path dependence | Cluster all outcomes by underlying path | Required |
| 09 | Path-class stratification | Four dry, four medium, four wet per family | Reported; rerun pending |
| 10 | Forecast timing | Forecast issue time precedes decision time | **Blocked** |
| 11 | Information parity | All controllers share permitted ex-ante information | **Blocked** |
| 12 | Leakage check | Flag realized same-day rainfall used in decisions | **Known concern** |
| 13 | Water accounting | Define withdrawals, applied irrigation, drainage in mm | Partial; reconcile mass balance |
| 14 | Outcome semantics | Define Q, its units, and whether it is a proxy | Pending |
| 15 | Pairing integrity | Exactly one outcome per policy per matched key | Reported; rerun pending |
| 16 | Effect estimand | Report paired differences, not causal field effects | Descriptive only |
| 17 | Uncertainty | Path-level interval or sensitivity, not row-wise IID CI | Pending |
| 18 | Multiplicity | Label eight decision weights exploratory | Required |
| 19 | External validation | Independent observed field or held-out operational data | Not available |
| 20 | Commercial claim gate | No realized savings/profit claims without measured evidence | **Not passed** |

## Pre-specified analysis protocol

For a matched key `k` and policy `p`, compute `d(k,p)=Y(k,p)-Y(k,baseline)`. Aggregate first within each climate path `h`, then summarize the 12 path-level means within each family. Report the mean, median, minimum, maximum and all 12 individual path-level effects. Where the number of paths is small, describe the range rather than present artificially precise confidence intervals. Do not treat policy rows or weather paths sharing a generator as independent farm replicates.

A proposed sensitivity analysis excludes any scenario whose controller used realized rainfall unavailable at decision time; **do not execute or interpret that exclusion as a prospective comparison until forecast timestamps and policy information sets have been reconstructed**. Repeat the descriptive summaries separately for dry, medium and wet classes; display denominators. Report all eight decision-weight results without choosing a favorable weight after observing the outcomes.

## Reporting table (not fabricated results)

| Family | Policy | Paths (n) | Matched keys (n) | Mean paired water effect (mm) | Median path effect (mm) | Mean paired Q effect (defined units) | Ex-ante comparable? |
|---|---|---:|---:|---|---|---|---|
| C | Each non-baseline policy | Verify 12 | Verify 540 | Await frozen-source computation | Await computation | Await Q definition and computation | Unverified |
| R1 | Each non-baseline policy | Verify 12 | Verify 540 | Await frozen-source computation | Await computation | Await Q definition and computation | Unverified |

No blank cells in this table should be silently replaced by zeros. Negative water differences signify less applied water only if the source variable is defined as applied irrigation; they do not by themselves imply yield, profit or environmental benefits.

## Author-facing limitations paragraph

This work evaluates deterministic or stochastic **simulated** irrigation policy outcomes under author-specified scenarios. The unit of paired comparison is a scenario key; climate paths provide a much smaller dependence-aware summary scale. Model-based contrasts are descriptive and conditional on generator assumptions. Some original controller decisions may have access to realized rainfall, which would not be available to a prospective decision maker. Consequently these analyses cannot establish real-world treatment efficacy, out-of-sample forecast skill, yield gains, or realized economic returns. Original generator replay, input provenance, decision-time information parity, independent field validation, and author approval remain prerequisites for external claims.

## Reproducibility release gate

Archive a manifest with SHA-256 for every input, generator, configuration, output, script and manuscript table; record exact command, Python version, random seeds and UTC execution time. Require a fresh clean-environment rerun, exact row/key reconciliation, path-level cross-checks and CI on the exact commit. Preserve the source files privately if licenses or author permissions prohibit distribution. Release only an appropriately redacted reproducibility package with author approval.

## Reference anchors (methodology; not dataset validation)

- Allen, R.G. et al. (1998). *Crop evapotranspiration: Guidelines for computing crop water requirements*. FAO Irrigation and Drainage Paper 56. https://www.fao.org/4/x0490e/x0490e00.htm
- Cameron, A.C. & Miller, D.L. (2015). A practitioner's guide to cluster-robust inference. *Journal of Human Resources*, 50(2), 317–372. https://doi.org/10.3368/jhr.50.2.317
- Wasserstein, R.L. & Lazar, N.A. (2016). The ASA statement on p-values. *The American Statistician*, 70(2), 129–133. https://doi.org/10.1080/00031305.2016.1154108

**Release controls:** no journal submission, email, payment, PR merge, deployment or empirical marketing claim authorized by this document.
