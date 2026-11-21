# R01 — reproducible evidence ledger and falsification protocol (2026-11-15)

**Classification:** internal scientific supplement; not a journal submission, field experiment, or efficacy claim. All numerical results below are *archived synthetic-model outputs* reported in the R01 source crosswalk, not independently reproduced in this document.

## Frozen evidence table (descriptive, v3 minus v2)

| Quantity | Cohort C | Regime R1 | Interpretation |
|---|---:|---:|---|
| Archived policy records | 1,620 | 2,160 | Model outputs, not farm observations |
| Matched scenario keys | 540 | 540 | 45 factorial cells per climate path |
| Climate paths | 12 | 12 | Primary dependence grouping |
| Mean modeled irrigation difference (m³) | +36.068955967 | +30.575281425 | v3 uses **more**, not less, modeled irrigation |
| Mean simulated Q100 threshold-day difference | −6.892592593 | −7.470370370 | Fewer modeled threshold-days, not observed yield |
| v3 dominates / v2 dominates / ties / tradeoff (higher water, lower Q) | 65 / 229 / 89 / 157 | 43 / 232 / 94 / 171 | Exhaustive 540-key partition |

Source: `PAIRED_RESULTS_AND_LIMITATIONS_20261115.md`, Tables 1–3, from author-controlled native workbook `ZM-IRR-MODEL-2026-01`. The present document does **not** independently certify the workbook's provenance or recreate its generator.

## Twenty separately auditable scientific controls

Each line states a **required check and failure criterion**, not a claim that the check passed.

| ID | Control | Pass evidence required | Failure / hold |
|---|---|---|---|
| E01 | Raw provenance | Original export bytes, custodian, timestamp, immutable SHA-256 | Missing original bytes |
| E02 | Generator provenance | Exact generator commit, dependencies and executable entrypoint | Recovered code only |
| E03 | Deterministic replay | Fresh export reproduces frozen file or declared numeric tolerance | Unexplained mismatch |
| E04 | Policy identity | v2/v3 definitions and stable mapping to all native policy labels | Ambiguous policy |
| E05 | Pair integrity | One v2 and one v3 per composite key, no duplicates | Missing or duplicate pair |
| E06 | Family separation | C and R1 analyzed separately, with explicit denominators | Accidental pooling |
| E07 | Path dependence | Twelve path IDs and 45 within-path factorial cells verified | Treating 540 as independent |
| E08 | Climate stratification | Four path IDs per dry/medium/wet class, labels crosschecked | Class/path mismatch |
| E09 | Factorial completeness | Five bias × three ET × three rainfall-information cases per path | Incomplete cell grid |
| E10 | Water units | m³ per defined 0.1 ha, 30-day model profile; no mm substitution | Unlabeled denominator |
| E11 | Drainage units | mm depth kept separate from m³ water volume | Invalid dimensional arithmetic |
| E12 | Q100 definition | Exact threshold and observation timing from source generator | Interpreted as crop yield |
| E13 | Difference orientation | Δ=v3−v2 throughout code, figures and manuscript | Sign reversal |
| E14 | Missing-value policy | Nonfinite, blank, malformed and inconsistent rows rejected or accounted for | Silent deletion |
| E15 | Pareto accounting | All five exclusive categories sum to 540 per family | Nonexhaustive partition |
| E16 | Weight sensitivity | All eight λ weights and tie tolerance displayed; λ units m³/Q-day | Selective best-weight claim |
| E17 | Forecast leakage | Identify cases using realized same-day rainfall and quarantine oracle scenarios | Prospective superiority claim |
| E18 | Robustness | Leave-one-climate-path-out descriptive summaries with path identities | Naive row-bootstrap inference |
| E19 | External validation | Independent meters, forecast issue timestamps, soil and crop observations | Real-world efficacy claim |
| E20 | Disclosure/release | Author rights, synthetic-data disclosure, editorial approval, CI on final SHA | Submission or marketing |

## Cross-table arithmetic checks that can be verified from the printed tables

- C partition: 65 + 229 + 89 + 157 + 0 = **540**.
- R1 partition: 43 + 232 + 94 + 171 + 0 = **540**.
- C row count: 540 × 3 = **1,620**; R1: 540 × 4 = **2,160**.
- Per family: 12 × (5 × 3 × 3) = **540**; per climate class: 4 × 45 = **180**.
- At λ=0, ΔL=ΔV by definition; at λ=10, C mean ΔL ≈ 36.068955967 − 10×6.892592593 = **−32.856969963** and R1 ≈ 30.575281425 − 10×7.470370370 = **−44.128422275**. Differences of ~4×10⁻⁹ from displayed Table 3 are expected from rounded source means, **not** proof of a generator replay.

## Publication-safe interpretation

> In two distinct synthetic irrigation-policy archives, v3 produced higher mean modeled gross irrigation volumes than v2 while reducing the number of modeled Q100 threshold-days. These conflicting outcomes describe a simulation-specific water-versus-threshold tradeoff. The archives do not establish actual water savings, crop productivity, economic profitability, or prospective controller performance.

**Inference boundary:** The factorial scenarios are not sampled farms, and the twelve climate paths are not a defensible basis for ordinary row-level independent confidence intervals. Any future interval must document a sampling model, small-cluster limitations and sensitivity to each path.

**Source methodology:** FAO-56 (Allen et al., 1998), https://www.fao.org/4/X0490E/x0490e00.htm; Cameron and Miller (2015), *A Practitioner's Guide to Cluster-Robust Inference*, Journal of Human Resources 50(2):317–372, https://doi.org/10.3368/jhr.50.2.317. These sources motivate methods only; they do not validate R01 results.

**Release gate:** Keep PR draft. No merge, customer-facing publication, journal submission, email, transaction or deployment. All E01–E20 remain **not independently certified by this ledger** until underlying evidence is inspected.
