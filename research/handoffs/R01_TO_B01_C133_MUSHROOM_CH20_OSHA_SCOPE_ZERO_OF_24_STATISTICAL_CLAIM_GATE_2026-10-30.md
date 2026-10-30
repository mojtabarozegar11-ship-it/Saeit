# R-01 → B-01 | Independent source-and-inference handoff | 2026-10-30

**Target:** B-01 English Mushroom Volume II, Chapter 20, owner B-01. **Status:** independent editorial review packet; no edit, merge, deployment, book publication, or owner approval performed by R-01.

## A. OSHA jurisdiction / scope correction

Primary authority inspected 30 October 2026: [29 CFR §1928.21, OSHA official text](https://www.osha.gov/laws-regs/regulations/standardnumber/1928/1928.21). Paragraph (a) lists specific 29 CFR Part 1910 provisions applicable to *agricultural operations* (including hazard communication §1910.1200, subject to its actual scope). Paragraph (b) states that, except as specified in (a), Part 1910 subparts B–T and Z do not apply to agricultural operations. Therefore it is unsafe to assert either that **all** general-industry Part 1910 requirements automatically apply to mushroom-farm agricultural operations, or that a mushroom operation is categorically exempt from general-industry rules. Classification depends on the activity, establishment, work area, processing/packing operation, jurisdiction, and the applicable federal/state plan; the cited regulation alone does not decide the status of every mushroom growing/packing facility. Request competent occupational-safety/legal review of the exact process before labeling a requirement mandatory.

**Safe suggested wording:** “Applicable U.S. occupational-safety requirements depend on whether the specific mushroom-growing, handling, packing or processing activity is classified as an agricultural or general-industry operation, as well as the jurisdiction and state plan. Consult the relevant OSHA standards and a qualified safety professional before treating a particular Part 1910 provision as legally applicable.”

## B. Exact binomial bound for 0 events in 24 trials

If (and only if) 24 observations are independent Bernoulli trials with a common event probability p, and **zero** events are observed, the exact **one-sided 95% upper confidence bound** is `1 - 0.05^(1/24) = 0.117346...` (**11.73%**). The exact **two-sided 95% Clopper–Pearson interval** has lower endpoint 0 and upper endpoint `1 - 0.025^(1/24) = 0.142474...` (**14.25%**). These are **not interchangeable**; the confidence level, sidedness and denominator must be named. The “rule of three” (3/24=12.5%) is only an approximation to the one-sided bound. The zero-event observation does not demonstrate zero hazard, regulatory compliance, commercial safety, or suitability of a product. With batch clustering, dependent observations, nonrandom selection, censored outcomes or unverified event ascertainment, these binomial bounds may be inappropriate.

**Safe suggested wording:** “No event was observed among 24 assessed units. Under an independent identical-probability Bernoulli model, the exact one-sided 95% upper bound is 11.73%; this is not evidence of zero risk. Sample selection and event ascertainment must be documented before generalization.”

## C. Source/claim matrix for B owner

| Claim | Primary source or calculation | Decision | Remaining gate |
|---|---|---|---|
| All Part 1910 rules apply to mushroom agriculture | OSHA §1928.21(a)-(b) | **REJECT** blanket statement | Activity classification and jurisdiction review |
| Agriculture is exempt from all Part 1910 provisions | OSHA §1928.21(a) | **REJECT** blanket exemption | Identify specifically applicable provisions |
| 0/24 means no underlying hazard | Exact binomial likelihood | **REJECT** | Define hazard, sample frame and outcome detection |
| 0/24 implies one-sided 95% upper 11.73% | `1 - .05^(1/24)` | **CONDITIONALLY VALID** | IID Bernoulli assumptions and denominator |
| 0/24 implies two-sided 95% upper 14.25% | `1 - .025^(1/24)` | **CONDITIONALLY VALID** | State Clopper–Pearson and assumptions |

## D. B-01 acceptance recommendation

Insert only after verifying the exact Chapter 20 text and distinguishing farm cultivation from industrial processing. Preserve source attribution; avoid any claim of OSHA certification, verified hazard absence, validated commercial food safety or independent peer review. The owner B-01 retains final editorial control and author-approval/publication gate. This is a handoff, not a release.
