# R01 frozen-source release evidence checklist — 2026-11-16

**Scientific classification:** modeled/synthetic irrigation scenarios only. This is a prospective source-replay and editorial acceptance protocol, NOT a report of executed experiments. Source PR #1999 describes 1,620 C and 2,160 R1 policy rows (540 matched scenario keys in each family; 12 simulated climate paths per family). These counts are PR assertions, not freshly verified by this document.

## Twenty distinct deliverables and their acceptance artifacts

| ID | Independent deliverable | Machine-verifiable or reviewable acceptance evidence | Current status |
|---|---|---|---|
| B01 | Freeze source C archive | File path, byte length and SHA-256 digest | Missing |
| B02 | Freeze source R1 archive | File path, byte length and SHA-256 digest | Missing |
| B03 | Freeze generator revision | Exact Git commit and immutable code archive digest | Missing |
| B04 | Freeze generator inputs | Seed list, parameter values and input manifest | Missing |
| B05 | Establish source permissions | Signed author authorization and data reuse terms | Missing |
| B06 | Validate C policy-row count | Parsed count 1,620 with rejected-row log | Not rerun |
| B07 | Validate R1 policy-row count | Parsed count 2,160 with rejected-row log | Not rerun |
| B08 | Validate paired keys | Exactly 540 unique matched keys per family | Not rerun |
| B09 | Validate policy completeness | Every C key has 3 policies; every R1 key has 4 | Not rerun |
| B10 | Validate climate clusters | Exactly 12 climate paths per family, not 3,780 independent farms | Not rerun |
| B11 | Validate climate strata | Four dry, four medium, four wet paths per family | Not rerun |
| B12 | Audit action-time information | Per-decision timestamp and allowed observed variables | Missing |
| B13 | Audit forecast provenance | Forecast issued_at <= decision_at and forecast horizon recorded | Missing |
| B14 | Reject realized-rain leakage | Trace every rainfall value to availability time | Missing |
| B15 | Establish information parity | Compare policies under identical ex-ante information set | Missing |
| B16 | Verify water mass balance | Input - runoff - ET - drainage - delta-storage residual, tolerance stated | Missing |
| B17 | Verify units | Irrigation/drainage mm, energy kWh, yield measured vs modeled distinguished | Missing |
| B18 | Recompute paired path outcomes | Twelve path-level deltas per family; complete denominators | Not rerun |
| B19 | Quantify tradeoffs | Water, Q98, events, drainage, energy and yield proxies separately; no selective benefit claim | Incomplete |
| B20 | Complete publication dossier | Methods, limitations, disclosures, reproducibility archive, author approval and external review | Missing |

**Status definitions:** “Not rerun” means prior PR narrative claims exist but this cycle did not independently execute them; “Missing” means required immutable evidence is not available in this document. These twenty entries are requirements, **not twenty completed scientific validations**.

## Prespecified paired analysis

For each family f, climate path h, scenario k, and modeled policy p, calculate D(f,h,k,p)=Y(f,h,k,p)-Y(f,h,k,baseline) only when both outcomes are present and share the same ex-ante information. Average D within each climate path first; summarize the 12 path means and report each climate class separately. Disclose missingness, path-level range and leave-one-path-out descriptive sensitivity. Do not treat policy rows as independent field replicates or leave-one-path-out ranges as confidence intervals. For inference with 12 clusters, preregister an appropriate small-cluster procedure and clearly label exploratory contrasts.

## Prepublication results table template (no invented data)

| Family | Outcome | Unit | Baseline mean | Comparison mean | Paired delta | Path count | Source digest | Status |
|---|---|---|---|---|---|---|---|---|
| C | Irrigation applied | mm | — | — | — | — | — | Unverified |
| C | Q98 threshold days | modeled days | — | — | — | — | — | Unverified |
| C | Drainage | mm | — | — | — | — | — | Unverified |
| R1 | Irrigation applied | mm | — | — | — | — | — | Unverified |
| R1 | Q98 threshold days | modeled days | — | — | — | — | — | Unverified |
| R1 | Drainage | mm | — | — | — | — | — | Unverified |

**Known caution from existing PR narrative (not newly verified):** modeled v3-v2 Q98 threshold-day deltas are reported as C -4.342593 and R1 -4.794444; simulated irrigation event deltas +1.855556 and +1.703704, and drainage depth deltas +13.435478 and +12.016956 mm. More events/drainage are possible adverse tradeoffs. No measured water savings, yield increase, causal field effect or profit follows.

## Primary methodological sources (bibliographic pointers, not proof of data)

- Allen RG, Pereira LS, Raes D, Smith M (1998). FAO Irrigation and Drainage Paper 56, *Crop evapotranspiration*. https://www.fao.org/4/x0490e/x0490e00.htm
- Imbens GW, Kolesár M (2016). Robust standard errors in small samples: some practical advice. *Review of Economics and Statistics* 98(4):701–712. https://doi.org/10.1162/REST_a_00552

## Release decision

**NO SUBMISSION / NO AGRONOMIC SALES CLAIM.** Missing original-archive digests, generator replay, decision-time forecast provenance, physical balance checks, author permissions and independently observed field evidence prevent scientific or commercial efficacy claims. Do not email, merge, deploy, publish, charge or present synthetic results as experimental measurements. Exact-head CI is necessary but cannot replace scientific validity.
