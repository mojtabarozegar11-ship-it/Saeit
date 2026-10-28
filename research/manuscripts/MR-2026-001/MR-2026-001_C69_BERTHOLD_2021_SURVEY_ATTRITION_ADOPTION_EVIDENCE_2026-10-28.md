# MR-2026-001 C69 — Berthold et al. (2021): adoption survey denominator and selection audit

**Document ID:** MR-C69-20261028-v1  
**Status:** READY_FOR_REVIEW — source-level critical extraction; **not** a validated review, experiment, or submission.  
**Primary source:** Berthold TA, Ajaz A, Olsovsky T, Kathuria D (2021). *Identifying barriers to adoption of irrigation scheduling tools in Rio Grande Basin*. *Smart Agricultural Technology* 1, article 100016. DOI: https://doi.org/10.1016/j.atech.2021.100016 . Open-access publisher article, Methods section 2, Results sections 3.2–3.4 and Tables 1–2, accessed 2026-10-28. Source text: https://www.sciencedirect.com/science/article/pii/S2772375521000162 .

## Verified source statements and exact denominators

- The study used a **mailed questionnaire**, not a controlled intervention or independently observed irrigation-event ledger. It randomly selected **1,500** producer addresses from a Texas/New Mexico Rio Grande basin subset of USDA Farm Service Agency payment records (2013–2017). The sampling frame excludes producers outside those eligibility and geographic filters.
- **96** mailings were undeliverable; **310** surveys were returned; **77** responses were considered usable. The article describes a **22% response rate**, consistent with 310/(1500-96)=**22.0798%** using deliverable addresses.
- For the **usable** analytical sample, 77/(1500-96)=**5.4843%** of deliverable mailings, and 77/310=**24.8387%** of returns. These are *derived retention ratios*, not a response-rate correction supplied by the authors. The article does not establish why every returned questionnaire was excluded from the usable sample; do not invent missing-data reasons.
- Adoption-barrier **item-specific n differs**: Table 1 shows **41–54** responses for its displayed items, e.g. weather reliability n=49; uncertain future water n=51; financing n=53; risk of reduced yield n=50. It is invalid to use 77, 310 or 1,500 as a uniform denominator for each reported barrier percentage.
- The questionnaire included 18 questions over seven pages, including self-reported familiarity/use and agreement scales; the authors also used PCA and stepwise regression. These measures capture **perceptions and self-reported practice**, not logged receipt or independently metered adherence to specific advice.
- The authors explicitly acknowledge a limitation of **77 usable responses**. Nonresponse, eligible-population selection, self-report and variable item response all constrain generalization; no causal intervention effect can be inferred.

## Consequence for MR's novelty and claim-evidence matrix

This **pre-existing empirical study directly examines farmer familiarity, use and adoption barriers** for scientific irrigation scheduling. MR must not claim originality for farmer adoption surveys, barrier taxonomies, or combining agronomic and socioeconomic considerations. The narrower proposed difference is *recommendation-event provenance* linking generation, delivery/receipt, observed action, measured physical outcome and valid counterfactual, plus later independent reuse. **The Berthold survey is not a ninth fully extracted field-intervention case** in MR's purposively chosen eight-case matrix.

**Evidence class:** S (surveyed self-report/attitude); O (independently observed implementation) **not established**; M (physical outcome measured by this survey) **not established**; P (causal modelled saving attributable to this survey) **not established**. Lack of those measurements *in this survey's inspected methods* is not a universal claim about all earlier irrigation research.

## Reproduction (calculator only; not independent empirical replication)

```python
sent, undeliverable, returned, usable = 1500, 96, 310, 77
deliverable = sent - undeliverable
assert deliverable == 1404
assert round(100 * returned / deliverable, 1) == 22.1
assert round(100 * usable / deliverable, 2) == 5.48
assert round(100 * usable / returned, 2) == 24.84
assert min([49,51,53,50,41,54]) == 41
```

**Decision:** add as an adjacent prior-art comparator in the manuscript Introduction and references, *not* as a new primary field trial. Do not assert verified G/D/R/A chain or publishability. **MAJOR REVISION / NO SUBMISSION**. Human-author interpretation and source confirmation pending.
